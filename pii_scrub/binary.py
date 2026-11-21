"""What the gateway does with images, audio and files inside a request.

Text can be rewritten; a PDF or a picture cannot, safely. So binary parts are
never altered: under ``binary_parts: scan`` (the default) documents whose text can
be extracted (PDF, Word) are scanned, and the request is refused if they hold
personal data; images, audio and video are forwarded with a warning (they cannot
be read without OCR or speech recognition); any other file is refused, since what
it holds is unknown. ``block`` refuses every binary part, ``allow`` forwards them all.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from collections import Counter, OrderedDict
from collections.abc import Callable

log = logging.getLogger("pii_airlock.binary")

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MEDIA = ("image/", "audio/", "video/")
_MAGIC = (
    (b"%PDF", "application/pdf"),
    (b"\x89PNG", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF8", "image/gif"),
    (b"RIFF", "audio/wav"), (b"ID3", "audio/mpeg"), (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
)

#: texts -> entity type counts (the engine with the project's policy)
Detect = Callable[[list[str]], Counter]

# Agents resend the whole conversation on every turn, attachments included: remember
# each document's verdict (entity counts only, never its text) by content digest.
_VERDICTS: OrderedDict[tuple[bytes, int], Counter] = OrderedDict()
_MAX_VERDICTS = 64


def _verdict(raw: bytes, mime: str, detect: Detect) -> Counter:
    key = (hashlib.blake2b(raw, digest_size=16).digest(), id(detect))
    if key in _VERDICTS:
        _VERDICTS.move_to_end(key)
        return _VERDICTS[key]
    found = detect(_document_texts(raw, mime))
    _VERDICTS[key] = found
    while len(_VERDICTS) > _MAX_VERDICTS:
        _VERDICTS.popitem(last=False)
    return found


def sniff(raw: bytes) -> str | None:
    """The MIME type a file's first bytes give away, if any."""
    for magic, mime in _MAGIC:
        if raw.startswith(magic):
            if mime == "audio/wav" and raw[8:12] == b"WEBP":
                return "image/webp"
            return mime
    if raw.startswith(b"PK\x03\x04") and b"word/" in raw[:4096]:
        return _DOCX
    if raw[4:12] in (b"ftypmp42", b"ftypisom", b"ftypM4A "):
        return "video/mp4"
    return None


def _decode(data: str) -> bytes | None:
    try:
        return base64.b64decode(data + "=" * (-len(data) % 4), validate=False)
    except (binascii.Error, ValueError):
        return None


def _document_texts(raw: bytes, mime: str) -> list[str]:
    from .engine import collect_texts
    from .formats.docx import DocxHandler
    from .formats.pdf import PdfHandler

    handler = PdfHandler(raw) if mime == "application/pdf" else DocxHandler(raw)
    return collect_texts(lambda grab: handler.scrub(grab, lambda _e, v: v))


def check(parts: list[tuple[str | None, str]], mode: str, detect: Detect) -> str | None:
    """A refusal message for the request's binary parts, or None to forward it.

    Never includes the data or any value found in it: only types and counts.
    """
    if mode == "allow" or not parts:
        return None
    if mode == "block":
        return (f"pii-airlock: request not sent — it carries {len(parts)} image, audio or "
                "file part(s) and `binary_parts: block` is set. Remove them, or set "
                "`binary_parts: scan`.")
    found: Counter = Counter()
    media = 0
    for declared, data in parts:
        raw = _decode(data) or b""
        mime = (declared or "").lower() or sniff(raw) or "application/octet-stream"
        if mime.startswith(_MEDIA):
            media += 1
            continue
        if mime not in ("application/pdf", _DOCX):
            return (f"pii-airlock: request not sent — it carries a `{mime}` file that "
                    "cannot be checked for personal data. Send its text instead, or set "
                    "`binary_parts: allow`.")
        try:
            found += _verdict(raw, mime, detect)
        except RuntimeError as exc:  # MissingExtra, or a model that will not load
            return (f"pii-airlock: request not sent — a {mime.split('/')[-1].upper()} "
                    f"document could not be checked: {exc}")
        except Exception as exc:  # a broken file: never forward what was not read
            return (f"pii-airlock: request not sent — a {mime.split('/')[-1].upper()} "
                    f"document could not be read ({type(exc).__name__}).")
    if found:
        kinds = ", ".join(f"{t}×{n}" for t, n in sorted(found.items()))
        return (f"pii-airlock: request not sent — an attached document contains personal "
                f"data ({kinds}). Documents cannot be rewritten safely: remove it, or "
                "scrub its text with `pii-airlock scrub` and send that instead.")
    if media:
        log.warning("pii-airlock: forwarded %d image/audio part(s) unchecked "
                    "(binary_parts: scan cannot read pictures or sound)", media)
    return None
