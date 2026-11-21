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
pipx install pii-airlock
pii-airlock init
```

This installs everything: the command-line tools, the hooks, the gateway, and Word and PDF support.

::: warning Python 3.15
spaCy, which pii-airlock uses to spot names, does not run on Python 3.15 yet. If `pii-airlock doctor`
reports `model load` as failed on Python 3.15, reinstall on 3.14:
`pipx reinstall --python python3.14 pii-airlock`. Your downloaded models are kept.
:::

## Download the language models

pii-airlock needs language models to recognise names. They are not bundled.
`pii-airlock init` downloads them for you; to do it separately:

```bash
pii-airlock download-models
```

Run it once. English and French are the defaults. To add other languages, see
[Add a language](/customize/languages).

The models are stored in `~/.local/share/pii-airlock/models`, outside pipx's environment, so
upgrading or reinstalling pii-airlock keeps them. When an upgrade brings a spaCy version that needs
newer models, `pii-airlock doctor` says so and `download-models` fetches them.

## Optional: GLiNER

One model for many languages instead of one spaCy model per language. It is large (it pulls PyTorch):

```bash
pipx inject pii-airlock 'pii-airlock[gliner]'
```

## Update and uninstall

```bash
pipx upgrade pii-airlock        # update, then check with: pii-airlock doctor
pipx uninstall pii-airlock      # remove
rm -rf ~/.local/share/pii-airlock   # the downloaded models too
```

## Next step

[Quick start](/guide/quick-start), or [check that it works](/guide/check-it-works).
