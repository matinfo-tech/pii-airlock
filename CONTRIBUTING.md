# Contributing to pii-airlock

Thanks for helping make PII safer for AI workflows. Contributions of all kinds
are welcome: bug reports, docs, new language configs, and new provider adapters.

## Quick start

```bash
git clone https://github.com/matinfo-tech/pii-airlock
cd pii-airlock
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev,all]"
```

## Before you open a PR

```bash
ruff check .        # lint (also: ruff format .)
pytest -q           # unit + integration tests, fully offline
```

Both must pass.

If your virtualenv breaks with `.venv/bin/pytest: bad interpreter` (it points at
an old folder), recreate it:

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e '.[dev]'
``` CI runs them on Linux (Python 3.10–3.14) and on macOS + Windows.

- Releases: bump the version in `pyproject.toml`, `pii_scrub/__init__.py` **and**
  `plugins/pii-airlock/.claude-plugin/plugin.json` (a test checks all three).
- Detection changes: run `python -m tests.eval.run_eval -v` (needs `en_core_web_sm`,
  `fr_core_news_sm`, `de_core_news_sm` and `it_core_news_sm`) and add a labeled case to `tests/eval/corpus.jsonl`; CI gates on it.
  A weekly job also gates the GLiNER backend (`--backend gliner`, needs `pii-airlock[gliner]`).
- Tests stub Presidio/spaCy, so they need no model download and no network.
- Keep new code lint-clean and add tests for new behavior.
- Match the surrounding style (type hints, `from __future__ import annotations`,
  small focused modules).

## Good first contributions

- **Add a language.** spaCy ships models for many languages — see
  [Add a language](https://pii-airlock.matinfo.tech/customize/languages) in the
  user guide. A docs PR listing a working `{lang: model}` pair is useful.
- **Add a provider adapter.** Implement a `PayloadAdapter` in
  `pii_scrub/payload.py`. Requests need no code: every string is scrubbed except
  `STRUCTURAL_KEYS`. Write where model text lives in responses and streams
  (`restore_response`, `restore_event`), and add a kitchen-sink request body to
  `tests/test_gateway_leaks.py` plus tests in `tests/test_payload.py`.
- **Custom recognizers** to improve detection (e.g. locale-specific phone/ID
  formats) via Presidio's recognizer registry.

## Commit & PR conventions

- Conventional-commit style subjects are appreciated (`feat:`, `fix:`, `docs:`…).
- Describe the user-facing change and how you verified it.
- One logical change per PR where practical.

## Reporting bugs / security

- Bugs: open an issue using the template.
- Security vulnerabilities: **do not** open a public issue — see
  [SECURITY.md](SECURITY.md).

By contributing you agree your contributions are licensed under the project's
[MIT License](LICENSE).
