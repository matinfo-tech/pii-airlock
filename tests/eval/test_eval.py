"""Recall/precision gate on the labeled corpus. Needs the small spaCy models.

Run with `pytest -m eval` (deselected by default: loading models is slow).
"""

import json

import pytest

from tests.eval.run_eval import (
    SHELL_CORPUS,
    SMALL_MODELS,
    THRESHOLDS,
    available_models,
    check_gate,
    check_shell_gate,
    evaluate,
    evaluate_shell,
    format_report,
    format_shell_report,
    gold_spans,
    load_corpus,
)


@pytest.mark.parametrize("path", [None, SHELL_CORPUS], ids=["corpus", "shell"])
def test_corpus_labels_are_present_in_text(path):
    for case in load_corpus(*([path] if path else [])):
        found = {(e, case["text"][s:t]) for e, s, t in gold_spans(case)}
        for entity, value in case["pii"]:
            assert (entity, value) in found, f"{case['id']}: {value!r} not in text"


@pytest.mark.eval
def test_detection_quality_gate():
    if set(available_models(SMALL_MODELS)) != set(SMALL_MODELS):
        pytest.skip("run `python -m spacy download en_core_web_sm fr_core_news_sm`")
    report = evaluate(load_corpus(), SMALL_MODELS)
    failures = check_gate(report, json.loads(THRESHOLDS.read_text("utf-8")))
    assert not failures, format_report(report, verbose=True)


@pytest.mark.eval
def test_shell_command_gate():
    if set(available_models(SMALL_MODELS)) != set(SMALL_MODELS):
        pytest.skip("run `python -m spacy download en_core_web_sm fr_core_news_sm`")
    report = evaluate_shell(load_corpus(SHELL_CORPUS), SMALL_MODELS)
    failures = check_shell_gate(report, json.loads(THRESHOLDS.read_text("utf-8")))
    assert not failures, format_shell_report(report, verbose=True)


@pytest.mark.eval
def test_batched_analysis_matches_one_by_one():
    from pii_scrub.config import Config
    from pii_scrub.engine import ScrubEngine

    models = available_models(SMALL_MODELS)
    if not models:
        pytest.skip("no small spaCy model installed")
    texts = [case["text"] for case in load_corpus()]

    def run(prime: bool):
        engine = ScrubEngine(Config(languages=list(models), models=models))
        if prime:
            engine.prime(texts)
        return [sorted((d.entity_type, d.start, d.end, d.score) for d in engine.detect(t))
                for t in texts]

    assert run(prime=True) == run(prime=False)
