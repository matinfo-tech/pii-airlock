"""Which configured language a stretch of text is written in, from its function words.

With several languages configured, every spaCy model reads every text (mixed EN/FR is
common, and one pass per guessed language would miss names in the other). But a model
reading a language it doesn't know tags ordinary phrases: the English model calls
"Merci d'envoyer le contrat à" an organization. This module lets the engine keep a
model's name, place or organization only where the words around it are in that model's
language, or where there is too little text to tell.

Function words that only one configured language uses ("the", "le", "der", "il") are
counted around each finding; no model, no download, microseconds per call.
"""

from __future__ import annotations

import importlib
import re
from functools import cache

_WORD = re.compile(r"[^\W\d_]+")
#: Characters read on each side of a finding (the finding itself is read too).
WINDOW = 120
#: Fewer marker words than this around a finding: too little to tell, keep it.
MIN_EVIDENCE = 2


@cache
def _stop_words(lang: str) -> frozenset[str]:
    try:
        module = importlib.import_module(f"spacy.lang.{lang}.stop_words")
    except ImportError:
        return frozenset()
    return frozenset(w.lower() for w in getattr(module, "STOP_WORDS", ()))


@cache
def _markers(langs: tuple[str, ...]) -> dict[str, frozenset[str]]:
    """Per language, its function words that no other configured language shares."""
    sets = {lang: _stop_words(lang) for lang in langs}
    return {lang: words.difference(*(sets[o] for o in langs if o != lang))
            for lang, words in sets.items()}


def votes(text: str, langs: tuple[str, ...]) -> dict[str, int]:
    """Marker-word count per language in `text`."""
    markers = _markers(langs)
    counts = dict.fromkeys(langs, 0)
    for word in _WORD.findall(text.lower()):
        for lang in langs:
            if word in markers[lang]:
                counts[lang] += 1
    return counts


# Lowercase words that belong inside names: "Jean de La Fontaine", "Ludwig van Beethoven".
_PARTICLES = frozenset({"de", "du", "des", "la", "le", "van", "von", "der", "den", "di", "da",
                        "del", "della", "dos", "y", "e", "bin", "al", "ter", "zu"})
# German writes its formal pronouns capitalized mid-sentence ("Rufen Sie bitte an").
_FORMAL = frozenset({"sie", "ihr", "ihnen", "ihre", "ihren", "ihrem", "ihrer", "ihres"})
_JOINER = re.compile(r"[ \t\-'’.]*")  # what may sit between two words of one name
_SENTENCE_END = ".!?:;\n\"«»()[]{}•*#>|-"


def _sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip(" \t")
    return not before or before[-1] in _SENTENCE_END


def _name_runs(text: str, start: int, end: int,
               function_words: frozenset[str]) -> list[tuple[int, int]]:
    """The parts of text[start:end] that read as proper names.

    Runs of capitalized words, with name particles inside them. Sentence-initial
    capitals prove nothing, so a function word there ("Die Zahlung", "Il") ends the run,
    as does German's formal "Sie"; elsewhere a capitalized "Will" is a name.
    """
    runs: list[tuple[int, int]] = []
    current: list[tuple[int, int, bool]] = []  # (start, end, is_particle)

    def close():
        while current and current[-1][2]:
            current.pop()  # a run ends on a name word, not on "de"
        if current:
            runs.append((current[0][0], current[-1][1]))
        current.clear()

    last = start
    for m in _WORD.finditer(text, start, end):
        if current and not _JOINER.fullmatch(text, last, m.start()):
            close()
        word, lower = m.group(0), m.group(0).lower()
        at_start = _sentence_start(text, m.start())
        if word[0].isupper() and not (
                lower in function_words and (at_start or lower in _FORMAL)):
            current.append((m.start(), m.end(), False))
        elif current and lower in _PARTICLES:
            current.append((m.start(), m.end(), True))
        else:
            close()
        last = m.end()
    close()
    return runs


def keep(text: str, start: int, end: int, lang: str,
         langs: tuple[str, ...]) -> list[tuple[int, int]]:
    """The parts of a `lang` model's finding at text[start:end] worth keeping.

    All of it when the words around it may be in `lang`, or there is too little text to
    tell. Otherwise only the parts that read as proper names: the model of the text's
    own language misses names that another model finds, and recall comes first.
    """
    if len(langs) < 2 or not _markers(langs).get(lang):
        return [(start, end)]  # one language, or one without a word list: no basis
    around = text[max(start - WINDOW, 0):end + WINDOW]  # its own "le", "à" count too
    counts = votes(around, langs)
    best = max(counts.values())
    if best < MIN_EVIDENCE or counts[lang] * 2 >= best:
        return [(start, end)]
    spoken = [other for other, n in counts.items() if n * 2 >= best]
    return _name_runs(text, start, end, frozenset().union(*map(_stop_words, spoken)))
