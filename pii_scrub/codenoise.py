"""Model detections in code-like text that do not read as a name.

Code is not prose, and NER reads it badly: `npm` as an organisation, `customer.txt` as a
place, `git log --oneline` or `useState` as a person. In code-like text (shell commands,
search patterns, paths, URLs, source files, tool definitions) a person, place or
organisation found by the language model must be written like a name to count.
Pattern detections (e-mail, phone, IBAN, ids, secrets) and the user's own `deny` terms
are never dropped. Used by the tool hook and the gateway.
"""

from __future__ import annotations

import re

from .engine import Detection

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


def keep(text: str, detection: Detection) -> bool:
    """Whether `detection` in code-like `text` still counts (see the module docstring).

    A certain detection (score 1.0: a `deny` term or custom pattern labelled PERSON...)
    is the user's own rule and always stays."""
    return (detection.entity_type not in _NER_TYPES or detection.score >= 1.0
            or _reads_as_a_name(text, detection.start, detection.end))


def filter_detections(text: str, detections: list[Detection]) -> list[Detection]:
    return [d for d in detections if keep(text, d)]
