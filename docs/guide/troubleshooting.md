# Troubleshooting

Start with the health check. It names the problem most of the time.

```bash
pii-airlock doctor
```

Find your symptom below.

## Installing

### `command not found: pii-airlock` (or `pipx`)

The folder holding pipx programs is not on your path yet.

```bash
pipx ensurepath
```

Close the terminal and open a new one.

### Names are no longer caught after an upgrade, or every tool call asks

Run `pii-airlock doctor`. If `model load` fails on Python 3.15, spaCy cannot run there yet:

```bash
pipx reinstall --python python3.14 pii-airlock
```

If `installed models` fails, run `pii-airlock download-models`.

### `No module named spacy`

You ran a Python command in the wrong environment. Run `pii-airlock download-models` instead, from the same terminal
you use for the rest.

### `OSError: [E050] Can't find model …` after downloading

The model went into a different environment than the one pii-airlock runs in. Run `pii-airlock download-models`: it
stores models where every pii-airlock install finds them.

### The gateway fails with `httpx`, `starlette` or `uvicorn` missing, or Word / PDF files are rejected

The installation is incomplete (these come with pii-airlock): `pipx reinstall pii-airlock`.

## Using the gateway

### My AI tool does not seem to use pii-airlock

- Is `pii-airlock proxy` still running in another terminal?
- Did you set the address **in the same terminal** you launched the tool from? Programs started from the Dock,
  Start menu or another window do not see it.
- Does the address end with the provider name (`/openai`, `/anthropic` or `/gemini`)?

### I get a 403 or 400 error

The gateway **refuses** requests it cannot clean safely: file uploads, audio, or a body that is not JSON.
Also, a type set to `block` triggers a 403 on purpose. The message names the type.

### The port is already in use

Another copy is probably running. Stop it, or choose another port: `pii-airlock proxy --port 8800`, and use that port in the address.

## Using hooks

### Everything is blocked after installing the Claude Code plugin

The plugin cannot find the `pii-airlock` command, and blocks everything by design. Install the program
([Install](/guide/install)), then restart Claude Code.

### It flags things that are not personal

Teach it: `pii-airlock allow "the word"`. See [Tell it what is sensitive](/customize/allow-and-deny).
You can also raise the confidence threshold for a type, for example `score_thresholds: {PERSON: 0.7}`
(see [Settings](/reference/settings#detection)).

### Hooks are slow

The first call loads the models, which takes seconds. Later calls take about 60 ms.
Check the helper with `pii-airlock daemon status`.

### Every tool call is checked twice

You installed the hooks twice, for example the plugin and `install-hook --scope user`, or a project-level
`install-hook` for Claude Code and one for Copilot in the same repository. `pii-airlock status` lists the hooks
it finds. Keep one.

### A project's settings seem ignored

If the project came from someone else, only settings that tighten protection apply until you run `pii-airlock trust`
after reviewing the files. `pii-airlock status` lists what is being ignored.

## Still stuck?

[Open a bug report](https://github.com/matinfo-tech/pii-airlock/issues/new/choose) with:

- the output of `pii-airlock --version`
- how you installed it (pipx, Homebrew or pip)
- the exact command and the full error message

Never paste real personal data into a bug report.
