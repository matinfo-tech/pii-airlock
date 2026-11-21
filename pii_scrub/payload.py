"""Provider-agnostic payload scrubbing.

The :class:`~pii_scrub.engine.ScrubEngine` and :class:`~pii_scrub.mapping.Mapping`
are provider-agnostic. The *only* provider-specific knowledge is **where the
user text lives in a request body, and where the model text lives in a response
body**. That knowledge is captured here as a :class:`PayloadAdapter`.

This mirrors the ``formats/`` design: a structural locator plus a ``str -> str``
transform. ``scrub_payload`` passes a scrubbing transform; ``restore_payload``
passes ``Mapping.restore``. One engine, many adapters.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from typing import Any

from .mapping import ANY_TOKEN_RE, Mapping

Transform = Callable[[str], str]


# --- shared helpers ------------------------------------------------------

#: Event = (SSE ``event:`` name or None, parsed ``data:`` JSON object)
Event = tuple[str | None, dict]

#: String fields that hold JSON text (tool-call arguments). Scrubbing parses
#: them so NER sees the values; restoring JSON-escapes the real values so the
#: argument string stays valid JSON.
_JSON_TEXT_KEYS = frozenset({"arguments", "partial_json"})

#: Free-text string fields of a content block / message / item.
_TEXT_KEYS = ("text", "title", "context", "refusal", "reasoning_content")

#: Anthropic blocks whose text is covered by a signature. Never scrubbed in
#: requests, so never restored in responses either (a restored value would be
#: sent back upstream in clear on the next turn).
_SIGNED_BLOCKS = frozenset({"thinking", "redacted_thinking"})

#: Request keys whose string values are never scrubbed: protocol structure the API
#: validates (model, role, type, ids, tool names), opaque blobs the provider signed or
#: encrypted, and credentials meant for the provider. Every other string is scrubbed.
STRUCTURAL_KEYS = frozenset({
    "model", "role", "type", "object", "name", "id", "tool_use_id", "tool_call_id",
    "call_id", "item_id", "previous_response_id", "file_id", "cachedContent",
    "media_type", "mime_type", "mimeType", "detail", "format", "language", "outcome",
    "signature", "encrypted_content", "authorization_token", "cache_control",
})


def _deep(value: Any, transform: Transform) -> Any:
    """Apply `transform` to every string value (not key) in a JSON tree."""
    if isinstance(value, str):
        return transform(value)
    if isinstance(value, list):
        return [_deep(v, transform) for v in value]
    if isinstance(value, dict):
        return {k: _deep(v, transform) for k, v in value.items()}
    return value


def _json_text(text: str, transform: Transform) -> str:
    """Transform the string values inside a JSON-encoded string."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return transform(text)
    return json.dumps(_deep(parsed, transform), ensure_ascii=False)


def _mapping_of(restore: Transform) -> Mapping | None:
    """The Mapping behind a ``mapping.restore`` transform (it also knows fakes)."""
    owner = getattr(restore, "__self__", None)
    return owner if isinstance(owner, Mapping) else None


def _json_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def json_escaped(restore: Transform) -> Transform:
    """Wrap a restore transform for text that is (a fragment of) JSON source.

    Restored values are inserted JSON-escaped, so a name containing a quote or
    backslash cannot break a tool-call ``arguments`` string.
    """
    mapping = _mapping_of(restore)
    if mapping is not None:
        return lambda text: mapping.restore(text, escape=_json_str)

    def _sub(match: re.Match) -> str:
        token = f"<{match.group(1)}>"
        value = restore(token)
        if value == token:
            return match.group(0)
        return _json_str(value)

    return lambda text: ANY_TOKEN_RE.sub(_sub, text)


def _restore_deep(value: Any, restore: Transform) -> Any:
    """Restore tokens anywhere in a response tree.

    Safe to apply everywhere: only strings matching a token minted for *this*
    request are replaced. Covers text, tool-call inputs, Responses ``output[]``
    and Gemini function calls without per-shape knowledge.
    """
    if isinstance(value, str):
        return restore(value)
    if isinstance(value, list):
        return [_restore_deep(v, restore) for v in value]
    if isinstance(value, dict):
        if value.get("type") in _SIGNED_BLOCKS:
            return value
        return {
            k: json_escaped(restore)(v) if k in _JSON_TEXT_KEYS and isinstance(v, str)
            else _restore_deep(v, restore)
            for k, v in value.items()
        }
    return value


#: Subtrees written by the developer, not the user: tool and schema definitions, config.
#: Scrubbed as code-like text (see codenoise): emails and names still count, while
#: "Executes a bash command" is not read as a person and a place.
_DEFINITION_KEYS = frozenset({"tools", "functions", "response_format", "tool_choice",
                              "generationConfig", "toolConfig", "text"})
#: Values that hold code or a command line.
_CODE_KEYS = frozenset({"command", "code", "cmd", "pattern", "path", "file_path", "glob"})
_URI = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://\S+|www\.\S+")
_DATA_URI = re.compile(r"data:([\w.+-]+/[\w.+-]+)?((?:;[\w-]+=[^;,]*)*);base64,", re.ASCII)
_BASE64 = re.compile(r"[A-Za-z0-9+/=\s_-]{256,}", re.ASCII)
#: Sibling keys that say what a ``data`` field holds.
_MIME_KEYS = ("media_type", "mime_type", "mimeType")


def _is_text_mime(mime: str | None) -> bool:
    mime = (mime or "").lower()
    return mime.startswith("text/") or mime in (
        "application/json", "application/xml", "application/csv", "application/x-ndjson",
        "application/yaml", "application/x-yaml", "application/sql")


def _base64_text(data: str, transform: Transform) -> str:
    """Decode base64 text, scrub it, encode it back. Undecodable data is left as is."""
    try:
        text = base64.b64decode(data, validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return data
    return base64.b64encode(transform(text).encode("utf-8")).decode("ascii")


def _code(transform: Transform) -> Transform:
    """The transform for code-like text, when the scrubber offers one (engine.scrub_all)."""
    return getattr(transform, "code", transform)


def _sweep_string(value: str, transform: Transform, mime: str | None = None,
                  code: bool = False) -> str:
    """Scrub one request string. Base64 payloads are binary unless their type is text."""
    uri = _DATA_URI.match(value)
    if uri:
        if _is_text_mime(uri.group(1)):
            return value[: uri.end()] + _base64_text(value[uri.end():], transform)
        return value  # an image, audio or document: see the binary-parts policy
    if mime is not None:
        return _base64_text(value, transform) if _is_text_mime(mime) else value
    if _BASE64.fullmatch(value) and " " not in value.strip():
        return value  # a bare base64 blob (audio, image) with no declared type
    if code or _URI.fullmatch(value.strip()):
        return _code(transform)(value)
    return transform(value)


def _sweep(value: Any, transform: Transform, code: bool = False) -> Any:
    """Scrub every string in a request body, except protocol structure.

    Deny by default: a field this module has never heard of is scrubbed too, so a new
    provider feature cannot leak by omission. Left alone, and covered by
    tests/test_gateway_leaks.py: the values of STRUCTURAL_KEYS, Anthropic's signed
    thinking blocks, and binary data (base64 images, audio, PDFs). Base64 *text*
    (a text/plain document, a CSV inline part) is decoded, scrubbed and re-encoded.
    JSON-encoded strings (tool-call ``arguments``) are parsed so NER sees the values.
    """
    if isinstance(value, str):
        return _sweep_string(value, transform, code=code)
    if isinstance(value, list):
        return [_sweep(v, transform, code) for v in value]
    if not isinstance(value, dict) or value.get("type") in _SIGNED_BLOCKS:
        return value
    mime = next((value[k] for k in _MIME_KEYS if isinstance(value.get(k), str)), None)
    # Anthropic's {"type": "text", "media_type": "text/plain", "data": ...} is plain text.
    base64_source = value.get("type") == "base64" or (mime is not None
                                                      and value.get("type") != "text")
    out = {}
    for key, v in value.items():
        if key in STRUCTURAL_KEYS:
            out[key] = v
        elif key in _JSON_TEXT_KEYS and isinstance(v, str):
            out[key] = _json_text(v, lambda t: _sweep_string(t, transform, code=code))
        elif key == "data" and isinstance(v, str) and base64_source:
            out[key] = _sweep_string(v, transform, mime or "application/octet-stream")
        else:
            nested = code or key in _CODE_KEYS or (key in _DEFINITION_KEYS
                                                   and isinstance(v, dict | list))
            out[key] = _sweep(v, transform, nested)
    return out


# --- streaming token reassembly ------------------------------------------


class StreamRestorer:
    """Restore tokens across a stream where a token may split between chunks.

    A placeholder like ``<PERSON_1>`` can arrive as ``<PERS`` then ``ON_1>``.
    Feeding fragments, this holds back any trailing partial-token prefix and
    only restores+emits text that cannot still be part of an unfinished token.
    Call :meth:`flush` once at end of the text channel to release any remainder.
    """

    # A trailing run that could still grow into a token, in any form
    # ANY_TOKEN_RE accepts: an opener (or its prefix) + token chars + a partial closer.
    _PARTIAL = re.compile(
        r"(?:(?:<|&lt;|\\<|\\u003[cC])[A-Z0-9_]*(?:&g?t?|\\(?:u0?0?3?)?)?"
        r"|&l?t?|\\(?:u0?0?3?)?)$"
    )

    def __init__(self, restore: Transform, mapping: Mapping | None = None) -> None:
        self._restore = restore
        # With surrogates, a fake ("Gaspard Castellan") can split too.
        self._mapping = mapping or _mapping_of(restore)
        self._buf = ""

    def feed(self, fragment: str) -> str:
        self._buf += fragment
        m = self._PARTIAL.search(self._buf)
        cut = m.start() if m else len(self._buf)
        if self._mapping is not None:
            cut = min(cut, len(self._buf) - self._mapping.hold_back(self._buf))
        safe, self._buf = self._buf[:cut], self._buf[cut:]
        return self._restore(safe)

    def flush(self) -> str:
        out = self._restore(self._buf)
        self._buf = ""
        return out


class StreamState:
    """Per-stream restore state: one :class:`StreamRestorer` per text channel.

    A channel is one independently streamed string — an OpenAI choice, a
    tool call's arguments, an Anthropic content block, a Responses output part.
    Keeping them separate stops ``n>1`` choices or parallel blocks from
    interleaving each other's held-back token prefixes.
    """

    def __init__(self, restore: Transform) -> None:
        self._restore = restore
        self._json_restore = json_escaped(restore)
        self._mapping = _mapping_of(restore)
        self._channels: dict[tuple, StreamRestorer] = {}

    def feed(self, key: tuple, fragment: str, *, json_text: bool = False) -> str:
        restorer = self._channels.get(key)
        if restorer is None:
            restorer = StreamRestorer(self._json_restore if json_text else self._restore,
                                      self._mapping)
            self._channels[key] = restorer
        return restorer.feed(fragment)

    def flush(self, key: tuple) -> str:
        restorer = self._channels.pop(key, None)
        return restorer.flush() if restorer else ""

    def open_keys(self, *prefix) -> list[tuple]:
        """Channels whose key starts with `prefix`, in creation order."""
        return [k for k in self._channels if k[: len(prefix)] == prefix]

    def restore(self, value: Any) -> Any:
        return _restore_deep(value, self._restore)


# --- adapters ------------------------------------------------------------


class PayloadAdapter:
    """Locate user/model text inside one provider's wire format."""

    #: registry key and CLI/proxy route name
    name: str = ""
    #: path fragments whose POST bodies carry user text (and are scrubbed)
    request_endpoints: tuple[str, ...] = ()

    def scrub_request(self, body: dict, transform: Transform) -> dict:
        """Return a copy of a request body with every user-controlled string transformed.

        The same for every provider (see _sweep): what differs between APIs is where
        model text sits in *responses*, which the methods below handle."""
        return _sweep(body, transform)

    def restore_response(self, body: Any, transform: Transform) -> Any:
        """Return a copy of a (non-streaming) response body with tokens restored."""
        return _restore_deep(body, transform)

    def restore_event(self, event: str | None, chunk: dict, state: StreamState) -> list[Event]:
        """Restore one streamed event. May return extra events (flushed tails)."""
        return [(event, state.restore(chunk))]

    def finish(self, state: StreamState) -> list[Event]:
        """Events releasing text still held back when the stream ends."""
        return []


class OpenAIAdapter(PayloadAdapter):
    """OpenAI Chat Completions, Responses, legacy Completions, Embeddings.

    Also Codex CLI, Cursor, Ollama, LiteLLM and other OpenAI-compatible tools.
    """

    name = "openai"
    request_endpoints = ("chat/completions", "completions", "responses",
                         "embeddings", "moderations")

    def restore_event(self, event, chunk, state):
        kind = chunk.get("type")
        if isinstance(kind, str) and kind.startswith("response."):
            return _responses_event(event, chunk, state)
        if not isinstance(chunk.get("choices"), list):
            return [(event, state.restore(chunk))]
        out = state.restore({k: v for k, v in chunk.items() if k != "choices"})
        out["choices"] = [_chat_choice(c, state) for c in chunk["choices"]]
        return [(event, out)]

    def finish(self, state):
        events: list[Event] = []
        for key in state.open_keys():
            tail = state.flush(key)
            if not tail:
                continue
            if key[0] == "c":
                events.append((None, {"choices": [
                    {"index": key[1], "delta": {"content": tail}, "finish_reason": None}]}))
            elif key[0] == "t":
                events.append((None, {"choices": [{"index": key[1], "finish_reason": None,
                    "delta": {"tool_calls": [{"index": key[2],
                                              "function": {"arguments": tail}}]}}]}))
            elif key[0] == "r":
                events.append(_responses_tail(None, key, tail, {}))
        return events


def _chat_choice(choice: Any, state: StreamState) -> Any:
    if not isinstance(choice, dict):
        return choice
    i = choice.get("index", 0)
    out = dict(choice)
    if isinstance(choice.get("text"), str):  # legacy completions stream
        out["text"] = state.feed(("c", i), choice["text"])
    delta = choice.get("delta")
    if isinstance(delta, dict):
        d = dict(delta)
        if isinstance(delta.get("content"), str):
            d["content"] = state.feed(("c", i), delta["content"])
        if isinstance(delta.get("tool_calls"), list):
            calls = []
            for tc in delta["tool_calls"]:
                fn = tc.get("function") if isinstance(tc, dict) else None
                if isinstance(fn, dict) and isinstance(fn.get("arguments"), str):
                    args = state.feed(("t", i, tc.get("index", 0)), fn["arguments"],
                                      json_text=True)
                    tc = {**tc, "function": {**fn, "arguments": args}}
                calls.append(tc)
            d["tool_calls"] = calls
        out["delta"] = d
    if choice.get("finish_reason"):
        _flush_chat_choice(out, i, state)
    return out


def _flush_chat_choice(choice: dict, i: int, state: StreamState) -> None:
    """Append held-back tails to the choice's final chunk, before it closes."""
    tail = state.flush(("c", i))
    if tail:
        if "delta" in choice:
            choice["delta"] = {**choice["delta"],
                               "content": (choice["delta"].get("content") or "") + tail}
        else:
            choice["text"] = (choice.get("text") or "") + tail
    for key in state.open_keys("t", i):
        tail = state.flush(key)
        if not tail:
            continue
        delta = choice.setdefault("delta", {})
        calls = list(delta.get("tool_calls") or [])
        for n, tc in enumerate(calls):
            if isinstance(tc, dict) and tc.get("index", 0) == key[2]:
                fn = tc.get("function") or {}
                calls[n] = {**tc, "function": {**fn,
                                               "arguments": (fn.get("arguments") or "") + tail}}
                break
        else:
            calls.append({"index": key[2], "function": {"arguments": tail}})
        choice["delta"] = {**delta, "tool_calls": calls}


_RESPONSES_INDEX_KEYS = ("output_index", "content_index", "summary_index")


def _responses_key(kind: str, chunk: dict) -> tuple:
    return ("r", kind, *(chunk.get(k) for k in _RESPONSES_INDEX_KEYS))


def _responses_tail(event: str | None, key: tuple, tail: str, ref: dict) -> Event:
    kind = f"{key[1]}.delta"
    chunk = {"type": kind}
    for k, v in zip(_RESPONSES_INDEX_KEYS, key[2:], strict=True):
        if v is not None:
            chunk[k] = v
    if "item_id" in ref:
        chunk["item_id"] = ref["item_id"]
    chunk["delta"] = tail
    return (kind if event else None, chunk)


def _responses_event(event: str | None, chunk: dict, state: StreamState) -> list[Event]:
    """OpenAI Responses API stream: ``*.delta`` fragments, closed by ``*.done``."""
    kind = chunk["type"]
    if kind.endswith(".delta") and isinstance(chunk.get("delta"), str):
        base = kind[: -len(".delta")]
        key = _responses_key(base, chunk)
        delta = state.feed(key, chunk["delta"], json_text="arguments" in base)
        return [(event, {**chunk, "delta": delta})]
    events: list[Event] = []
    if kind.endswith(".done"):
        key = _responses_key(kind[: -len(".done")], chunk)
        tail = state.flush(key)
        if tail:
            events.append(_responses_tail(event, key, tail, chunk))
    events.append((event, state.restore(chunk)))
    return events


class AnthropicAdapter(PayloadAdapter):
    """Anthropic Messages API (incl. count_tokens and message batches)."""

    name = "anthropic"
    request_endpoints = ("messages", "complete")

    def restore_event(self, event, chunk, state):
        kind = chunk.get("type")
        idx = chunk.get("index", 0)
        delta = chunk.get("delta")
        if kind == "content_block_delta" and isinstance(delta, dict):
            dtype = delta.get("type")
            if dtype in ("thinking_delta", "signature_delta"):
                return [(event, chunk)]
            for field in ("text", "partial_json"):
                if isinstance(delta.get(field), str):
                    text = state.feed(("b", idx, dtype, field), delta[field],
                                      json_text=field == "partial_json")
                    return [(event, {**chunk, "delta": {**delta, field: text}})]
        if kind == "content_block_stop":
            # Release the block's held-back tail *inside* the block, before it closes.
            tails = [self._tail(event, key, state) for key in state.open_keys("b", idx)]
            return [t for t in tails if t] + [(event, chunk)]
        return [(event, state.restore(chunk))]

    def finish(self, state):
        return [t for t in (self._tail("content_block_delta", k, state)
                           for k in state.open_keys()) if t]

    @staticmethod
    def _tail(event: str | None, key: tuple, state: StreamState) -> Event | None:
        _, idx, dtype, field = key
        tail = state.flush(key)
        if not tail:
            return None
        chunk = {"type": "content_block_delta", "index": idx,
                 "delta": {"type": dtype, field: tail}}
        return ("content_block_delta" if event else None, chunk)


class GeminiAdapter(PayloadAdapter):
    """Google Gemini generateContent / streamGenerateContent / countTokens / embeddings."""

    name = "gemini"
    request_endpoints = ("generateContent", "streamGenerateContent", "countTokens",
                         "embedContent", "batchEmbedContents")

    def restore_event(self, event, chunk, state):
        if not isinstance(chunk.get("candidates"), list):
            return [(event, state.restore(chunk))]
        out = state.restore({k: v for k, v in chunk.items() if k != "candidates"})
        out["candidates"] = [_gemini_candidate(n, c, state)
                             for n, c in enumerate(chunk["candidates"])]
        return [(event, out)]

    def finish(self, state):
        events: list[Event] = []
        for key in state.open_keys():
            tail = state.flush(key)
            if tail:
                part = {"text": tail, **({"thought": True} if key[2] else {})}
                events.append((None, {"candidates": [
                    {"index": key[1], "content": {"role": "model", "parts": [part]}}]}))
        return events


def _gemini_candidate(n: int, cand: Any, state: StreamState) -> Any:
    if not isinstance(cand, dict):
        return cand
    idx = cand.get("index", n)
    out = state.restore({k: v for k, v in cand.items() if k != "content"})
    content = cand.get("content")
    if isinstance(content, dict) and isinstance(content.get("parts"), list):
        parts = []
        for p in content["parts"]:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                key = ("g", idx, bool(p.get("thought")))
                p = {**p, "text": state.feed(key, p["text"])}
            else:
                p = state.restore(p)
            parts.append(p)
        if cand.get("finishReason"):
            for key in state.open_keys("g", idx):
                tail = state.flush(key)
                if tail:
                    parts.append({"text": tail, **({"thought": True} if key[2] else {})})
        out["content"] = {**content, "parts": parts}
    elif content is not None:
        out["content"] = state.restore(content)
    return out


_ADAPTERS: dict[str, PayloadAdapter] = {
    a.name: a for a in (OpenAIAdapter(), AnthropicAdapter(), GeminiAdapter())
}


def get_adapter(name: str) -> PayloadAdapter:
    try:
        return _ADAPTERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider '{name}'. Known: {', '.join(sorted(_ADAPTERS))}."
        ) from None


def adapter_names() -> list[str]:
    return sorted(_ADAPTERS)


# --- top-level scrub / restore over a parsed body ------------------------


def scrub_payload(body: dict, adapter: PayloadAdapter, scrub: Transform) -> dict:
    """Scrub user text in a request `body`. `scrub` is `text -> tokenized text`."""
    return adapter.scrub_request(body, scrub)


def restore_payload(body: dict, adapter: PayloadAdapter, restore: Transform) -> dict:
    """Restore model text in a non-streaming response `body`."""
    return adapter.restore_response(body, restore)


# --- SSE helpers (used by the proxy) -------------------------------------


def split_sse_event(raw: str) -> tuple[str | None, str | None]:
    """Parse a single SSE event block into (event_name, data_string).

    Returns (None, None) when there is no ``data:`` line (comment/keep-alive).
    """
    event = None
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif line.startswith("event:"):
            event = line[6:].strip()
    if not data_lines:
        return event, None
    return event, "\n".join(data_lines)


def format_sse(events: list[Event]) -> str:
    """Serialize events as SSE blocks, each terminated by a blank line."""
    out = []
    for name, chunk in events:
        prefix = f"event: {name}\n" if name else ""
        out.append(f"{prefix}data: {json.dumps(chunk, ensure_ascii=False)}\n\n")
    return "".join(out)


def restore_sse_event(raw: str, adapter: PayloadAdapter, state: StreamState) -> str:
    """Rewrite one raw SSE event block (without its trailing blank line).

    Returns one or more SSE blocks. ``[DONE]`` first releases any held-back text.
    Comments, keep-alives and non-JSON data pass through unchanged.
    """
    event, data = split_sse_event(raw)
    if data is None:
        return raw + "\n\n"
    if data.strip() == "[DONE]":
        return format_sse(adapter.finish(state)) + raw + "\n\n"
    try:
        chunk = json.loads(data)
    except ValueError:
        return raw + "\n\n"
    if not isinstance(chunk, dict):
        return raw + "\n\n"
    return format_sse(adapter.restore_event(event, chunk, state))
