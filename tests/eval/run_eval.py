"""Detection quality harness: per-entity recall/precision on a labeled EN+FR corpus.

    python -m tests.eval.run_eval                 # report
    python -m tests.eval.run_eval --gate          # exit 1 if below thresholds.json
    python -m tests.eval.run_eval -v              # also list misses and false positives
    python -m tests.eval.run_eval --models en=en_core_web_lg,fr=fr_core_news_lg
    python -m tests.eval.run_eval --backend gliner   # needs pii-airlock[gliner]
    python -m tests.eval.run_eval --threshold 0.4 --timing

The corpus (corpus.jsonl) holds only fake data. Each case lists the PII values
that appear in its text; every occurrence of a value is a gold span.

Metrics, per entity type:
  recall     gold spans overlapped by a detection of the same type
  precision  detections overlapping a gold span of the same type
  leak-free  gold spans fully covered by detections of *any* type (what matters
             for privacy: a PERSON tokenized as LOCATION is still hidden)

Disguised PII (obfuscated.jsonl: zero-width characters, look-alike letters, "[at]" and
"dot", URL/HTML/JSON escapes, fullwidth digits, base64) is scored on leak-free coverage,
and its clean texts on pattern false alarms (names are left to the main corpus).

Code-like inputs (shell_commands.jsonl, code_snippets.jsonl: commands, search patterns,
paths, source code) are scored the way the tool hook sees them, after its code filter:
  clean      inputs without PII that raise no detection (a false alarm stops the agent)
  recall     gold spans in inputs with PII that are still detected
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pii_scrub import models as model_store
from pii_scrub.config import Config
from pii_scrub.engine import ScrubEngine

HERE = Path(__file__).parent
CORPUS = HERE / "corpus.jsonl"
CODE_CORPORA = (HERE / "shell_commands.jsonl", HERE / "code_snippets.jsonl")
OBFUSCATED_CORPUS = HERE / "obfuscated.jsonl"
THRESHOLDS = HERE / "thresholds.json"
THRESHOLDS_BY_BACKEND = {"gliner": HERE / "thresholds-gliner.json"}
SMALL_MODELS = {
    "en": "en_core_web_sm", "fr": "fr_core_news_sm",
    "de": "de_core_news_sm", "it": "it_core_news_sm",
}


@dataclass
class Stats:
    gold: int = 0
    found: int = 0       # gold spans hit by a same-type detection
    covered: int = 0     # gold spans fully covered by any detection
    detected: int = 0
    correct: int = 0     # detections hitting a same-type gold span

    @property
    def recall(self) -> float:
        return self.found / self.gold if self.gold else 1.0

    @property
    def leak_free(self) -> float:
        return self.covered / self.gold if self.gold else 1.0

    @property
    def precision(self) -> float:
        return self.correct / self.detected if self.detected else 1.0


@dataclass
class Report:
    per_entity: dict[str, Stats] = field(default_factory=lambda: defaultdict(Stats))
    total: Stats = field(default_factory=Stats)
    misses: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)


def load_corpus(path: Path = CORPUS) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def load_code_corpora() -> list[dict]:
    return [case for path in CODE_CORPORA for case in load_corpus(path)]


def gold_spans(case: dict) -> list[tuple[str, int, int]]:
    """Every occurrence of every labeled value, as (entity, start, end)."""
    text, spans = case["text"], set()
    for entity, value in case["pii"]:
        for m in re.finditer(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text):
            spans.add((entity, m.start(), m.end()))
    return sorted(spans, key=lambda s: s[1])


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def available_models(models: dict[str, str]) -> dict[str, str]:
    """Models that load: installed packages, or copies in the model store."""
    return {lang: m for lang, m in models.items() if model_store.locate(m) is not None}


_ENGINES: dict[tuple, ScrubEngine] = {}
#: Config overrides for every engine the harness builds (--threshold).
SETTINGS: dict = {}


def _engine(models: dict[str, str], backend: str) -> ScrubEngine:
    """One engine per model set, so the models load once for all three corpora."""
    key = (tuple(sorted(models.items())), backend, tuple(sorted(SETTINGS.items())))
    if key not in _ENGINES:
        _ENGINES[key] = ScrubEngine(Config(languages=list(models), models=models,
                                           ner_backend=backend, **SETTINGS))
    return _ENGINES[key]


def evaluate(cases: list[dict], models: dict[str, str], backend: str = "spacy") -> Report:
    if backend == "spacy":
        models = available_models(models)
    engine = _engine(models, backend)
    report = Report()
    for case in cases:
        text = case["text"]
        gold = gold_spans(case)
        dets = [(d.entity_type, d.start, d.end) for d in engine.detect(text)]
        for entity, start, end in gold:
            stats = (report.per_entity[entity], report.total)
            hit = any(t == entity and _overlap((s, e), (start, end)) for t, s, e in dets)
            covered = _covered(start, end, [(s, e) for _, s, e in dets])
            for st in stats:
                st.gold += 1
                st.found += hit
                st.covered += covered
            if not hit:
                kind = "LEAK" if not covered else "mistyped"
                report.misses.append(f"[{case['id']}] {kind} {entity}: {text[start:end]!r}")
        for entity, start, end in dets:
            ok = any(t == entity and _overlap((start, end), (s, e)) for t, s, e in gold)
            for st in (report.per_entity[entity], report.total):
                st.detected += 1
                st.correct += ok
            if not ok:
                report.false_positives.append(
                    f"[{case['id']}] extra {entity}: {text[start:end]!r}"
                )
    return report


@dataclass
class CodeReport:
    inputs: int = 0      # inputs without PII
    clean: int = 0       # of those, no detection after the hook's filter
    unfiltered: int = 0  # of those, no detection before it
    gold: int = 0
    found: int = 0
    false_alarms: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def clean_rate(self) -> float:
        return self.clean / self.inputs if self.inputs else 1.0

    @property
    def recall(self) -> float:
        return self.found / self.gold if self.gold else 1.0


def evaluate_code(cases: list[dict], models: dict[str, str],
                   backend: str = "spacy") -> CodeReport:
    """Score code-like inputs as the pre-tool-use hook does (see _drop_code_noise)."""
    from pii_scrub.hooks._common import _drop_code_noise

    if backend == "spacy":
        models = available_models(models)
    engine = _engine(models, backend)
    report = CodeReport()
    for case in cases:
        text = case["text"]
        raw = engine.detect(text)
        ((_, kept),) = _drop_code_noise([(text, raw)])
        gold = gold_spans(case)
        if not gold:
            report.inputs += 1
            report.unfiltered += not raw
            report.clean += not kept
            if kept:
                found = ", ".join(f"{d.entity_type} {text[d.start:d.end]!r}" for d in kept)
                report.false_alarms.append(f"[{case['id']}] {text!r}: {found}")
        for entity, start, end in gold:
            hit = any(_overlap((d.start, d.end), (start, end)) for d in kept)
            report.gold += 1
            report.found += hit
            if not hit:
                report.misses.append(f"[{case['id']}] LEAK {entity}: {text[start:end]!r}")
    return report


_NER_ONLY = frozenset({"PERSON", "LOCATION", "ORGANIZATION", "NRP"})


@dataclass
class ObfuscatedReport:
    gold: int = 0
    covered: int = 0
    texts: int = 0       # clean texts
    clean: int = 0       # of those, no pattern detection
    leaks: list[str] = field(default_factory=list)
    false_alarms: list[str] = field(default_factory=list)

    @property
    def leak_free(self) -> float:
        return self.covered / self.gold if self.gold else 1.0

    @property
    def clean_rate(self) -> float:
        return self.clean / self.texts if self.texts else 1.0


def evaluate_obfuscated(cases: list[dict], models: dict[str, str],
                        backend: str = "spacy") -> ObfuscatedReport:
    if backend == "spacy":
        models = available_models(models)
    engine = _engine(models, backend)
    report = ObfuscatedReport()
    for case in cases:
        text, dets = case["text"], engine.detect(case["text"])
        gold = gold_spans(case)
        if not gold:
            report.texts += 1
            extra = [d for d in dets if d.entity_type not in _NER_ONLY]
            report.clean += not extra
            if extra:
                report.false_alarms.append(f"[{case['id']}] " + ", ".join(
                    f"{d.entity_type} {text[d.start:d.end]!r}" for d in extra))
        for entity, start, end in gold:
            covered = _covered(start, end, [(d.start, d.end) for d in dets])
            report.gold += 1
            report.covered += covered
            if not covered:
                report.leaks.append(f"[{case['id']}] LEAK {entity}: {text[start:end]!r}")
    return report


def format_obfuscated_report(report: ObfuscatedReport, verbose: bool = False) -> str:
    rows = [f"disguised PII: {report.covered}/{report.gold} caught, "
            f"{report.clean}/{report.texts} clean texts without a false alarm"]
    if verbose:
        rows += ["", "Disguised leaks:", *report.leaks,
                 "", "Disguised false alarms:", *report.false_alarms]
    return "\n".join(rows)


def check_obfuscated_gate(report: ObfuscatedReport, thresholds: dict) -> list[str]:
    values = {"leak_free": report.leak_free, "clean": report.clean_rate}
    return [f"OBFUSCATED {metric} {values[metric]:.2f} < {floor:.2f}"
            for metric, floor in thresholds.get("OBFUSCATED", {}).items()
            if values[metric] + 1e-9 < floor]


def format_code_report(report: CodeReport, verbose: bool = False) -> str:
    rows = [f"code-like inputs: {report.clean}/{report.inputs} clean "
            f"({report.unfiltered} before the hook's filter), "
            f"recall {report.found}/{report.gold}"]
    if verbose:
        rows += ["", "Code false alarms:", *report.false_alarms,
                 "", "Code misses:", *report.misses]
    return "\n".join(rows)


def check_code_gate(report: CodeReport, thresholds: dict) -> list[str]:
    floors = thresholds.get("CODE", {})
    values = {"clean": report.clean_rate, "recall": report.recall}
    return [f"CODE {metric} {values[metric]:.2f} < {floor:.2f}"
            for metric, floor in floors.items() if values[metric] + 1e-9 < floor]


def _covered(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """Whether [start, end) is fully inside the union of `spans`."""
    pos = start
    for s, e in sorted(spans):
        if s <= pos < e:
            pos = e
    return pos >= end


def format_report(report: Report, verbose: bool = False) -> str:
    rows = [f"{'entity':<16}{'gold':>5}{'recall':>9}{'leak-free':>11}{'precision':>11}"]
    for entity, st in sorted(report.per_entity.items()):
        rows.append(
            f"{entity:<16}{st.gold:>5}{st.recall:>9.2f}{st.leak_free:>11.2f}{st.precision:>11.2f}"
        )
    t = report.total
    rows.append(f"{'ALL':<16}{t.gold:>5}{t.recall:>9.2f}{t.leak_free:>11.2f}{t.precision:>11.2f}")
    if verbose:
        rows += ["", "Misses:", *report.misses, "", "Extra detections:", *report.false_positives]
    return "\n".join(rows)


def check_gate(report: Report, thresholds: dict) -> list[str]:
    """Return failure messages for every metric below its threshold."""
    failures = []
    for entity, floors in thresholds.items():
        if entity in ("CODE", "OBFUSCATED"):
            continue  # see check_code_gate
        st = report.total if entity == "ALL" else report.per_entity.get(entity, Stats())
        for metric, floor in floors.items():
            value = getattr(st, metric)
            if value + 1e-9 < floor:
                failures.append(f"{entity} {metric} {value:.2f} < {floor:.2f}")
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if below thresholds.json (thresholds-gliner.json for gliner)")
    ap.add_argument("-v", "--verbose", action="store_true", help="list misses and extras")
    ap.add_argument("--models", help="lang=model pairs, e.g. en=en_core_web_lg,fr=fr_core_news_lg")
    ap.add_argument("--backend", choices=["spacy", "gliner"], default="spacy")
    ap.add_argument("--threshold", type=float, help="score_threshold (default: the config's)")
    ap.add_argument("--timing", action="store_true", help="print model load and scan times")
    args = ap.parse_args(argv)
    if args.threshold is not None:
        SETTINGS["score_threshold"] = args.threshold

    models = dict(SMALL_MODELS)
    if args.models:
        models = dict(pair.split("=", 1) for pair in args.models.split(","))
    missing = sorted(set(models) - set(available_models(models)))
    if missing and args.backend == "spacy":
        print(f"warning: models not installed for {missing}; those cases are scored anyway",
              file=sys.stderr)
    clock = time.perf_counter()
    if args.backend == "spacy":
        _engine(available_models(models), args.backend).load()
    else:
        _engine(models, args.backend).load()
    timings = [("model load", time.perf_counter() - clock)]

    def timed(label, run, *a):
        start = time.perf_counter()
        result = run(*a)
        timings.append((label, time.perf_counter() - start))
        return result

    report = timed("corpus", evaluate, load_corpus(), models, args.backend)
    print(format_report(report, args.verbose))
    code = timed("code", evaluate_code, load_code_corpora(), models, args.backend)
    print("\n" + format_code_report(code, args.verbose))
    disguised = timed("disguised", evaluate_obfuscated, load_corpus(OBFUSCATED_CORPUS),
                      models, args.backend)
    print(format_obfuscated_report(disguised, args.verbose))
    if args.timing:
        print("\ntiming: " + ", ".join(f"{label} {sec:.1f}s" for label, sec in timings))
    if args.gate:
        path = THRESHOLDS_BY_BACKEND.get(args.backend, THRESHOLDS)
        thresholds = json.loads(path.read_text("utf-8"))
        failures = (check_gate(report, thresholds) + check_code_gate(code, thresholds)
                    + check_obfuscated_gate(disguised, thresholds))
        if failures:
            print("\nGATE FAILED:\n  " + "\n  ".join(failures), file=sys.stderr)
            return 1
        print("\ngate ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
