"""Sandbox de chemins : profils historiques audit/ifc, P2.1/P2.2, erreurs
overwrite (décision 2), contrôles input. Offline, filesystem tmp.

Tests repris **tels quels** de ``bim-sandbox`` lors de la migration : ce sont
eux qui garantissent que le déménagement n'a rien changé au comportement.
"""

from __future__ import annotations

import pytest

from bim_core import paths as bs


def _mkfile(p, content=b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


# ── UnsafePathError = ValueError (compat except ValueError) ───────────────────


def test_unsafe_path_error_is_value_error():
    assert issubclass(bs.UnsafePathError, ValueError)


# ── P2.1 — résolution des relatifs DIVERGE selon le profil ────────────────────


def test_p2_1_relative_resolution_diverges(tmp_path, monkeypatch):
    in_dir = tmp_path / "in"
    _mkfile(in_dir / "a.pdf")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("AUDIT_INPUT_DIR", str(in_dir))
    monkeypatch.chdir(work)  # cwd HORS de AUDIT_INPUT_DIR

    # ifc : "a.pdf" résolu sous AUDIT_INPUT_DIR → OK
    got = bs.safe_input_path("a.pdf", profile="ifc")
    assert got == (in_dir / "a.pdf").resolve()

    # audit : "a.pdf" résolu depuis cwd (=work) → hors racine → refus
    with pytest.raises(bs.UnsafePathError):
        bs.safe_input_path("a.pdf", profile="audit")


def test_audit_resolves_from_cwd_without_root(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIT_INPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    _mkfile(tmp_path / "a.pdf")
    got = bs.safe_input_path("a.pdf", profile="audit")
    assert got == (tmp_path / "a.pdf").resolve()


# ── P2.2 — safe_output_path APLATIT vers Path(name).name ──────────────────────


def test_p2_2_output_path_flattens(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_OUTPUT_DIR", str(tmp_path / "out"))
    target = bs.safe_output_path("sub/dir/../x.json")
    assert target.name == "x.json"
    assert target.parent == (tmp_path / "out").resolve()  # aplati sous la racine


# ── Décision 2 — erreurs overwrite par fonction ───────────────────────────────


def test_decision2_export_path_existing_raises_unsafe(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_OUTPUT_DIR", str(tmp_path / "out"))
    p = bs.safe_export_path("x.json")
    _mkfile(p)
    with pytest.raises(bs.UnsafePathError):
        bs.safe_export_path("x.json", overwrite=False)


def test_decision2_output_path_existing_raises_file_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_OUTPUT_DIR", str(tmp_path / "out"))
    p = bs.safe_output_path("x.json")
    _mkfile(p)
    with pytest.raises(FileExistsError):
        bs.safe_output_path("x.json", overwrite=False)


# ── Confinement écriture (profil audit) ───────────────────────────────────────


def test_export_path_dotdot_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_OUTPUT_DIR", str(tmp_path / "out"))
    with pytest.raises(bs.UnsafePathError):
        bs.safe_export_path("../escape.json")


def test_export_path_absolute_outside_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_OUTPUT_DIR", str(tmp_path / "out"))
    with pytest.raises(bs.UnsafePathError):
        bs.safe_export_path(str(tmp_path / "elsewhere.json"))


# ── Contrôles input — profil audit (whitelist défaut, régulier, taille) ───────


def test_audit_default_whitelist_enforced(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIT_INPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    _mkfile(tmp_path / "bad.exe")
    with pytest.raises(bs.UnsafePathError):  # .exe hors whitelist défaut
        bs.safe_input_path("bad.exe", profile="audit")


def test_audit_dotdot_refused(tmp_path, monkeypatch):
    with pytest.raises(bs.UnsafePathError):
        bs.safe_input_path("../x.pdf", profile="audit")


def test_audit_missing_file_raises_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIT_INPUT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        bs.safe_input_path("nope.pdf", profile="audit")


def test_audit_size_limit(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIT_INPUT_DIR", raising=False)
    monkeypatch.setenv("AUDIT_MAX_INPUT_MB", "1")
    monkeypatch.chdir(tmp_path)
    _mkfile(tmp_path / "big.pdf", content=b"0" * (2 * 1024 * 1024))  # 2 MB > 1 MB
    with pytest.raises(bs.UnsafePathError):
        bs.safe_input_path("big.pdf", profile="audit")


# ── Contrôles input — profil ifc (pas de whitelist défaut) ────────────────────


def test_ifc_no_default_whitelist(tmp_path, monkeypatch):
    # Sans allowed_extensions, ifc n'impose PAS d'extension (contraire à audit).
    monkeypatch.setenv("AUDIT_INPUT_DIR", str(tmp_path))
    _mkfile(tmp_path / "model.ifc")
    got = bs.safe_input_path("model.ifc", profile="ifc")
    assert got == (tmp_path / "model.ifc").resolve()


def test_ifc_extension_checked_when_provided(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_INPUT_DIR", str(tmp_path))
    _mkfile(tmp_path / "model.txt")
    with pytest.raises(bs.UnsafePathError):
        bs.safe_input_path("model.txt", profile="ifc", allowed_extensions={".ifc"})


def test_ifc_outside_root_refused(tmp_path, monkeypatch):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    monkeypatch.setenv("AUDIT_INPUT_DIR", str(in_dir))
    _mkfile(tmp_path / "outside.ifc")
    with pytest.raises(bs.UnsafePathError):
        bs.safe_input_path(str(tmp_path / "outside.ifc"), profile="ifc")


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        bs.safe_input_path("x.pdf", profile="nope")
