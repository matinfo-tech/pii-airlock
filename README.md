<div align="center">

<img src="https://raw.githubusercontent.com/matinfo-tech/pii-airlock/main/docs/public/logo.svg" alt="pii-airlock logo" width="96" height="96">

# pii-airlock

**Your prompts get the placeholders. You keep the secrets.**

A local privacy layer for AI tools: swaps personal data for placeholders before requests leave your machine, then restores the originals in the reply.

[![CI](https://github.com/matinfo-tech/pii-airlock/actions/workflows/ci.yml/badge.svg)](https://github.com/matinfo-tech/pii-airlock/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pii-airlock.svg)](https://pypi.org/project/pii-airlock/)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.14-blue.svg)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Works with **Claude Code · GitHub Copilot · Codex · Cursor · Aider · Gemini · any OpenAI-compatible client**

**[📖 User guide](https://pii-airlock.matinfo.tech/) · [Quickstart](#2-minute-quickstart) · [Pick your setup](#pick-your-setup) · [Help](https://pii-airlock.matinfo.tech/guide/troubleshooting)**

</div>

## Why

Everything you paste into an AI tool is sent to a third party. `pii-airlock` sits between you and the provider: it spots names, emails, phones, cards, IBANs and secrets, and sends placeholders instead. Answers come back with your real values restored.

```text
John Smith (john@acme.com) → <PERSON_482913> (<EMAIL_ADDRESS_093117>)
```

Detection runs 100% on your machine (macOS, Linux, Windows · Python ≥ 3.10), built on [Microsoft Presidio](https://microsoft.github.io/presidio/).

<p align="center">
  <img src="https://raw.githubusercontent.com/matinfo-tech/pii-airlock/main/docs/public/demo.gif"
       alt="Terminal demo: pii-airlock scrubs a name and an email from a prompt, then restores them in the reply"
       width="760">
</p>

## 2-minute quickstart

```bash
pipx install "pii-airlock[proxy]"   # or: brew install matinfo/tap/pii-airlock
cd my-project
pii-airlock init                    # guard this project
```

That's it. `init` creates `.pii-airlock/` in the project, installs the hooks for Claude Code and GitHub Copilot (once, for your user), and downloads the detection models. From now on, in this project only, prompts and tool calls that contain personal data are stopped before they leave your machine.

```bash
pii-airlock status              # what is guarded, by which hooks, with which policy
pii-airlock allow "Acme SA"     # never PII here (your company, products)
pii-airlock deny "Project X"    # always sensitive here (client, code name)
pii-airlock off                 # pause here (`pii-airlock on` resumes)
```

**Check it works:**

```bash
pii-airlock doctor              # one-command health check
echo "Contact John Smith at john@example.com" | pii-airlock scrub
# → Contact <PERSON_482913> at <EMAIL_ADDRESS_093117>
```

More install options (Homebrew details, pip, extras): **[Install guide](https://pii-airlock.matinfo.tech/guide/install)**.

## Pick your setup

| You use | Do this | Details |
|---|---|---|
| **Claude Code** | `pii-airlock init` — hooks block prompts and tool calls containing PII | [Claude Code guide](https://pii-airlock.matinfo.tech/use/claude-code) |
| **GitHub Copilot** | `pii-airlock init` — guards Copilot's tool calls | [Copilot guide](https://pii-airlock.matinfo.tech/use/copilot) |
| **Cursor, Codex, Aider, SDKs, any OpenAI-compatible client** | The gateway (below) | [Gateway guide](https://pii-airlock.matinfo.tech/use/gateway) |
| **A website chat you paste into** | `scrub` / `restore` (below) | [Clean a file or text](https://pii-airlock.matinfo.tech/use/files-and-text) |

### The gateway

Point your client at a local address; pii-airlock scrubs on the way out and restores on the way back:

```bash
pii-airlock proxy               # listens on http://127.0.0.1:8745
export OPENAI_BASE_URL=http://127.0.0.1:8745/openai         # OpenAI-compatible tools
export ANTHROPIC_BASE_URL=http://127.0.0.1:8745/anthropic   # Anthropic SDK
# Gemini: use base URL http://127.0.0.1:8745/gemini
```

Per-tool setup (Cursor, Continue, Aider, Gemini SDK…): **[Gateway guide](https://pii-airlock.matinfo.tech/use/gateway)**.

### Scrub files or text by hand

```bash
echo "Contacte Jean Dupont à jean@acme.fr" | pii-airlock scrub
# → Contacte <PERSON_558644> à <EMAIL_ADDRESS_094087>

# …send the scrubbed text to your LLM, then restore its answer:
echo "J'ai répondu à <PERSON_558644>." | pii-airlock restore
# → J'ai répondu à Jean Dupont.
```

Works on files too (text, CSV, JSON, Word, PDF): **[Clean a file or text](https://pii-airlock.matinfo.tech/use/files-and-text)**.

## Limits & safety — read this

- **Detection is best-effort, not a guarantee.** Statistical models miss things; review truly sensitive material. [Safety and limits](https://pii-airlock.matinfo.tech/guide/safety)
- **Mapping files hold the real values.** They are encrypted and git-ignored by default; never commit or share a plain `--map` file. [Data handling](https://pii-airlock.matinfo.tech/guide/safety#the-map-file-holds-the-real-data)
- **Hooks don't see tool output** (what `cat` prints back). Route traffic through the gateway for full coverage. [What hooks cannot see](https://pii-airlock.matinfo.tech/use/claude-code#what-hooks-cannot-see)

## Configure

Your rules live in `.pii-airlock/config.yaml`, shared with your team (only protection-tightening settings apply until a teammate runs `pii-airlock trust`). Allow/deny terms, per-type actions (`tokenize`, `redact`, `allow`, `block`), placeholder styles, languages and more:

- **[Tell it what is sensitive](https://pii-airlock.matinfo.tech/customize/allow-and-deny)** · **[Choose what happens](https://pii-airlock.matinfo.tech/customize/actions)** · **[Placeholders](https://pii-airlock.matinfo.tech/customize/placeholders)** · **[Languages](https://pii-airlock.matinfo.tech/customize/languages)**
- **[All settings](https://pii-airlock.matinfo.tech/reference/settings)** · **[What it detects](https://pii-airlock.matinfo.tech/reference/detected-types)** · **[All commands](https://pii-airlock.matinfo.tech/reference/commands)**

## Community

- ❓ **Need help?** [Troubleshooting](https://pii-airlock.matinfo.tech/guide/troubleshooting), or open a [bug report](https://github.com/matinfo-tech/pii-airlock/issues/new/choose) with `pii-airlock --version`, your install method, and the exact command + error (never real personal data).
- 🤝 **[Contributing](CONTRIBUTING.md)** — adding a language or a provider adapter is a great first PR
- 🔒 **[Security policy](SECURITY.md)** — responsible disclosure + the honest threat model
- 📜 **[Changelog](CHANGELOG.md)** · **[Code of Conduct](CODE_OF_CONDUCT.md)**

If pii-airlock helps you keep PII out of your AI tools, a ⭐ helps others find it.

## License

[MIT](LICENSE) © Matinfo
