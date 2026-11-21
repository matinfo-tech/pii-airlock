"""The model store: spaCy models kept outside the app's environment."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from pii_scrub import models


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(models, "_spacy_version", lambda: "3.8.7")
    monkeypatch.setattr(models, "wheel_url", lambda model: f"https://example.test/{model}.whl")


def _meta(version="3.8.0", spacy=">=3.8.0,<3.9.0", name="core_web_sm"):
    return json.dumps({"lang": "en", "name": name, "version": version, "spacy_version": spacy})


def _wheel(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def _real_layout(version="3.8.0", spacy=">=3.8.0,<3.9.0") -> dict[str, str]:
    data = f"en_core_web_sm/en_core_web_sm-{version}/"
    return {
        "en_core_web_sm/__init__.py": "",
        "en_core_web_sm/meta.json": _meta(version, spacy),
        data + "meta.json": _meta(version, spacy),
        data + "config.cfg": "[nlp]\n",
        data + "ner/model": "weights",
        f"en_core_web_sm-{version}.dist-info/METADATA": "",
    }


def _serve(monkeypatch, members: dict[str, str]) -> None:
    def _download(url, dest, progress):
        _wheel(dest, members)

    monkeypatch.setattr(models, "_download", _download)


def test_home_follows_xdg_data_home(tmp_path):
    assert models.home() == tmp_path / "data" / "pii-airlock" / "models"


def test_install_unpacks_the_model_directory_only(monkeypatch):
    _serve(monkeypatch, _real_layout())

    path = models.install("en_core_web_sm", progress=lambda _l: None)

    assert path == models.home() / "en_core_web_sm-3.8.0"
    assert sorted(p.name for p in path.iterdir()) == ["config.cfg", "meta.json", "ner"]
    assert models.stored("en_core_web_sm") == path
    assert models.locate("en_core_web_sm") == str(path)


def test_install_replaces_older_versions(monkeypatch):
    _serve(monkeypatch, _real_layout("3.8.0"))
    old = models.install("en_core_web_sm", progress=lambda _l: None)
    _serve(monkeypatch, _real_layout("3.8.1"))

    new = models.install("en_core_web_sm", progress=lambda _l: None)

    assert new.name == "en_core_web_sm-3.8.1" and not old.exists()


def test_install_refuses_paths_outside_the_store(monkeypatch, tmp_path):
    members = _real_layout()
    members["en_core_web_sm/en_core_web_sm-3.8.0/../../../../evil.txt"] = "x"
    _serve(monkeypatch, members)

    with pytest.raises(RuntimeError, match="unsafe path"):
        models.install("en_core_web_sm", progress=lambda _l: None)

    assert not list(tmp_path.rglob("evil.txt"))
    assert models.stored("en_core_web_sm") is None
    assert [p.name for p in models.home().iterdir()] == []  # nothing half-written


def test_install_refuses_a_wheel_for_another_model(monkeypatch):
    members = _real_layout()
    members["en_core_web_sm/en_core_web_sm-3.8.0/meta.json"] = _meta(name="core_web_lg")
    _serve(monkeypatch, members)

    with pytest.raises(RuntimeError, match="no matching meta.json"):
        models.install("en_core_web_sm", progress=lambda _l: None)


def test_a_download_error_is_a_runtime_error(monkeypatch):
    def _download(url, dest, progress):
        raise ConnectionError("offline")

    monkeypatch.setattr(models, "_download", _download)

    with pytest.raises(RuntimeError, match="offline"):
        models.install("en_core_web_sm", progress=lambda _l: None)


def test_a_stored_model_for_another_spacy_is_not_used(monkeypatch):
    _serve(monkeypatch, _real_layout())
    models.install("en_core_web_sm", progress=lambda _l: None)
    monkeypatch.setattr(models, "_spacy_version", lambda: "3.9.0")  # spaCy upgraded

    assert models.stored("en_core_web_sm") is None


def test_locate_falls_back_to_an_installed_package(monkeypatch):
    monkeypatch.setattr(models.importlib.util, "find_spec",
                        lambda name: object() if name == "en_core_web_sm" else None)

    assert models.locate("en_core_web_sm") == "en_core_web_sm"
    assert models.in_environment_only("en_core_web_sm")
    assert models.locate("xx_missing") is None


def test_a_stored_copy_is_not_fragile(monkeypatch):
    _serve(monkeypatch, _real_layout())
    models.install("en_core_web_sm", progress=lambda _l: None)
    monkeypatch.setattr(models.importlib.util, "find_spec", lambda name: object())

    assert not models.in_environment_only("en_core_web_sm")


def test_locate_accepts_a_model_directory(tmp_path):
    assert models.locate(str(tmp_path)) == str(tmp_path)


def test_engine_loads_a_stored_model_by_path(monkeypatch):
    """The analyzer hands Presidio the store path, not the package name."""
    from pii_scrub.config import Config
    from pii_scrub.engine import ScrubEngine

    _serve(monkeypatch, _real_layout())
    path = models.install("en_core_web_sm", progress=lambda _l: None)
    seen = {}

    class _Provider:
        def __init__(self, nlp_configuration):
            seen.update(nlp_configuration)

        def create_engine(self):
            raise OverflowError("boom")  # enough: the configuration is what we check

    import presidio_analyzer.nlp_engine as nlp

    monkeypatch.setattr(nlp, "NlpEngineProvider", _Provider)
    engine = ScrubEngine(Config(languages=["en"], models={"en": "en_core_web_sm"}))
    with pytest.raises(RuntimeError, match="cannot load models on Python"):
        engine._analyzer  # noqa: B018

    assert seen["models"] == [{"lang_code": "en", "model_name": str(path)}]


def test_on_python_315_the_hint_names_an_older_python(monkeypatch):
    monkeypatch.setattr(models.sys, "version_info", (3, 15, 2, "final", 0))

    hint = models.load_failure(OverflowError("Python int too large"))

    assert "Python 3.15" in hint and "pipx reinstall --python python3.14" in hint


def test_check_reports_a_model_that_does_not_load(monkeypatch, tmp_path):
    import spacy

    def _load(where):
        raise OverflowError("Python int too large to convert to C ssize_t")

    monkeypatch.setattr(spacy, "load", _load)

    assert "OverflowError" in models.check(str(tmp_path))
    assert "not installed" in models.check("xx_missing_model")
