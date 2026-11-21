# Quick start

About five minutes. Three steps that everyone does, then one step that depends on your tool.

::: info Before you begin
You need a **terminal**: Terminal on macOS, a shell on Linux, or PowerShell on Windows.
You also need **Python 3.10 or newer** and **pipx**. Not sure? Run the check below.
:::

## 1. Check your tools

```bash
python3 --version     # Windows: python --version
pipx --version
```

- Python shows `3.10` or higher: good.
- `pipx: command not found`: see [Install pipx](/guide/install#install-pipx).
- Python missing or too old: install it from [python.org](https://www.python.org/downloads/).

## 2. Install

```bash
pipx install pii-airlock
```

pipx puts pii-airlock in its own private space, so it never interferes with your other Python projects.
Prefer Homebrew or pip? See [Install](/guide/install) and [Install, advanced](/reference/install-advanced).

## 3. Guard your project

```bash
cd my-project
pii-airlock init
```

This creates a `.pii-airlock/` folder in the project, installs the hooks for Claude Code and
GitHub Copilot if you have them, and downloads the language models used to spot names (a few
minutes, once). You should end with:

```text
Done. `pii-airlock status` shows the setup; `pii-airlock off` pauses it here.
```

If a line says `[needs action]`, run what it says, then `pii-airlock init` again.

## 4. One last step, depending on your tool

- **Claude Code or GitHub Copilot? You are done.** In this project, prompts and tool calls with
  personal data are now stopped before they leave your computer. Run `pii-airlock init` in each
  project you want guarded. Details: [Claude Code](/use/claude-code) · [Copilot](/use/copilot).
- **Cursor, Codex, Aider, an SDK, or another AI app?** Continue with the
  [gateway quick start](/guide/quick-start-gateway) — two more minutes.
- **Just want to clean a file or some text?** [Clean a file or some text](/use/files-and-text).
- **Not sure?** [Pick your setup](/use/pick-your-setup).

## Try it with fake data

```bash
echo "Contact John Smith at john@example.com" | pii-airlock scrub
```

You should see placeholders instead of the name and email. More tests, including one for the hooks
and one for the gateway: [Check that it works](/guide/check-it-works).

## What now?

- [Tell it what is sensitive](/customize/allow-and-deny) in your own work.
- Read [Safety and limits](/guide/safety) once.
- Stuck? [Troubleshooting](/guide/troubleshooting).
