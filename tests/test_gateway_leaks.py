"""Gateway leak fuzz: a canary in every string of a request must reach the scrubber.

Each body below is a "kitchen sink" request for one provider API: every field
that can carry text, as documented by OpenAI, Anthropic and Google. A unique
canary is written into every string value, then the body goes through the
adapter with a transform that marks what it saw. A canary left untouched is a
field that would leave the machine without being checked.

Only the keys in ``payload.STRUCTURAL_KEYS`` (model, role, ids, signatures...) and
binary data are exempt, and each exemption is tested on its own below.
"""

from __future__ import annotations

import base64
import copy
import json
import re

import pytest

from pii_scrub import payload
from pii_scrub.payload import STRUCTURAL_KEYS, get_adapter, scrub_payload

_CANARY = re.compile(r"zq\d+zq")
_B64_PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4).decode()

OPENAI_CHAT = {
    "model": "gpt-5",
    "user": "end-user",
    "safety_identifier": "end-user",
    "prompt_cache_key": "key",
    "metadata": {"customer": "acme"},
    "stop": ["stop here"],
    "prediction": {"type": "content", "content": "predicted file content"},
    "response_format": {"type": "json_schema", "json_schema": {
        "name": "answer", "description": "schema description",
        "schema": {"type": "object", "properties": {"city": {
            "type": "string", "description": "field description", "enum": ["a value"]}}}}},
    "tools": [{"type": "function", "function": {
        "name": "lookup", "description": "tool description",
        "parameters": {"type": "object", "properties": {"q": {
            "type": "string", "description": "param description"}}}}}],
    "tool_choice": {"type": "function", "function": {"name": "lookup"}},
    "messages": [
        {"role": "developer", "content": "developer prompt"},
        {"role": "system", "content": [{"type": "text", "text": "system part"}]},
        {"role": "user", "name": "participant", "content": [
            {"type": "text", "text": "user text"},
            {"type": "image_url", "image_url": {"url": "https://example.com/a.png",
                                                "detail": "high"}},
            {"type": "file", "file": {"filename": "report.txt", "file_id": "file-1"}},
        ]},
        {"role": "assistant", "content": "assistant text", "refusal": "refusal text",
         "audio": {"id": "audio_1"},
         "tool_calls": [{"id": "call_1", "type": "function", "function": {
             "name": "lookup", "arguments": json.dumps({"q": "argument value"})}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "tool output"},
        {"role": "function", "name": "lookup", "content": "legacy function output"},
    ],
}

OPENAI_RESPONSES = {
    "model": "gpt-5",
    "instructions": "system instructions",
    "previous_response_id": "resp_1",
    "prompt": {"id": "pmpt_1", "version": "2", "variables": {"customer": "variable value"}},
    "text": {"format": {"type": "json_schema", "name": "out",
                        "schema": {"type": "object", "description": "schema text"}}},
    "metadata": {"ticket": "metadata value"},
    "tools": [
        {"type": "function", "name": "lookup", "description": "tool description",
         "parameters": {"type": "object", "properties": {"q": {"description": "param"}}}},
        {"type": "web_search", "user_location": {"type": "approximate", "city": "a city"}},
        {"type": "mcp", "server_label": "crm", "server_url": "https://mcp.example.com",
         "headers": {"X-Note": "header value"}},
    ],
    "input": [
        {"role": "user", "content": [
            {"type": "input_text", "text": "input text"},
            {"type": "input_image", "image_url": "https://example.com/a.png"},
            {"type": "input_file", "filename": "notes.txt", "file_id": "file-1"},
        ]},
        {"type": "message", "role": "assistant", "id": "msg_1",
         "content": [{"type": "output_text", "text": "output text", "annotations": [
             {"type": "url_citation", "title": "citation title", "url": "https://x.io"}]}]},
        {"type": "function_call", "call_id": "call_1", "name": "lookup",
         "arguments": json.dumps({"q": "argument value"})},
        {"type": "function_call_output", "call_id": "call_1", "output": "function output"},
        {"type": "custom_tool_call", "call_id": "call_2", "name": "patch", "input": "raw input"},
        {"type": "custom_tool_call_output", "call_id": "call_2", "output": "custom output"},
        {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque",
         "summary": [{"type": "summary_text", "text": "summary text"}]},
        {"type": "computer_call_output", "call_id": "call_3",
         "output": {"type": "input_image", "image_url": "https://example.com/s.png"}},
        {"type": "local_shell_call", "call_id": "call_4", "action": {
            "type": "exec", "command": ["cat", "a file"], "env": {"NAME": "env value"}}},
        {"type": "mcp_call", "id": "mcp_1", "server_label": "crm", "name": "find",
         "arguments": json.dumps({"who": "mcp argument"}), "output": "mcp output"},
    ],
}

OPENAI_LEGACY = {"model": "gpt-3.5-turbo-instruct", "prompt": ["first prompt", "second"],
                 "suffix": "suffix text", "stop": "stop text"}
OPENAI_EMBEDDINGS = {"model": "text-embedding-3-small", "input": ["embed me", "and me"]}

ANTHROPIC = {
    "model": "claude-sonnet-4-6",
    "metadata": {"user_id": "user id value"},
    "system": [{"type": "text", "text": "system text", "cache_control": {"type": "ephemeral"}}],
    "stop_sequences": ["stop text"],
    "tools": [
        {"name": "lookup", "description": "tool description", "input_schema": {
            "type": "object", "properties": {"q": {"type": "string",
                                                   "description": "param description"}}}},
        {"type": "web_search_20250305", "name": "web_search",
         "allowed_domains": ["example.com"],
         "user_location": {"type": "approximate", "city": "a city"}},
    ],
    "mcp_servers": [{"type": "url", "url": "https://mcp.example.com", "name": "crm",
                     "authorization_token": "secret"}],
    "messages": [
        {"role": "user", "content": "user text"},
        {"role": "user", "content": [
            {"type": "text", "text": "text block", "citations": [
                {"type": "char_location", "cited_text": "cited text",
                 "document_title": "document title"}]},
            {"type": "image", "source": {"type": "url", "url": "https://example.com/a.png"}},
            {"type": "document", "title": "doc title", "context": "doc context",
             "source": {"type": "text", "media_type": "text/plain", "data": "doc text"}},
            {"type": "document", "source": {"type": "content", "content": [
                {"type": "text", "text": "content doc text"}]}},
            {"type": "search_result", "source": "https://example.com", "title": "result title",
             "content": [{"type": "text", "text": "result text"}]},
        ]},
        {"role": "assistant", "content": [
            {"type": "text", "text": "assistant text"},
            {"type": "tool_use", "id": "toolu_1", "name": "lookup",
             "input": {"q": "tool input", "nested": ["deep value"]}},
            {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search",
             "input": {"query": "search query"}},
            {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
                {"type": "web_search_result", "title": "web title", "url": "https://x.io",
                 "encrypted_content": "opaque"}]},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": [
                {"type": "text", "text": "tool result text"}]},
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "tool result string",
             "is_error": True},
        ]},
    ],
}
ANTHROPIC_BATCH = {"requests": [{"custom_id": "req-1", "params": {
    "model": "claude-sonnet-4-6", "max_tokens": 10,
    "messages": [{"role": "user", "content": "batched text"}]}}]}
ANTHROPIC_LEGACY = {"model": "claude-2", "prompt": "\n\nHuman: legacy prompt\n\nAssistant:"}

GEMINI = {
    "systemInstruction": {"parts": [{"text": "system text"}]},
    "cachedContent": "cachedContents/abc",
    "tools": [{"functionDeclarations": [{"name": "lookup", "description": "tool description",
                                         "parameters": {"type": "OBJECT", "properties": {
                                             "q": {"type": "STRING",
                                                   "description": "param"}}}}]}],
    "generationConfig": {"stopSequences": ["stop text"],
                         "responseSchema": {"type": "OBJECT", "description": "schema"}},
    "contents": [
        {"role": "user", "parts": [
            {"text": "user text"},
            {"fileData": {"mimeType": "application/pdf", "fileUri": "gs://bucket/file.pdf"}},
        ]},
        {"role": "model", "parts": [
            {"text": "model text"},
            {"functionCall": {"name": "lookup", "args": {"q": "call arg", "n": ["deep"]}}},
            {"executableCode": {"language": "PYTHON", "code": "print('code text')"}},
            {"codeExecutionResult": {"outcome": "OUTCOME_OK", "output": "code output"}},
        ]},
        {"role": "user", "parts": [
            {"functionResponse": {"name": "lookup", "response": {"result": "fn result"}}},
        ]},
    ],
}
GEMINI_COUNT = {"generateContentRequest": {"model": "models/gemini-2.5-pro", "contents": [
    {"role": "user", "parts": [{"text": "count me"}]}]}}
GEMINI_EMBED = {"requests": [{"model": "models/text-embedding-004",
                              "content": {"parts": [{"text": "embed me"}]}, "title": "a title"}]}

CASES = [
    ("openai", OPENAI_CHAT), ("openai", OPENAI_RESPONSES), ("openai", OPENAI_LEGACY),
    ("openai", OPENAI_EMBEDDINGS), ("anthropic", ANTHROPIC), ("anthropic", ANTHROPIC_BATCH),
    ("anthropic", ANTHROPIC_LEGACY), ("gemini", GEMINI), ("gemini", GEMINI_COUNT),
    ("gemini", GEMINI_EMBED),
]
IDS = ["openai-chat", "openai-responses", "openai-legacy", "openai-embeddings", "anthropic",
       "anthropic-batch", "anthropic-legacy", "gemini", "gemini-count", "gemini-embed"]


def _plant(value, counter, path=""):
    """Write a unique canary into every string not under a structural key."""
    if isinstance(value, str):
        counter[0] += 1
        return f"{value} zq{counter[0]}zq", {path: f"zq{counter[0]}zq"}
    planted = {}
    if isinstance(value, list):
        out = []
        for i, v in enumerate(value):
            v, p = _plant(v, counter, f"{path}[{i}]")
            out.append(v)
            planted.update(p)
        return out, planted
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in STRUCTURAL_KEYS:
                out[k] = v
                continue
            v, p = _plant(v, counter, f"{path}.{k}")
            out[k] = v
            planted.update(p)
        return out, planted
    return value, planted


def _scan(text: str) -> str:
    return _CANARY.sub("SEEN", text)


@pytest.mark.parametrize("provider,body", CASES, ids=IDS)
def test_every_string_of_a_request_is_scrubbed(provider, body):
    planted_body, planted = _plant(copy.deepcopy(body), [0])
    out = json.dumps(scrub_payload(planted_body, get_adapter(provider), _scan))
    leaks = sorted(path for path, canary in planted.items() if canary in out)
    assert not leaks, f"{len(leaks)} of {len(planted)} fields not scrubbed: {leaks}"


@pytest.mark.parametrize("provider,body", CASES, ids=IDS)
def test_structure_survives_scrubbing(provider, body):
    """With nothing to scrub the body comes back identical (same shape, same values)."""
    assert scrub_payload(copy.deepcopy(body), get_adapter(provider), lambda s: s) == body


def test_structural_keys_are_left_alone():
    body = {"model": "zq1zq", "messages": [{"role": "zq2zq", "content": "hi zq3zq",
                                            "tool_calls": [{"id": "zq4zq", "function": {
                                                "name": "zq5zq", "arguments": "{}"}}]}]}
    out = json.dumps(scrub_payload(body, get_adapter("openai"), _scan))
    assert [c for c in ("zq1zq", "zq2zq", "zq4zq", "zq5zq") if c in out] == [
        "zq1zq", "zq2zq", "zq4zq", "zq5zq"]
    assert "zq3zq" not in out


def test_signed_thinking_blocks_are_never_modified():
    block = {"type": "thinking", "thinking": "Jean zq1zq", "signature": "sig"}
    body = {"messages": [{"role": "assistant", "content": [block]}]}
    out = scrub_payload(body, get_adapter("anthropic"), _scan)
    assert out["messages"][0]["content"][0] == block


@pytest.mark.parametrize("provider,part", [
    ("anthropic", {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                               "data": _B64_PNG}}),
    ("openai", {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_B64_PNG}"}}),
    ("openai", {"type": "input_audio", "input_audio": {"data": _B64_PNG, "format": "wav"}}),
    ("openai", {"type": "file", "file": {"filename": "a.pdf",
                                         "file_data": f"data:application/pdf;base64,{_B64_PNG}"}}),
], ids=["anthropic-image", "openai-image", "openai-audio", "openai-file"])
def test_binary_data_is_not_fed_to_the_scrubber(provider, part):
    seen: list[str] = []

    def scan(text):
        seen.append(text)
        return text

    scrub_payload({"messages": [{"role": "user", "content": [part]}]},
                  get_adapter(provider), scan)
    assert not any(_B64_PNG[:40] in s for s in seen)


@pytest.mark.parametrize("provider,body,path", [
    ("anthropic", {"messages": [{"role": "user", "content": [{"type": "document", "source": {
        "type": "base64", "media_type": "text/plain",
        "data": base64.b64encode(b"plain zq1zq").decode()}}]}]},
     lambda o: o["messages"][0]["content"][0]["source"]["data"]),
    ("gemini", {"contents": [{"parts": [{"inlineData": {
        "mimeType": "text/csv", "data": base64.b64encode(b"name\nzq1zq").decode()}}]}]},
     lambda o: o["contents"][0]["parts"][0]["inlineData"]["data"]),
    ("openai", {"messages": [{"role": "user", "content": [{"type": "file", "file": {
        "file_data": "data:text/plain;base64," + base64.b64encode(b"zq1zq").decode()}}]}]},
     lambda o: o["messages"][0]["content"][0]["file"]["file_data"].split(",", 1)[1]),
], ids=["anthropic-text-document", "gemini-inline-csv", "openai-text-file"])
def test_base64_text_files_are_decoded_scrubbed_and_reencoded(provider, body, path):
    out = scrub_payload(body, get_adapter(provider), _scan)
    assert "SEEN" in base64.b64decode(path(out)).decode()


def test_structural_key_list_is_short_and_explicit():
    # Every exemption is a hole by definition: keep the list reviewable.
    assert len(STRUCTURAL_KEYS) <= 30
    assert payload.STRUCTURAL_KEYS is STRUCTURAL_KEYS


class _Recorder:
    """A transform that records which strings were handed over as code-like."""

    def __init__(self):
        self.prose: list[str] = []
        self.code_texts: list[str] = []

    def __call__(self, text):
        self.prose.append(text)
        return text

    def code(self, text):
        self.code_texts.append(text)
        return text


def test_urls_definitions_and_commands_are_scrubbed_as_code():
    body = {
        "system": "You are a helpful assistant.",
        "tools": [{"name": "Bash", "description": "Executes a bash command",
                   "input_schema": {"properties": {"command": {"description": "The command"}}}}],
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Call Sarah Johnson"},
                {"type": "image", "source": {"type": "url", "url": "https://example.com/a.png"}},
            ]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash",
                 "input": {"command": "npm test"}}]},
        ],
    }
    rec = _Recorder()
    scrub_payload(body, get_adapter("anthropic"), rec)
    assert sorted(rec.code_texts) == ["Executes a bash command", "The command",
                                      "https://example.com/a.png", "npm test"]
    assert sorted(rec.prose) == ["Call Sarah Johnson", "You are a helpful assistant."]


def test_engine_keeps_urls_and_tool_text_but_still_catches_pii_there():
    from pii_scrub.config import Config
    from pii_scrub.engine import Detection, ScrubEngine
    from pii_scrub.mapping import Mapping

    class NoisyEngine(ScrubEngine):
        """Reads every capitalised word, and the URL, as a person; finds e-mails."""

        def detect(self, text, language=None, known=()):
            out = [Detection("PERSON", m.start(), m.end(), 0.85)
                   for m in re.finditer(r"\b[A-Z][a-z]+\b|https://\S+", text)]
            out += [Detection("EMAIL_ADDRESS", m.start(), m.end(), 1.0)
                    for m in re.finditer(r"\S+@\S+\.\w+", text)]
            return out

        def prime(self, texts, language=None):
            pass

    body = {"tools": [{"name": "mail", "description": "Sends mail, e.g. to ops@acme.io"}],
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "call Sarah"},
                {"type": "image", "source": {"type": "url", "url": "https://x.io/a.png"}}]}]}
    engine = NoisyEngine(Config(languages=["en"], models={"en": "en_core_web_sm"}))
    out = engine.scrub_all(lambda f: scrub_payload(body, get_adapter("anthropic"), f), Mapping())
    assert out["messages"][0]["content"][0]["text"] == "call <PERSON_1>"
    assert out["messages"][0]["content"][1]["source"]["url"] == "https://x.io/a.png"
    assert out["tools"][0]["description"] == "Sends mail, e.g. to <EMAIL_ADDRESS_1>"
