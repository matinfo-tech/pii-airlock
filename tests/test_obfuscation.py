"""Disguised PII: spans found on a cleaned view are mapped back to the original text."""

from __future__ import annotations

import base64
import re

import pytest

from pii_scrub import obfuscation

ZW = "​"


def _analyze(text):
    """Stand-in for the engine: plain e-mails and one IBAN, by regex."""
    found = [("EMAIL_ADDRESS", m.start(), m.end(), 1.0)
             for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)]
    found += [("IBAN_CODE", m.start(), m.end(), 1.0)
              for m in re.finditer(r"CH93 ?0076 ?2011 ?6238 ?5295 ?7", text, re.I)]
    return found


def _spans(text):
    return {(e, text[s:t]) for e, s, t, _ in obfuscation.find(text, _analyze)}


@pytest.mark.parametrize("text,disguised", [
    (f"mail jean.dupont{ZW}@acme.ch now", f"jean.dupont{ZW}@acme.ch"),
    ("mail jean dot dupont at acme dot ch now", "jean dot dupont at acme dot ch"),
    ("mail marie [at] acme-corp [dot] ch now", "marie [at] acme-corp [dot] ch"),
    ("mail sarah(at)example(dot)org now", "sarah(at)example(dot)org"),
    ("q=jean.dupont%40acme.ch&x=1", "jean.dupont%40acme.ch"),
    ('{"to": "jean\\u0040acme.ch"}', "jean\\u0040acme.ch"),
    ("mailto:sarah&#64;example.org", "sarah&#64;example.org"),
    ("ｊｅａｎ＠ａｃｍｅ．ｃｈ here", "ｊｅａｎ＠ａｃｍｅ．ｃｈ"),
    ("Email jеаn@acme.ch", "jеаn@acme.ch"),  # Cyrillic е and а
    ("j e a n @ a c m e . c h", "j e a n @ a c m e . c h"),
    ("at jean.dupont@\nacme.ch ok", "jean.dupont@\nacme.ch"),
])
def test_disguised_emails_are_found_on_the_original_span(text, disguised):
    assert ("EMAIL_ADDRESS", disguised) in _spans(text)


def test_invisible_characters_inside_an_iban():
    iban = f"CH93{ZW}0076{ZW}2011{ZW}6238{ZW}5295{ZW}7"
    assert ("IBAN_CODE", iban) in _spans(f"IBAN {iban} please")


def test_base64_run_hiding_an_email_is_flagged_whole():
    blob = base64.b64encode(b"jean.dupont@acme.ch").decode()
    assert ("EMAIL_ADDRESS", blob) in _spans(f"token={blob} in the log")


@pytest.mark.parametrize("text", [
    "Look at the docs at docs.example.com for more.",
    "We meet at noon, then dot the i's.",
    "The rate is at least 3 dot 5 percent.",
    "plain jean@acme.ch is found by the usual pass, not here",
    "sha 9dbe1c6e7669191954e2a4cb203754fe435fa943 and aGVsbG8gd29ybGQ=",
    f"data:image/png;base64,{base64.b64encode(bytes(range(256))).decode()}",
])
def test_nothing_disguised_nothing_found(text):
    assert _spans(text) == set()


def test_clean_text_does_not_call_the_analyzer_again():
    calls = []
    obfuscation.find("Nothing to see here, Jean.", lambda t: calls.append(t) or [])
    assert calls == []
