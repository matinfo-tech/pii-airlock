# Install

The recommended way is **pipx**, which gives pii-airlock its own private environment on any system.
Other methods (Homebrew, pip, the Claude Code plugin, development builds):
[Install, advanced](/reference/install-advanced).

## Install pipx

::: code-group
```bash [macOS]
brew install pipx
pipx ensurepath
```
```bash [Linux (Debian/Ubuntu)]
sudo apt install pipx
pipx ensurepath
```
```powershell [Windows]
py -m pip install --user pipx
py -m pipx ensurepath
```
:::

Close and reopen your terminal afterwards so the new command is found.

## Install pii-airlock

```bash
pipx install "pii-airlock[proxy]"
pii-airlock init
```

`[proxy]` adds the gateway. Without it, only the command-line tools and hooks work.
Added it later by mistake? `pipx inject pii-airlock 'pii-airlock[proxy]'`.

## Download the language models

pii-airlock needs language models to recognise names. They are not bundled.
`pii-airlock init` downloads them for you; to do it separately:

```bash
pii-airlock download-models
```

Run it once, from the same terminal setup you use for `pii-airlock`. English and French are the defaults.
To add other languages, see [Add a language](/customize/languages).

## Optional extras

Plain text, CSV and JSON work out of the box. Add more only if you need them:

```bash
pipx inject pii-airlock 'pii-airlock[docx]'    # Word .docx files
pipx inject pii-airlock 'pii-airlock[pdf]'     # PDF files (text extraction only)
pipx inject pii-airlock 'pii-airlock[all]'    # Word, PDF and gateway
pipx inject pii-airlock 'pii-airlock[gliner]' # one model for many languages (large)
```

## Update and uninstall

```bash
pipx upgrade pii-airlock        # update
pipx uninstall pii-airlock      # remove
```

## Next step

[Quick start](/guide/quick-start), or [check that it works](/guide/check-it-works).
