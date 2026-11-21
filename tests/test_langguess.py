"""Findings of a model reading another language's text are trimmed to the names in them."""

from __future__ import annotations

import pytest

from pii_scrub import langguess

LANGS = ("en", "fr", "de", "it")


def _kept(text: str, span: str, lang: str) -> list[str]:
    start = text.index(span)
    return [text[s:e] for s, e in langguess.keep(text, start, start + len(span), lang, LANGS)]


def test_votes_count_words_only_one_language_uses():
    votes = langguess.votes("Merci de nous envoyer le contrat avant vendredi", LANGS)
    assert max(votes, key=votes.get) == "fr"
    votes = langguess.votes("Bitte senden Sie uns den Vertrag bis Freitag", LANGS)
    assert max(votes, key=votes.get) == "de"


@pytest.mark.parametrize("text, span", [
    ("Merci d'envoyer le contrat à Jean pour la signature.", "Merci d'envoyer le contrat à"),
    ("Le rapport trimestriel montre une croissance de douze pour cent.", "croissance de douze"),
    ("Nous verrons cela la semaine prochaine avec toute l'équipe.", "semaine prochaine"),
])
def test_ordinary_phrases_from_a_foreign_model_are_dropped(text, span):
    """Only a capitalized word may survive ("Merci" could start a name: recall first)."""
    assert all(k[0].isupper() and " " not in k for k in _kept(text, span, "en"))


@pytest.mark.parametrize("text, span, lang", [
    ("Die Zahlung wurde gestern von uns veranlasst.", "Die Zahlung", "en"),
    ("Rufen Sie uns bitte morgen an, wir sind den ganzen Tag im Büro.", "Rufen Sie", "fr"),
    ("Il pagamento è stato effettuato ieri da noi.", "Il", "fr"),
])
def test_capitalized_function_words_are_not_names(text, span, lang):
    assert "Sie" not in "".join(_kept(text, span, lang))
    assert not any(k in ("Die Zahlung", "Il") for k in _kept(text, span, lang))


def test_a_foreign_model_s_span_is_trimmed_to_its_names():
    text = "Réunion avec Ludwig van Dijk et Maria del Carmen Ruiz à Genève demain."
    span = "Ludwig van Dijk et Maria del Carmen Ruiz"
    assert _kept(text, span, "it") == ["Ludwig van Dijk", "Maria del Carmen Ruiz"]


def test_a_capitalized_function_word_mid_sentence_is_a_name():
    """Recall first: "Will" is a name here even though "will" is an English word."""
    text = "Can you ask Mark Will about the server migration before the end of the week?"
    assert _kept(text, "Mark Will", "fr") == ["Mark Will"]


@pytest.mark.parametrize("text, span", [
    ("Claire a confirmé le rendez-vous de jeudi avec nous.", "Claire"),
    ("Appelez Claire Favre au 079 123 45 67 pour confirmer le rendez-vous.",
     "Appelez Claire Favre"),
])
def test_names_survive_even_at_the_start_of_a_sentence(text, span):
    assert _kept(text, span, "en") == [span]


def test_the_model_of_the_text_s_language_is_not_filtered():
    text = "Merci d'envoyer le contrat à Jean pour la signature."
    span = "Merci d'envoyer le contrat à"
    assert _kept(text, span, "fr") == [span]


def test_too_little_text_to_tell_keeps_everything():
    assert _kept("ok merci", "ok merci", "en") == ["ok merci"]


def test_a_single_language_is_never_filtered():
    text = "Merci d'envoyer le contrat à Jean pour la signature."
    start = text.index("Merci")
    assert langguess.keep(text, start, start + 5, "en", ("en",)) == [(start, start + 5)]


def test_the_engine_trims_foreign_findings(monkeypatch):
    from pii_scrub.config import Config
    from pii_scrub.engine import ScrubEngine

    text = "Merci d'envoyer le contrat à Jean Dupont pour la signature demain."
    noise = (0, text.index(" Jean"))
    name = (text.index("Jean"), text.index(" pour"))
    by_lang = {"en": (("ORGANIZATION",) + noise + (0.85,), ("PERSON",) + name + (0.85,)),
               "fr": ()}
    engine = ScrubEngine(Config(languages=["en", "fr"],
                                models={"en": "en_x", "fr": "fr_x"}, builtin_recognizers=False))
    monkeypatch.setattr(engine, "_model_findings", lambda t, lang: by_lang[lang])

    found = {(d.entity_type, text[d.start:d.end]) for d in engine.detect(text)}

    assert ("PERSON", "Jean Dupont") in found
    assert not any(t == "ORGANIZATION" for t, _ in found)
