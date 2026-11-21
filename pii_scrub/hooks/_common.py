"""Shared logic for the Claude Code hooks.

Both hooks read the event JSON from stdin, run PII detection over the relevant
text, and print a decision JSON to stdout. They never rewrite the payload (the
hook API can't reliably do that) — they surface PII so the user can decide.

Detection runs in the hook daemon when one answers (models stay loaded between
calls), else in this process (see ``hook_daemon`` / ``hook_fallback``).

Fail closed: if detection itself fails (missing spaCy model, unreadable file),
the input is treated as containing PII unless ``hook_on_error: open``.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from pii_scrub import daemon
from pii_scrub.config import Config, load_config
from pii_scrub.engine import Detection, ScrubEngine, apply_detections
from pii_scrub.mapping import Mapping
from pii_scrub.project import find_project, is_active
from pii_scrub.token_key import token_key

# Tool-input fields worth scanning, per tool name. `Read` is special-cased: the
# file *content* is what reaches the model, so the hook reads and scans it.
_TOOL_FIELDS: dict[str, tuple[str, ...]] = {
    "Bash": ("command",),
    "Write": ("content", "file_path"),
    "Edit": ("new_string", "old_string"),
    "MultiEdit": ("edits",),
    "NotebookEdit": ("new_source",),
    "Read": ("file_path",),
    "Grep": ("pattern", "path", "glob"),
    "WebFetch": ("url", "prompt"),
    "WebSearch": ("query",),
}

# Chunk size for scanning file contents (spaCy refuses texts over ~1M chars).
_CHUNK_CHARS = 100_000


class _ScanError(Exception):
    """Detection could not run; handled according to `hook_on_error`."""


# Failures that must not end the hook before it prints a decision: a non-zero
# exit makes Claude Code treat the hook as a non-blocking error (fail open).
# SystemExit included: spaCy's model downloader calls sys.exit().
_FAILURES = (Exception, SystemExit)


def _error_text(exc: BaseException) -> str:
    detail = str(exc) or type(exc).__name__
    if isinstance(exc, SystemExit):
        detail = "a library exited during detection (missing spaCy model?)"
    return (f"{detail} Run `pii-airlock doctor`, or set `hook_on_error: open` "
            "to skip checks.")


def _quiet():
    """Keep library chatter off stdout, which Claude Code parses as JSON."""
    return contextlib.redirect_stdout(sys.stderr)


def _read_event() -> dict:
    try:
        return _normalize(json.loads(sys.stdin.read() or "{}"))
    except json.JSONDecodeError:
        return {}


def _normalize(event: dict) -> dict:
    """Bring a GitHub Copilot hook payload (camelCase `toolName`/`toolArgs`, or the
    snake_case alias, with the arguments possibly as a JSON string) to Claude Code's shape."""
    if not isinstance(event, dict):
        return {}
    if {"toolName", "sessionId"} & event.keys():
        event = {**event, "tool_name": event.get("toolName") or "",
                 "tool_input": event.get("toolArgs")}
    # Copilot's `tool_input` (PascalCase events) can be the raw JSON string too.
    args = event.get("tool_input")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"raw": args}  # unparseable: still scanned as text
        event = {**event, "tool_input": args}
    if "tool_input" in event and not isinstance(event["tool_input"], dict):
        event = {**event, "tool_input": {}}
    return event


def _load_config(event: dict) -> tuple[Config, BaseException | None]:
    """Config for the project Claude Code reports (its SKILL.md policy applies).

    A broken config (e.g. invalid YAML in the policy block) must not crash the
    hook — that would fail open. Fall back to defaults and report the error.
    """
    try:
        return load_config(cwd=event.get("cwd") or None), None
    except _FAILURES as exc:
        return Config(), exc


def _collect_strings(value) -> list[str]:
    """Flatten nested tool-input values into a list of strings."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _collect_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _collect_strings(v)]
    return []


def _chunks(text: str) -> list[str]:
    """Split long text on line boundaries into pieces spaCy can handle."""
    if len(text) <= _CHUNK_CHARS:
        return [text]
    out: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > _CHUNK_CHARS:
            out.append(current)
            current = ""
        current += line
    if current:
        out.append(current)
    return out


def _read_file_text(tool_input: dict, cwd: str | None, config: Config) -> str | None:
    """Text Claude's Read tool will see, or None if there is nothing to scan."""
    raw_path = tool_input.get("file_path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    if not path.is_file():
        return None  # Read will fail on its own; nothing leaves the machine
    try:
        size = path.stat().st_size
        if size > config.hook_max_file_bytes:
            raise _ScanError(
                f"{path.name} is {size} bytes, over hook_max_file_bytes "
                f"({config.hook_max_file_bytes})"
            )
        data = path.read_bytes()
    except OSError as exc:
        raise _ScanError(f"cannot read {path.name}: {exc}") from exc
    if b"\x00" in data[:8192]:
        return None  # binary (image, PDF, ...) — not scanned as text
    text = data.decode("utf-8", errors="replace")
    offset, limit = tool_input.get("offset"), tool_input.get("limit")
    if isinstance(offset, int) or isinstance(limit, int):
        lines = text.splitlines(keepends=True)
        start = max((offset or 1) - 1, 0)
        end = start + limit if isinstance(limit, int) else None
        text = "".join(lines[start:end])
    return text


def _analyze(config: Config, event: dict, texts: list[str]) -> list[tuple[str, list[Detection]]]:
    """(chunk, detections) for every chunk of `texts`, via the daemon if it answers."""
    chunks = [c for text in texts if text and text.strip() for c in _chunks(text)]
    if not chunks:
        return []
    cwd = event.get("cwd") or None
    if config.hook_daemon != "off":
        found = daemon.detect(cwd, chunks)  # DaemonError: detection failed, fail closed
        if found is not None:
            return [(chunk, [Detection(*d) for d in dets])
                    for chunk, dets in zip(chunks, found, strict=True)]
        if config.hook_daemon == "auto":
            with contextlib.suppress(OSError):
                daemon.spawn(cwd)  # ready for the next call; this one runs here
    engine = ScrubEngine(config, regex_only=config.hook_fallback == "regex")
    engine.prime(chunks)
    return [(chunk, engine.detect(chunk)) for chunk in chunks]


# Code is not prose, and NER reads it badly: `npm` as an organisation, `customer.txt`
# as a place, `git log --oneline` or `useState` as a person. In code-like text a model
# detection must read as a name to count (see _reads_as_a_name).
# Tools whose every argument is code: shell commands, search patterns, globs.
_CODE_TOOLS = frozenset({"Bash", "bash", "powershell", "Grep", "grep", "rg", "glob"})
# Arguments that hold a file path or a search pattern, whatever the tool.
_PATH_KEYS = frozenset({"file_path", "path", "paths", "notebook_path", "glob", "pattern"})
# Files whose content is source code. Data and prose (.json, .csv, .yaml, .sql, .md, .txt,
# .html...) are left out on purpose: fixtures, seeds and documents are where names live.
_CODE_SUFFIXES = frozenset("""
    .py .pyi .js .jsx .mjs .cjs .ts .tsx .mts .cts .vue .svelte .astro .go .rs .java .kt .kts
    .scala .groovy .gradle .rb .php .cs .fs .swift .m .mm .c .h .cc .cpp .cxx .hpp .hh .sh
    .bash .zsh .fish .ps1 .psm1 .lua .pl .dart .ex .exs .erl .hs .clj .elm .zig .nim .jl
    .css .scss .sass .less .tf .hcl .toml .ini .cfg .lock
""".split())
_CODE_FILE_NAMES = frozenset({"Dockerfile", "Makefile", "Justfile", "Rakefile", "Gemfile",
                              "Procfile", "Containerfile", "CMakeLists.txt"})
# Entity types that only the language model finds. Pattern detections (e-mail, IBAN,
# phone, secrets, national ids...) are precise on command lines too and are never dropped.
_NER_TYPES = frozenset({"PERSON", "LOCATION", "ORGANIZATION", "NRP"})
_NAME_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*\.?")
_QUOTES = "\"'`"
_SPAN_EDGES = " \t\n\"'`()[]{}<>,;:="
_NAME_PARTICLES = frozenset({"de", "du", "des", "la", "le", "van", "von", "der", "den",
                             "di", "da", "del", "della", "of", "and", "et", "&",
                             "the", "a", "an"})
# Capitalised words that fill command descriptions, commit messages and code.
_TECH_WORDS = frozenset("""
    api aws azure bash build bun cargo ci cli css docker dockerfile eslint git github gitlab
    go gradle homebrew html http https java javascript jest json kubernetes linux macos make
    makefile markdown maven mysql nginx node npm pnpm postgres prettier pytest python react
    readme redis ruby ruff rust shell sql svelte terraform typescript ubuntu vite vue
    webpack windows yaml yarn zsh
    none null nil true false self this super props state string number boolean object array
    error exception class function return import export default const let var async await
    def lambda type interface enum struct impl fn void int float bool dict list tuple str
    bytes any path config settings button input form app main index utils service model
    view component test tests todo fixme
""".split())
# A word joined to a capitalised one inside a name ("McDonald", "LeBlanc", "DiCaprio").
_NAME_PREFIXES = ("Mc", "Mac", "De", "Di", "Da", "Du", "La", "Le", "Van", "Von", "O'", "D'")
# What may precede the first word of a line or sentence: indentation, comment and list
# markers, quotes, a full stop.
_OPENERS = " \t#*-+>/|:;.!?\"'`"


def _identifier(word: str) -> bool:
    """CamelCase like `UserService` or `setCount`, which a name is not ("McDonald" is)."""
    for prefix in _NAME_PREFIXES:
        if word.startswith(prefix) and len(word) > len(prefix):
            word = word[len(prefix):]
            break
    return any(a.islower() and b.isupper() for a, b in zip(word, word[1:], strict=False))


def _opens_a_sentence(text: str, start: int) -> bool:
    """Whether `start` is the first word of a line, a sentence or a quoted string."""
    line = text[:start].rsplit("\n", 1)[-1]
    if not line.strip(_OPENERS):
        return True
    before = line.rstrip()
    return before[-1] in _QUOTES or (before[-1] in ".!?" and line[-1:].isspace())


def _reads_as_a_name(text: str, start: int, end: int) -> bool:
    """Whether a model detection in code-like text looks like a name written by a person:
    whole words only (no path, flag, file name or operator), at least one of them
    capitalised like a name ("Jean", not "npm", "HEAD" or "UserService"), none a tool or
    keyword. The capital that opens a line or sentence ("Push branch", `-m "Fix login"`,
    `# Fails below`) does not count, unless the word stands alone (`grep "Dupont"`)."""
    span = text[start:end]
    start += len(span) - len(span.lstrip(_SPAN_EDGES))  # NER spans often take a quote along
    words = span.strip(_SPAN_EDGES).split()
    if not words or not all(_NAME_WORD.fullmatch(w) for w in words):
        return False
    core = [w for w in words if w.casefold() not in _NAME_PARTICLES]
    if not core or any(w.rstrip(".").casefold() in _TECH_WORDS or _identifier(w)
                       for w in core):
        return False
    after = text[start + len(words[0]):].lstrip(" \t")
    alone = after[:1] in ("", "\n", *_QUOTES)
    opens = _opens_a_sentence(text, start) and not alone
    named = core[1:] if opens and core[0] is words[0] else core
    return any(w[0].isupper() and not w.isupper() for w in named)


def _drop_code_noise(
    results: list[tuple[str, list[Detection]]],
) -> list[tuple[str, list[Detection]]]:
    """Model detections in code-like text that do not read as a name are dropped.

    A certain detection (score 1.0: a `deny` term or custom pattern labelled PERSON...)
    is the user's own rule and always stays."""
    return [(chunk, [d for d in dets if d.entity_type not in _NER_TYPES or d.score >= 1.0
                     or _reads_as_a_name(chunk, d.start, d.end)])
            for chunk, dets in results]


def _types(results: list[tuple[str, list[Detection]]]) -> Counter:
    return Counter(d.entity_type for _, dets in results for d in dets)


# Shown with every detection so a false positive costs one command to fix.
_FALSE_POSITIVE_HINT = (
    'False positive? `pii-airlock allow "<term>"` adds it to this project\'s policy.'
)


def _summary(found: Counter) -> str:
    return ", ".join(f"{t}×{n}" for t, n in found.most_common())


def _blocked(config: Config, found: Counter) -> Counter:
    """Entities whose `entity_actions` policy is `block`: never sent, never asked."""
    return Counter({t: n for t, n in found.items() if config.action_for(t) == "block"})


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


# Tools whose file content is what leaves the machine (Claude Code's Read, Copilot's view).
_FILE_READERS = frozenset({"Read", "read", "view"})


def _tool_texts(tool: str, tool_input: dict, event: dict, config: Config) -> list[str] | None:
    """Strings to scan for this tool call, or None if the tool is not covered.

    Claude Code's tools: the declared fields only (a file path is not content). MCP tools
    and Copilot's tools (bash, edit, create, view, web_fetch, ... all lower case, unlike
    Claude Code's): every argument, since their argument names are not ours to know. The
    same goes for a known tool whose arguments carry none of the declared fields. Other
    Claude Code tools (TodoWrite, Glob...) are not covered.
    """
    fields = _TOOL_FIELDS.get(tool)
    if fields is None and not (tool.startswith("mcp__") or tool == tool.lower()):
        return None
    if fields is None or not any(f in tool_input for f in fields):
        texts = _collect_strings(tool_input)
    else:
        texts = []
        for field in fields:
            texts.extend(_collect_strings(tool_input.get(field)))
    if tool in _FILE_READERS:
        path = tool_input.get("file_path") or tool_input.get("path")
        content = _read_file_text({**tool_input, "file_path": path}, event.get("cwd"), config)
        if content:
            texts.append(content)
    return texts


def _is_code_file(path) -> bool:
    if not isinstance(path, str) or not path:
        return False
    p = Path(path)
    return p.name in _CODE_FILE_NAMES or p.suffix.lower() in _CODE_SUFFIXES


def _code_texts(tool: str, tool_input: dict, texts: list[str]) -> list[bool]:
    """For each of `texts`, whether it is code (filtered) rather than prose (not)."""
    if tool in _CODE_TOOLS:
        return [True] * len(texts)
    if tool in ("NotebookEdit",) or _is_code_file(tool_input.get("file_path")
                                                   or tool_input.get("path")):
        return [True] * len(texts)  # content, old and new strings of a source file
    paths = {s for key in _PATH_KEYS for s in _collect_strings(tool_input.get(key))}
    return [text in paths for text in texts]


def _scan(config: Config, event: dict, texts: list[str], code: list[bool]):
    """_analyze, then the code-noise filter on the chunks that come from code."""
    results = _analyze(config, event, texts)
    flags = [c for text, c in zip(texts, code, strict=True)
             if text and text.strip() for _ in _chunks(text)]
    if not any(flags):
        return results
    return [_drop_code_noise([r])[0] if c else r
            for r, c in zip(results, flags, strict=True)]


def run_pre_tool_use() -> None:
    event = _read_event()
    config, config_error = _load_config(event)
    if not is_active(event.get("cwd"), config.activation):
        return  # project has not opted in (`pii-airlock init`)
    tool = event.get("tool_name", "") or ""
    tool_input = event.get("tool_input", {}) or {}
    decision = "deny" if config.hook_decision == "deny" else "ask"

    try:
        with _quiet():
            texts = _tool_texts(tool, tool_input, event, config)
            if texts is not None and config_error is not None:
                raise config_error
            if texts is None:
                return  # tool not covered; no decision -> allow
            found = _types(_scan(config, event, texts,
                                 _code_texts(tool, tool_input, texts)))
    except _FAILURES as exc:
        if config.hook_on_error == "open":
            return
        reason = f"pii-airlock could not check {tool} input for PII: {_error_text(exc)}"
    else:
        if not found:
            return
        reason = (
            f"pii-airlock: PII detected in {tool} input — {_summary(found)}. "
            f"Review before this leaves your machine. {_FALSE_POSITIVE_HINT}"
        )
        blocked = _blocked(config, found)
        if blocked:
            decision = "deny"
            reason = (f"pii-airlock: {tool} input blocked by policy (entity_actions) — "
                      f"{_summary(blocked)}. Use a placeholder instead.")
    # One reply for both harnesses: Claude Code reads the nested object and ignores the
    # top-level keys (checked against the claude CLI); Copilot reads the top-level ones.
    _emit(
        {
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        }
    )


def run_user_prompt_submit() -> None:
    event = _read_event()
    config, config_error = _load_config(event)
    if not is_active(event.get("cwd"), config.activation):
        return  # project has not opted in (`pii-airlock init`)
    prompt = event.get("prompt", "") or ""
    block = config.prompt_decision != "warn" or config.hook_decision == "deny"

    try:
        with _quiet():
            if config_error is not None:
                raise config_error
            results = _analyze(config, event, [prompt])
            found = _types(results)
            blocked = _blocked(config, found)
            scrubbed = None
            if len(results) == 1:  # long pastes are chunked: count only
                # Same tokens as the gateway would send, so the two can be mixed;
                # redacted and blocked entities become [ENTITY].
                hidden = {e for e, a in config.entity_actions.items() if a == "redact"}
                scrubbed = apply_detections(prompt, results[0][1], Mapping(token_key(config)),
                                            hidden | set(blocked))
    except _FAILURES as exc:
        if config.hook_on_error == "open":
            return
        _emit({
            "decision": "block",
            "reason": f"pii-airlock could not check your prompt for PII: {_error_text(exc)}",
        })
        return

    if not found:
        return
    summary = _summary(found)
    if block or blocked:
        reason = f"pii-airlock blocked your prompt: PII detected — {summary}."
        if blocked:
            reason = (f"pii-airlock blocked your prompt: {_summary(blocked)} is blocked by "
                      f"policy (entity_actions); also found: {summary}.")
        if scrubbed is not None:
            reason += f"\n\nScrubbed version you can send instead:\n\n{scrubbed}"
        reason += f"\n\n{_FALSE_POSITIVE_HINT}"
        if not blocked:
            reason += " Set `prompt_decision: warn` to send prompts with a warning instead."
        _emit({"decision": "block", "reason": reason})
        return
    _emit(
        {
            "systemMessage": f"⚠ pii-airlock: your prompt contains PII — {summary}. "
                             "It was sent unchanged.",
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    f"pii-airlock: the user's prompt contains PII ({summary}). "
                    "Do not repeat it unnecessarily."
                ),
            },
        }
    )


# Context Claude gets at session start in a guarded project (replaces a policy skill).
_SESSION_RULES = """\
This project is guarded by pii-airlock: prompts and tool calls are checked for personal \
data (names, emails, phones, IBANs, client names...) before they leave the machine.
- Do not copy personal data into commands, code, tests, docs or commit messages; use \
obvious placeholders (Jane Doe, jane@example.com).
- When a pii-airlock hook asks or blocks, do not work around it (no re-encoding, splitting \
or paraphrasing the value): tell the user what was flagged and let them decide.
- To work on a file with personal data, suggest `pii-airlock scrub FILE -o FILE.scrubbed`, \
work on the copy, then `pii-airlock restore`.
- Never read or print anything under .pii-airlock/maps/ (real values).
- Do not edit .pii-airlock/config.yaml or run `pii-airlock allow|deny|action|trust|off` \
unless the user asks."""


def run_session_start() -> None:
    event = _read_event()
    config, _ = _load_config(event)
    if not is_active(event.get("cwd"), config.activation):
        return
    root = find_project(event.get("cwd"))
    where = f" (policy: {root}/.pii-airlock/config.yaml)" if root else ""
    sys.stdout.write(_SESSION_RULES.replace("by pii-airlock:", f"by pii-airlock{where}:", 1) + "\n")
