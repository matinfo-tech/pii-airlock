# Other AI apps and SDKs

The **gateway** is a small server on your own computer. You tell your AI tool to talk to it instead of the
provider. It hides personal data on the way out and restores it on the way back.

```text
your app  ──▶  pii-airlock gateway  ──▶  AI provider
          ◀──  (restores originals) ◀──  (sees placeholders only)
```

## 1. Start it

```bash
pii-airlock proxy
```

Keep that terminal open. It listens at `http://127.0.0.1:8745` and only your own computer can reach it.

Seeing `missing httpx / starlette / uvicorn`? You installed without the gateway part.
Run `pipx reinstall pii-airlock`.

## 2. Point your tool at it

Each provider has its own address under the gateway.

| Provider | Address |
|---|---|
| OpenAI and OpenAI-compatible | `http://127.0.0.1:8745/openai` |
| Anthropic (Claude) | `http://127.0.0.1:8745/anthropic` |
| Google Gemini | `http://127.0.0.1:8745/gemini` |

### Set it once per terminal

::: code-group
```bash [macOS / Linux (bash, zsh)]
export OPENAI_BASE_URL=http://127.0.0.1:8745/openai
```
```fish [fish]
set -x OPENAI_BASE_URL http://127.0.0.1:8745/openai
```
```powershell [Windows PowerShell]
$env:OPENAI_BASE_URL = "http://127.0.0.1:8745/openai"
```
```bat [Windows cmd.exe]
set OPENAI_BASE_URL=http://127.0.0.1:8745/openai
```
:::

Start your tool from **that same terminal window**. The setting does not reach programs started elsewhere.
To keep it permanently, add the line to your shell profile.

## Tool by tool

### Codex CLI, OpenAI SDK, LiteLLM, vLLM, Ollama front-ends

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8745/openai
```

### Anthropic SDK and tools built on it

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8745/anthropic
```

### Cursor

Open **Settings → Models**, turn on **Override OpenAI Base URL** and enter `http://127.0.0.1:8745/openai`.
Use a model that Cursor can reach through an OpenAI-compatible endpoint.

### Continue (VS Code and JetBrains)

In `~/.continue/config.json`, add `apiBase` to the model:

```json
{
  "models": [
    { "title": "via pii-airlock", "provider": "openai",
      "model": "gpt-4o", "apiBase": "http://127.0.0.1:8745/openai" }
  ]
}
```

### Aider

```bash
export OPENAI_API_BASE=http://127.0.0.1:8745/openai
aider
```

### Google Gemini (Python SDK)

```python
from google import genai
from google.genai.types import HttpOptions

client = genai.Client(
    api_key="...",
    http_options=HttpOptions(base_url="http://127.0.0.1:8745/gemini"),
)
```

## Is it safe to point my app at plain `http`?

Yes here, because the traffic never leaves your computer. Your app talks to `localhost`.
The gateway then makes the real, encrypted `https` call to the provider. There are no certificates to install,
and your API key is passed through without being stored or logged.

## What happens to unknown requests

If the gateway does not know how to clean a request, it **refuses** rather than sending it on.
That covers file uploads, audio and other unfamiliar endpoints. You will see an error such as 403 or 400.
This is the safe default. If you are sure a path never carries personal data, list it under `passthrough_paths`
in [Settings](/reference/settings).

## What is not cleaned

- **Every piece of text in a request is cleaned**, in any field, including ones the gateway has never seen
  before: messages, system prompts, tool results and arguments, tool and schema descriptions, metadata,
  `user`, stop sequences, citations, prompt variables, code-execution parts. A new provider feature
  cannot slip past by being unknown.
- Text files sent inline as base64 (a `text/plain` document, a CSV part) are decoded, cleaned and re-encoded.
- Not cleaned: protocol fields the provider checks (model, role, type, ids, tool names, signatures), and
  credentials meant for the provider (an MCP server's `authorization_token`).
- Images, audio and files inside a request are never altered (they cannot be rewritten safely). What happens
  depends on `binary_parts` (see below).
- Anthropic `thinking` blocks are signed, so they are neither cleaned nor restored.

### Images, audio and attached files

| Attached | `binary_parts: scan` (default) | `block` | `allow` |
|---|---|---|---|
| PDF or Word document | Its text is checked. With personal data: **refused** (403). Clean: sent. | refused | sent |
| Image, audio, video | **Sent unchecked**, with a warning in the gateway log | refused | sent |
| Any other file (zip, spreadsheet...) | **refused**: its content cannot be checked | refused | sent |

A refused document stays in the conversation, and coding agents resend the whole conversation on every turn: remove
it, or start a new conversation, then send its cleaned text instead (`pii-airlock scrub report.pdf`). Screenshots
are not read: if they may show personal data, set `binary_parts: block`.

URLs, commands and tool definitions are checked like [code](/use/claude-code#shell-commands-and-code): an email or
a name in them is cleaned, but `https://example.com/logo.png` or "Executes a bash command" is not mistaken for one.

## How the gateway works (details)

**What it covers.** Three wire formats, one adapter each (`pii_scrub/payload.py`):

| Route | Wire format | Covers | Streaming |
|---|---|---|---|
| `/openai` | Chat Completions, Responses, Completions, Embeddings, Moderations | OpenAI, Codex, Cursor, Continue, Ollama, LiteLLM, vLLM, … | SSE ✅ |
| `/anthropic` | Messages (including `count_tokens` and batches) | Claude SDKs and Claude-compatible tools | SSE ✅ |
| `/gemini` | generateContent, countTokens, embedContent | Google Gemini | SSE ✅ · array streaming is buffered |

Gemini streaming without `alt=sse` is buffered and restored as one response instead of streamed live.
Pass `alt=sse` if your client supports it.

**Tool traffic.** Tool results and function outputs (where file contents and command output live) and
tool-call arguments are cleaned on the way out. Tool-call arguments the model writes are restored on the way back.
This is what makes the gateway cover the tool output that [hooks cannot see](/use/claude-code#what-hooks-cannot-see).

**Privacy properties.**

- No TLS interception: your client speaks plain HTTP to `localhost`, and the gateway makes the real HTTPS call.
  It listens on `127.0.0.1` by default.
- Authentication headers pass through untouched. Request headers and bodies are never logged
  (the server runs at log level `warning`, so not even request lines are logged).
- Each request gets a fresh mapping **in memory**. The gateway writes no personal data to disk.
  The only thing it stores is the [token key](/customize/placeholders).
- Detection is serialized with a lock, so simultaneous requests share the engine safely.

**Refusals fail closed.** A body the gateway cannot clean (unknown endpoint, or not JSON) is refused with 403 or 400.
Opt specific paths out with `passthrough_paths` only if you know they carry no personal data.

## Setup for coding agents

| Tool | What to do |
|---|---|
| Codex CLI, OpenAI SDKs, LiteLLM (`api_base=`), vLLM and Ollama front-ends | `OPENAI_BASE_URL` as above. Chat Completions **and** the Responses API (used by Codex) are covered, including function-call arguments and outputs. |
| Claude Code | Use [hooks](/use/claude-code). You can add the gateway too, for tool output. |
| GitHub Copilot | See [GitHub Copilot](/use/copilot). |

## Add a provider

A provider is one small adapter in `pii_scrub/payload.py`. Requests need no code: every string is cleaned
except `STRUCTURAL_KEYS`. Implement `restore_response` and `restore_event` (where model text lives in
responses and streams), register it, and add a request body to `tests/test_gateway_leaks.py`. See
[CONTRIBUTING](https://github.com/matinfo-tech/pii-airlock/blob/main/CONTRIBUTING.md).

## Check it

Send a message containing a fake name and email. Your tool should show them normally.
The provider's dashboard or logs should show a placeholder such as `<EMAIL_ADDRESS_093117>` instead of the real value.
See [Check that it works](/guide/check-it-works).
