# AGENTS.md

Instructions for AI coding agents working **on this repository**. Looking to use pii-airlock with your own agent or
AI app? See the [user guide](https://pii-airlock.matinfo.tech/use/pick-your-setup).

## What this project is

`pii-airlock` is a local privacy layer for AI tools. It replaces personal data with placeholders before a request
leaves the machine and restores the originals in the reply. Python package `pii_scrub/`, CLI `pii-airlock`.

## Layout

| Path | Role |
|---|---|
| `pii_scrub/engine.py`, `recognizers.py`, `gliner_backend.py` | Detection (Presidio, spaCy, GLiNER, built-in checksum recognizers) |
| `pii_scrub/mapping*.py`, `token_key.py`, `surrogates.py` | Placeholders, mapping storage, encryption |
| `pii_scrub/payload.py`, `proxy.py` | Gateway and provider adapters (OpenAI, Anthropic, Gemini) |
| `pii_scrub/hooks/`, `hookinstall.py`, `daemon.py` | Claude Code and Copilot hooks, hook daemon |
| `pii_scrub/project.py`, `policy.py`, `trust.py`, `config*.py` | Project home `.pii-airlock/`, policy, trust, settings |
| `pii_scrub/cli.py` | CLI entry point |
| `plugins/pii-airlock/` | Claude Code plugin |
| `tests/` | Offline tests (Presidio and spaCy are stubbed); `tests/eval/` is the detection quality corpus |
| `docs/` | VitePress user guide (published at pii-airlock.matinfo.tech) |

## Commands

```bash
pip install -e ".[dev,all]"
ruff check .                         # lint, must pass
pytest -q                            # tests, offline, must pass
python -m tests.eval.run_eval -v     # detection quality (needs the small spaCy models)
cd docs && npm ci && npm run build   # build the docs site, must pass when docs change
```

## Rules

- **Privacy first.** Never log, print or commit real personal data, request bodies or mapping contents. Use fake data
  in tests and examples.
- **Fail closed.** If detection or a payload cannot be handled, deny or refuse. Do not silently forward.
- **Add a test** for every behaviour change. Detection changes also need a labeled case in `tests/eval/corpus.jsonl`.
- **Version bumps** touch `pyproject.toml`, `pii_scrub/__init__.py` and `plugins/pii-airlock/.claude-plugin/plugin.json`
  together (a test checks all three).
- **Docs.** User-facing change means updating `docs/` and the `[Unreleased]` section of `CHANGELOG.md`. Keep the
  README short: it points to the docs site for detail.
- Match the surrounding style: type hints, `from __future__ import annotations`, small focused modules.
- Conventional commit subjects (`feat:`, `fix:`, `docs:`), one logical change per commit.

## Adding a provider adapter

Implement a `PayloadAdapter` in `pii_scrub/payload.py`: `scrub_request` (where user text lives in the request) and
`restore_response` (where model text lives in the response). Register it and mirror the tests in
`tests/test_payload.py`.

See also [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
