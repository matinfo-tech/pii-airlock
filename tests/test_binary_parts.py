"""Images, audio and files in gateway requests: the binary_parts policy."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from collections import Counter

import httpx
import pytest

pytest.importorskip("starlette")

from pii_scrub import binary  # noqa: E402
from pii_scrub.config import Config  # noqa: E402
from pii_scrub.payload import binary_parts, get_adapter  # noqa: E402


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 10 50 Td ({text}) Tj ET".encode()
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 100]/Contents 4 0 R"
            b"/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length %d>>stream\n%s\nendstream" % (len(stream), stream),
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offsets = b"%PDF-1.4\n", []
    for n, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, obj)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1, xref)


def _docx(text: str) -> bytes:
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 2
EMAIL = re.compile(r"[\w.]+@[\w.]+")


def _detect(texts):
    """Stand-in for the engine: e-mails only."""
    return Counter("EMAIL_ADDRESS" for t in texts for _ in EMAIL.finditer(t))


# --- binary.check ------------------------------------------------------------

def test_allow_forwards_everything():
    assert binary.check([(None, _b64(b"PK\x03\x04 zip"))], "allow", _detect) is None


def test_block_refuses_any_binary_part():
    msg = binary.check([("image/png", _b64(PNG))], "block", _detect)
    assert "binary_parts: block" in msg


def test_scan_forwards_images_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="pii_airlock.binary"):
        assert binary.check([("image/png", _b64(PNG)), (None, _b64(PNG))], "scan",
                            _detect) is None
    assert "2 image/audio part(s) unchecked" in caplog.text


@pytest.mark.parametrize("make,mime", [(_pdf, "application/pdf"), (_docx, binary._DOCX)],
                         ids=["pdf", "docx"])
def test_scan_refuses_a_document_with_pii(make, mime):
    pytest.importorskip("pdfminer")
    raw = make("Contact jean@acme.ch")
    for declared in (mime, None):  # declared, or recognised from its first bytes
        msg = binary.check([(declared, _b64(raw))], "scan", _detect)
        assert msg and "EMAIL_ADDRESS" in msg and "jean" not in msg


@pytest.mark.parametrize("make", [_pdf, _docx], ids=["pdf", "docx"])
def test_scan_forwards_a_clean_document(make):
    pytest.importorskip("pdfminer")
    assert binary.check([(None, _b64(make("Quarterly report")))], "scan", _detect) is None


def test_scan_refuses_files_it_cannot_read():
    msg = binary.check([("application/zip", _b64(b"PK\x03\x04 zip"))], "scan", _detect)
    assert "application/zip" in msg and "binary_parts: allow" in msg
    broken = binary.check([("application/pdf", _b64(b"%PDF-1.4 garbage"))], "scan", _detect)
    assert broken and "could not be" in broken


def test_scan_fails_closed_when_detection_fails():
    def broken(_texts):
        raise RuntimeError("spaCy model(s) not installed")

    pytest.importorskip("pdfminer")
    msg = binary.check([(None, _b64(_pdf("hello")))], "scan", broken)
    assert "could not be checked" in msg


# --- finding the parts -------------------------------------------------------

@pytest.mark.parametrize("provider,body,expected", [
    ("anthropic", {"messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": _b64(PNG)}},
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                        "data": "JVBERi0xLjQK" * 30}}]}]},
     ["image/png", "application/pdf"]),
    ("openai", {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(PNG)}"}},
        {"type": "input_audio", "input_audio": {"data": _b64(PNG), "format": "wav"}},
        {"type": "file", "file": {"file_data": f"data:application/pdf;base64,{_b64(PNG)}"}},
        {"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}]}]},
     ["image/jpeg", None, "application/pdf"]),
    ("gemini", {"contents": [{"parts": [
        {"inlineData": {"mimeType": "audio/mp3", "data": _b64(PNG)}},
        {"inlineData": {"mimeType": "text/plain", "data": _b64(b"plain text")}}]}]},
     ["audio/mp3"]),
], ids=["anthropic", "openai", "gemini"])
def test_binary_parts_are_found_in_every_provider_shape(provider, body, expected):
    assert [m for m, _ in binary_parts(body, get_adapter(provider))] == expected


# --- the gateway -------------------------------------------------------------

class _Engine:
    """Tokenizes nothing; detects e-mails (for the document check)."""

    def scrub_all(self, run, mapping, texts=None):
        return run(lambda t: t)

    def prime(self, texts):
        pass

    def detect(self, text):
        from pii_scrub.engine import Detection

        return [Detection("EMAIL_ADDRESS", m.start(), m.end(), 1.0)
                for m in EMAIL.finditer(text)]


def _gateway(mode: str):
    from starlette.testclient import TestClient

    from pii_scrub.proxy import build_app

    sent = []

    def upstream(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = build_app(config=Config(binary_parts=mode), engine=_Engine(), client=client,
                    upstreams={"anthropic": "https://api.example"})
    return TestClient(app), sent


def _message(*parts):
    return {"model": "m", "max_tokens": 5, "messages": [{"role": "user", "content": [
        {"type": "text", "text": "see attached"}, *parts]}]}


def _doc(raw: bytes) -> dict:
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": _b64(raw)}}


def test_gateway_refuses_a_pdf_with_pii_and_sends_nothing():
    pytest.importorskip("pdfminer")
    client, sent = _gateway("scan")
    resp = client.post("/anthropic/v1/messages", json=_message(_doc(_pdf("jean@acme.ch"))))
    assert resp.status_code == 403 and "EMAIL_ADDRESS" in resp.text
    assert sent == []


def test_gateway_forwards_screenshots_and_clean_documents():
    pytest.importorskip("pdfminer")
    client, sent = _gateway("scan")
    image = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": _b64(PNG)}}
    resp = client.post("/anthropic/v1/messages",
                       json=_message(image, _doc(_pdf("Quarterly report"))))
    assert resp.status_code == 200 and len(sent) == 1


def test_gateway_block_mode_refuses_screenshots():
    client, sent = _gateway("block")
    image = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": _b64(PNG)}}
    assert client.post("/anthropic/v1/messages", json=_message(image)).status_code == 403
    assert sent == []


def test_a_document_resent_every_turn_is_read_once(monkeypatch):
    pytest.importorskip("pdfminer")
    reads = []
    real = binary._document_texts
    monkeypatch.setattr(binary, "_document_texts",
                        lambda raw, mime: reads.append(1) or real(raw, mime))
    part = [(None, _b64(_pdf("Quarterly report, turn after turn")))]
    for _ in range(3):
        assert binary.check(part, "scan", _detect) is None
    assert len(reads) == 1
