"""spaCy models kept outside the Python environment, so upgrades can't remove them.

pipx and ``uv tool`` rebuild an app's environment on a reinstall (and on some
upgrades): a model installed into it with ``pipx inject`` or ``spacy download``
goes with it, and detection stops until the user notices. pii-airlock therefore
downloads models into its own data directory and loads them from there by path:

    $XDG_DATA_HOME/pii-airlock/models/<model>-<version>/   (~/.local/share/...)

No pip is needed. A model installed as a package still works; a stored copy that
fits the installed spaCy is preferred, so an upgrade that moves spaCy to a new
minor version asks for a fresh download instead of loading a mismatched model.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

_RELEASES = "https://github.com/explosion/spacy-models/releases/download"


def home() -> Path:
    """``$XDG_DATA_HOME/pii-airlock/models`` (``~/.local/share/pii-airlock/models``)."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "pii-airlock" / "models"


def _spacy_version() -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("spacy")
    except PackageNotFoundError:
        return None


def _fits(meta: dict, spacy_version: str | None) -> bool:
    """Whether a model's meta.json allows the installed spaCy version."""
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    wanted = meta.get("spacy_version")
    if not wanted or spacy_version is None:
        return True
    try:
        return SpecifierSet(wanted).contains(spacy_version, prereleases=True)
    except InvalidSpecifier:
        return True


def _meta(path: Path) -> dict | None:
    try:
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def stored(model: str) -> Path | None:
    """The newest stored copy of `model` that fits the installed spaCy, if any."""
    from packaging.version import InvalidVersion, Version

    root = home()
    if not root.is_dir():
        return None
    spacy_version = _spacy_version()
    best: tuple[Version, Path] | None = None
    for path in root.glob(f"{model}-*"):
        meta = _meta(path)
        if not meta or f"{meta.get('lang')}_{meta.get('name')}" != model:
            continue
        if not _fits(meta, spacy_version):
            continue
        try:
            version = Version(str(meta.get("version")))
        except InvalidVersion:
            continue
        if best is None or version > best[0]:
            best = (version, path)
    return best[1] if best else None


def locate(model: str) -> str | None:
    """What spaCy should load for `model`: a path, an installed package name, or None.

    `model` may itself be a path to a model directory.
    """
    if Path(model).is_dir():
        return model
    path = stored(model)
    if path is not None:
        return str(path)
    importlib.invalidate_caches()
    return model if importlib.util.find_spec(model) is not None else None


def in_environment_only(model: str) -> bool:
    """`model` loads, but only from the app's environment (a reinstall can drop it)."""
    if Path(model).is_dir() or stored(model) is not None:
        return False
    return importlib.util.find_spec(model) is not None


def load_failure(exc: BaseException) -> str:
    """What to tell the user when spaCy is installed but cannot load a model."""
    py = ".".join(map(str, sys.version_info[:2]))
    what = (f"spaCy {_spacy_version()} cannot load models on Python {py} "
            f"({type(exc).__name__}: {exc}).")
    if sys.version_info >= (3, 15):  # spaCy 3.8 breaks there (tokenizer OverflowError)
        return (f"{what} Reinstall pii-airlock on Python 3.14: "
                "`pipx reinstall --python python3.14 pii-airlock` (downloaded models are kept).")
    return f"{what} Reinstall pii-airlock (`pipx reinstall pii-airlock`)."


def check(model: str) -> str | None:
    """Load `model` and run it on one sentence: None if it works, else the problem."""
    where = locate(model)
    if where is None:
        return f"{model} is not installed (run `pii-airlock download-models`)"
    try:
        import spacy

        spacy.load(where)("Jean Dupont lives in Geneva.")
    except Exception as exc:
        return load_failure(exc)
    return None


def wheel_url(model: str) -> str:
    """The release wheel of `model` that fits the installed spaCy (network)."""
    try:
        from spacy.cli.download import get_compatibility, get_version

        version = get_version(model, get_compatibility())
    except (Exception, SystemExit) as exc:  # spaCy's helpers exit on errors
        raise RuntimeError(
            f"cannot find a release of {model} for spaCy {_spacy_version()} "
            "(check the model name and your network)"
        ) from exc
    return f"{_RELEASES}/{model}-{version}/{model}-{version}-py3-none-any.whl"


def _download(url: str, dest: Path, progress: Callable[[str], None]) -> None:
    import requests  # a spaCy dependency; uses certifi, unlike urllib on some Pythons

    with requests.get(url, stream=True, timeout=(10, 120)) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length") or 0)
        if total:
            progress(f"  {total / 1e6:.0f} MB")
        with open(dest, "wb") as out:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                out.write(chunk)


def _extract(wheel: Path, model: str, staging: Path) -> dict:
    """Unpack the model's data directory from `wheel` into `staging`; its meta."""
    with zipfile.ZipFile(wheel) as zf:
        parts = [PurePosixPath(n).parts for n in zf.namelist()]
        data_dirs = {p[1] for p in parts
                     if len(p) > 2 and p[0] == model and p[1].startswith(f"{model}-")}
        if len(data_dirs) != 1:
            raise RuntimeError(f"unexpected layout in the {model} wheel")
        prefix = f"{model}/{data_dirs.pop()}/"
        for info in zf.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            rel = PurePosixPath(info.filename[len(prefix):])
            if rel.is_absolute() or ".." in rel.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe path in the {model} wheel: {info.filename!r}")
            target = staging.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    meta = _meta(staging)
    if not meta or f"{meta.get('lang')}_{meta.get('name')}" != model:
        raise RuntimeError(f"the {model} wheel has no matching meta.json")
    return meta


def install(model: str, progress: Callable[[str], None] = print) -> Path:
    """Download `model` into :func:`home` and return its directory.

    Older stored versions of the same model are removed once the new one is in
    place. Raises RuntimeError (nothing half-written is left behind) on failure.
    """
    url = wheel_url(model)
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    progress(f"Downloading {model} from {url}")
    with tempfile.TemporaryDirectory(dir=root, prefix=f".{model}-") as tmp:
        wheel, staging = Path(tmp) / "model.whl", Path(tmp) / "model"
        try:
            _download(url, wheel, progress)
            meta = _extract(wheel, model, staging)
        except (OSError, zipfile.BadZipFile) as exc:  # requests' errors are OSErrors
            raise RuntimeError(f"download of {model} failed: {exc}") from exc
        if not _fits(meta, _spacy_version()):
            raise RuntimeError(f"{model} {meta.get('version')} needs spaCy "
                               f"{meta.get('spacy_version')}, this is {_spacy_version()}")
        dest = root / f"{model}-{meta['version']}"
        if dest.exists():
            shutil.rmtree(dest)
        staging.rename(dest)
    for old in root.glob(f"{model}-*"):
        if old != dest and old.is_dir():
            shutil.rmtree(old, ignore_errors=True)  # a running daemon keeps its copy in memory
    return dest
