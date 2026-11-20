# Quick start: the gateway

For Cursor, Codex, Aider, Continue, SDK scripts and any other tool that lets you set a "base URL".
Do the [common quick start](/guide/quick-start) first (install + `init`).

## 1. Start the gateway

```bash
pii-airlock proxy
```

Leave this terminal window open. The gateway listens on your computer only, at `http://127.0.0.1:8745`.
Nobody else on your network can reach it.

## 2. Point your AI tool at it

Open a **second** terminal and set the address for the tool you use. For OpenAI-style tools, including Codex:

::: code-group
```bash [macOS / Linux]
export OPENAI_BASE_URL=http://127.0.0.1:8745/openai
```
```powershell [Windows PowerShell]
$env:OPENAI_BASE_URL = "http://127.0.0.1:8745/openai"
```
:::

Then start your tool **from that same terminal**. The setting only applies to programs launched from it.

Anthropic SDK: `ANTHROPIC_BASE_URL=http://127.0.0.1:8745/anthropic`. Gemini: base URL `http://127.0.0.1:8745/gemini`.
Tool-specific instructions (Cursor, Continue, Aider, SDKs): [Other AI apps and SDKs](/use/gateway).

## 3. Try it with fake data

In your AI tool, send: `Write a short thank-you email to Jean Dupont, jean@example.com.`

The answer should show **Jean Dupont** and **jean@example.com** as you typed them. The provider's logs show
placeholders instead. If you do not have access to those logs, [Check that it works](/guide/check-it-works)
has a test that needs no provider.
