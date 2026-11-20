# Install, advanced

The simple path is on [Install](/guide/install). This page covers the other methods and the details.

| Method | Good if | Optional extras (Word, PDF, GLiNER) |
|---|---|---|
| **pipx** (recommended) | Any system, most predictable | `pipx inject`, kept across upgrades |
| **Homebrew** | You are on macOS or Linux and prefer `brew` | Possible, but reset on each upgrade |
| **pip** | You manage your own Python environments | `pip install` |
| **Claude Code plugin** | You only use Claude Code | Needs the program installed first |

## Homebrew (macOS and Linux)

```bash
brew install matinfo/tap/pii-airlock
pii-airlock download-models
```

Homebrew installs the command, the hooks and the gateway into a **private virtualenv**: an isolated
folder of Python packages that belongs to pii-airlock alone. You never activate it. The `pii-airlock`
command already points into it.

Find it with:

```bash
brew --prefix pii-airlock
```

The virtualenv is the `libexec` folder inside that path.

To add Word support, PDF support or GLiNER, use that virtualenv's own `pip`:

```bash
"$(brew --prefix pii-airlock)/libexec/bin/python" -m pip install 'pii-airlock[docx]'
```

::: warning Upgrades reset the virtualenv
`brew upgrade pii-airlock` and `brew reinstall pii-airlock` rebuild it. Afterwards, run the extras
command again and `pii-airlock download-models`. If that gets tiresome, use pipx.
:::

Update and remove: `brew upgrade pii-airlock` and `brew uninstall pii-airlock`.

## pip

Do this inside a virtual environment you created, not in your system Python.

```bash
python3 -m venv ~/pii-airlock-env
source ~/pii-airlock-env/bin/activate      # Windows: ~/pii-airlock-env/Scripts/activate
pip install "pii-airlock[proxy]"
```

You must activate that environment every time before using `pii-airlock`.

## Claude Code plugin

Inside Claude Code:

```text
/plugin marketplace add matinfo-tech/pii-airlock
/plugin install pii-airlock@pii-airlock
```

This registers the hooks and adds a `/pii-airlock:setup` helper. It does **not** install the program
itself, so use pipx or Homebrew first. See [Claude Code](/use/claude-code).

## Install the newest unreleased version

```bash
pipx install git+https://github.com/matinfo-tech/pii-airlock
```

## Supported platforms

Tested in CI on **Linux, macOS and Windows**: Python 3.10 to 3.14 on Linux, 3.12 and 3.13 on macOS and Windows.
Python 3.10 or newer is required.

## If `download-models` says your environment has no pip

Normal with pipx. The command prints the exact `pipx inject pii-airlock "<model-wheel-url>"` lines to run instead.
