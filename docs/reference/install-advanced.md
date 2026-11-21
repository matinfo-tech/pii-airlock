# Install, advanced

The simple path is on [Install](/guide/install). This page covers the other methods and the details.

| Method | Good if | GLiNER (optional) |
|---|---|---|
| **pipx** (recommended) | Any system, most predictable | `pipx inject`, kept across upgrades |
| **Homebrew** | You are on macOS or Linux and prefer `brew` | Possible, but reset on each upgrade |
| **pip** | You manage your own Python environments | `pip install` |
| **Claude Code plugin** | You only use Claude Code | Needs the program installed first |

## Homebrew (macOS and Linux)

```bash
brew install matinfo-tech/tap/pii-airlock
pii-airlock download-models
```

The tap moved from `matinfo/tap` to `matinfo-tech/tap`. An existing `matinfo/tap` install keeps
updating: GitHub redirects the old address.

Homebrew installs the command, the hooks and the gateway into a **private virtualenv**: an isolated
folder of Python packages that belongs to pii-airlock alone. You never activate it. The `pii-airlock`
command already points into it.

Find it with:

```bash
brew --prefix pii-airlock
```

The virtualenv is the `libexec` folder inside that path.

To add GLiNER, use that virtualenv's own `pip`:

```bash
"$(brew --prefix pii-airlock)/libexec/bin/python" -m pip install 'pii-airlock[gliner]'
```

::: warning Upgrades reset the virtualenv
`brew upgrade pii-airlock` and `brew reinstall pii-airlock` rebuild it: run the GLiNER command again
afterwards. Models from `pii-airlock download-models` are stored outside it and are kept.
:::

Update and remove: `brew upgrade pii-airlock` and `brew uninstall pii-airlock`.

## pip

Do this inside a virtual environment you created, not in your system Python.

```bash
python3 -m venv ~/pii-airlock-env
source ~/pii-airlock-env/bin/activate      # Windows: ~/pii-airlock-env/Scripts/activate
pip install pii-airlock
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
Python 3.10 to 3.14 is required: spaCy does not run on 3.15 yet (`pipx install --python python3.14 pii-airlock`).

## Where the models are

`pii-airlock download-models` stores spaCy models in `$XDG_DATA_HOME/pii-airlock/models`
(`~/.local/share/pii-airlock/models` by default), not in the Python environment. No pip is needed, and
pipx, uv or Homebrew rebuilding that environment does not remove them. Each model is kept for the spaCy
version it was built for: when an upgrade moves spaCy to a version that needs newer models, `doctor`
reports them as missing and `download-models` replaces them. A model installed as a Python package
(`pip install`, `pipx inject`) still works; `doctor` notes that a reinstall would drop it.
