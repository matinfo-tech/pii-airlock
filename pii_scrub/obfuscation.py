"""Find PII that is written to slip past pattern matching.

``jean.dupont[at]acme[dot]ch``, an IBAN with zero-width spaces in it, a phone number in
fullwidth digits, ``jean%40acme.ch``, ``sarah&#64;example.org``, ``j e a n @ a c m e . c h``
or a base64-encoded e-mail all read as PII to a person (and to a model) but not to a
regex. This module builds a cleaned-up view of the text that remembers where every
character came from, runs detection on the parts that changed, and maps what it finds
back onto the original text, so the original span is what gets tokenized.

Only text that actually contains such a disguise costs anything: clean text is
scanned once by a few cheap regexes and left alone.
"""

from __future__ import annotations

import base64
import binascii
import html
import re
import unicodedata
from collections.abc import Callable

#: (entity_type, start, end, score) on the original text.
Finding = tuple[str, int, int, float]
#: Detection over a piece of clean text -> findings on that piece.
Analyze = Callable[[str], list[Finding]]

# Latin look-alikes from Cyrillic and Greek: NFKC leaves them as they are.
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
    "ј": "j", "ѕ": "s", "һ": "h", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ӏ": "l",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ј": "J", "Ѕ": "S",
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "τ": "t", "ι": "i", "κ": "k",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
})
# Escapes that stand for one character: %40, &#64; &#x40; &commat; @ \x40.
_ESCAPE = re.compile(
    r"(?:%[0-9A-Fa-f]{2})+|&#\d{1,7};|&#[xX][0-9A-Fa-f]{1,6};|&[A-Za-z]{2,8};"
    r"|\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2}")
# Single characters separated by single spaces: "j e a n @ a c m e . c h".
_SPACED = re.compile(r"(?<!\S)(?:\S ){4,}\S(?!\S)")
# An e-mail written with words or brackets for "@" and ".", or broken by spaces.
_AT = r"(?:\s*[\[({<]\s*at\s*[\])}>]\s*|\s+at\s+|\s*@\s*)"
_DOT = r"(?:\s*[\[({<]\s*dot\s*[\])}>]\s*|\s+dot\s+|\.)"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9_%+-]*[A-Za-z0-9])?"
_EMAIL = re.compile(
    rf"(?<![\w.@-]){_LABEL}(?:{_DOT}{_LABEL})*{_AT}{_LABEL}(?:{_DOT}{_LABEL})*{_DOT}"
    rf"[A-Za-z]{{2,24}}(?![\w@-])(?!{_AT}{_LABEL})",  # "me at jean dot ..." is not one
    re.IGNORECASE,
)
_PLAIN_EMAIL = re.compile(r"[\w.%+-]+@[\w-]+(?:\.[\w-]+)+")
# A base64 run long enough to hide an e-mail or an IBAN.
_BASE64 = re.compile(r"(?<![\w+/-])[A-Za-z0-9+/_-]{16,}={0,2}(?![\w+/=-])")
_WINDOW = 80


class _View:
    """A rewritten copy of a text, with each character's span in the original."""

    def __init__(self, text: str) -> None:
        self.source = text
        self.chars: list[str] = []
        self.spans: list[tuple[int, int]] = []

    def add(self, chars: str, start: int, end: int) -> None:
        for c in chars:
            self.chars.append(c)
            self.spans.append((start, end))

    @property
    def text(self) -> str:
        return "".join(self.chars)

    def original(self, start: int, end: int) -> tuple[int, int]:
        return self.spans[start][0], self.spans[end - 1][1]

    def rewrite(self, pattern: re.Pattern, replace: Callable[[re.Match], str]) -> _View:
        """A new view with every match of `pattern` replaced, spans kept."""
        out, text, pos = _View(self.source), self.text, 0
        for m in pattern.finditer(text):
            for i in range(pos, m.start()):
                out.add(self.chars[i], *self.spans[i])
            if m.end() > m.start():
                out.add(replace(m), *self.original(m.start(), m.end()))
            pos = m.end()
        for i in range(pos, len(self.chars)):
            out.add(self.chars[i], *self.spans[i])
        return out


def _unescape(m: re.Match) -> str:
    s = m.group(0)
    if s.startswith("%"):
        try:
            return bytes.fromhex(s.replace("%", "")).decode("utf-8")
        except UnicodeDecodeError:
            return s
    if s.startswith(("\\u", "\\x")):
        return chr(int(s[2:], 16))
    return html.unescape(s)


def _clean(text: str) -> _View:
    """Drop invisible characters, fold look-alikes and decode escapes."""
    view = _View(text)
    for i, c in enumerate(text):
        if unicodedata.category(c) == "Cf":  # zero-width space, joiner, BOM...
            continue
        folded = unicodedata.normalize("NFKC", c).translate(_CONFUSABLES)
        view.add(folded, i, i + 1)
    view = view.rewrite(_ESCAPE, _unescape)
    return view.rewrite(_SPACED, lambda m: m.group(0).replace(" ", ""))


_WORD_AT = re.compile(r"\s+at\s+", re.IGNORECASE)
_SPELLED_DOT = re.compile(r"\bdot\b", re.IGNORECASE)


def _email_text(m: re.Match) -> str:
    s = m.group(0)
    if _WORD_AT.search(s) and "@" not in s and not _SPELLED_DOT.search(s):
        return s  # "the docs at docs.example.com" is prose, "jean at acme dot ch" is not
    s = re.sub(_AT, "@", s, count=1, flags=re.IGNORECASE)
    return re.sub(_DOT, ".", s, flags=re.IGNORECASE).replace(" ", "")


def _windows(changed: list[int], size: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for i in changed:
        start, end = max(i - _WINDOW, 0), min(i + _WINDOW, size)
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _printable(text: str) -> bool:
    return bool(text) and sum(c.isprintable() or c in "\n\t" for c in text) >= 0.95 * len(text)


def _base64_findings(text: str, analyze: Analyze) -> list[Finding]:
    found: list[Finding] = []
    for m in _BASE64.finditer(text):
        run = m.group(0)
        try:
            raw = base64.b64decode(run + "=" * (-len(run) % 4),
                                   altchars=b"-_" if "-" in run or "_" in run else None)
            decoded = raw.decode("utf-8")
        except (binascii.Error, ValueError):
            continue
        if not _printable(decoded) or len(decoded) < 6:
            continue
        hits = analyze(decoded)
        if hits:
            found.append((hits[0][0], m.start(), m.end(), max(h[3] for h in hits)))
    return found


def find(text: str, analyze: Analyze) -> list[Finding]:
    """Findings for PII disguised in `text`, as spans of `text`.

    `analyze` runs the usual detection on a clean piece of text (without calling this
    function again). Findings that the usual detection on `text` itself would make are
    returned too where they overlap; the engine collapses duplicates.
    """
    found: list[Finding] = []
    view = _clean(text)
    email_view = view.rewrite(_EMAIL, _email_text)
    for m in _PLAIN_EMAIL.finditer(email_view.text):
        start, end = email_view.original(m.start(), m.end())
        if text[start:end] != m.group(0):  # only disguised ones: plain ones are found anyway
            found.append(("EMAIL_ADDRESS", start, end, 1.0))
    clean = view.text
    if clean != text:
        changed = [i for i, (c, (s, e)) in enumerate(zip(view.chars, view.spans, strict=True))
                   if e - s != 1 or text[s] != c
                   or (i and view.spans[i - 1][1] != s)]  # an invisible character was dropped
        marks = set(changed)
        for w_start, w_end in _windows(changed, len(clean)):
            for entity, s, e, score in analyze(clean[w_start:w_end]):
                if not marks.intersection(range(w_start + s, w_start + e)):
                    continue  # nothing disguised in it: the plain pass already decided
                start, end = view.original(w_start + s, w_start + e)
                found.append((entity, start, end, score))
    found.extend(_base64_findings(text, analyze))
    return found
