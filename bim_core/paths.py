"""Sandbox de chemins I/O — implémentation commune + deux profils historiques.

Migré **verbatim** depuis ``bim-sandbox`` : les corps de fonctions sont
inchangés, seule la docstring de module l'est. Ce choix est délibéré — la
sandbox est un garde-fou de sécurité, la réécrire à l'occasion d'un
déménagement introduirait un risque sans contrepartie.

Ce module est désormais la **seule** implémentation : la décommission de
``bim-sandbox`` est terminée (plus aucun consommateur), le dépôt d'origine
n'étant plus qu'un shim de ré-exports figé.

Un serveur MCP piloté par un agent distant doit refuser tout chemin hostile avant
de toucher au disque. Ce module fournit la validation partagée, avec **deux
profils** reproduisant à l'identique le comportement historique de chaque MCP :

- **audit** : base ``cwd`` + whitelist d'extensions (défaut) + fichier régulier +
  taille max ; sorties via ``safe_export_path`` (confinement, ``..`` interdits).
- **ifc** : base ``AUDIT_INPUT_DIR`` + existence + extension (si fournie) ;
  sortie via ``safe_output_path`` (aplatissement ``Path(name).name``).

Toutes les violations lèvent :class:`UnsafePathError` (sous-classe de
``ValueError`` → compatible avec les ``except ValueError`` existants).
``safe_output_path`` conserve ``FileExistsError`` sur écrasement (parité stricte,
cf. décision de scope — pas d'unification en v0.1.0).
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_EXPORT_DIR = "./out"
DEFAULT_MAX_INPUT_MB = 50

# Extensions acceptées en *input* (profil audit par défaut). Volontairement
# strict : pas de .zip, .exe, .py, .so, etc.
ALLOWED_INPUT_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xlsm",
    ".xls",
    ".docx",
    ".csv",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
}


class UnsafePathError(ValueError):
    """Chemin refusé par la sandbox d'I/O."""


# ── Racines / limites (lues à chaque appel : testables via monkeypatch) ──────


def get_export_root() -> Path:
    """Racine d'export courante (``AUDIT_OUTPUT_DIR`` ou ``./out``), créée."""
    root_str = os.getenv("AUDIT_OUTPUT_DIR") or DEFAULT_EXPORT_DIR
    root = Path(root_str).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def input_root() -> Path | None:
    """Racine d'inputs autorisée. ``None`` si ``AUDIT_INPUT_DIR`` non défini."""
    root_str = os.getenv("AUDIT_INPUT_DIR")
    if not root_str:
        return None
    return Path(root_str).expanduser().resolve()


def max_input_bytes() -> int:
    """Taille maximale acceptée pour un input (octets)."""
    raw = os.getenv("AUDIT_MAX_INPUT_MB")
    try:
        mb = int(raw) if raw else DEFAULT_MAX_INPUT_MB
    except ValueError:
        mb = DEFAULT_MAX_INPUT_MB
    return max(1, mb) * 1024 * 1024


# ── Écriture — profil audit (confinement, sans aplatissement) ────────────────


def safe_export_path(
    output_path: str | os.PathLike,
    *,
    overwrite: bool = False,
    export_root: Path | None = None,
) -> Path:
    """Valide un chemin d'**écriture** sous la racine d'export.

    Raises:
        UnsafePathError: ``..``, évasion de racine, ou écrasement non autorisé.
    """
    root = (export_root or get_export_root()).resolve()
    raw = Path(output_path).expanduser()

    if any(part == ".." for part in raw.parts):
        raise UnsafePathError(f"Composants `..` interdits dans le chemin : {output_path!r}")

    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Le chemin doit rester sous {root}. Reçu : {candidate}") from exc

    if candidate.exists() and not overwrite:
        raise UnsafePathError(f"{candidate} existe déjà — passer `overwrite=True` pour l'écraser.")

    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def safe_export_read_path(
    output_path: str | os.PathLike,
    *,
    export_root: Path | None = None,
    must_exist: bool = True,
) -> Path:
    """Valide un chemin de **lecture** sous la racine d'export.

    Raises:
        UnsafePathError: ``..`` ou évasion de racine.
        FileNotFoundError: ``must_exist=True`` et fichier absent.
    """
    root = (export_root or get_export_root()).resolve()
    raw = Path(output_path).expanduser()

    if any(part == ".." for part in raw.parts):
        raise UnsafePathError(f"Composants `..` interdits dans le chemin : {output_path!r}")

    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Le chemin doit rester sous {root}. Reçu : {candidate}") from exc

    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)

    return candidate


def safe_export_dir(
    dir_path: str | os.PathLike,
    *,
    export_root: Path | None = None,
) -> Path:
    """Variante de :func:`safe_export_path` pour un **dossier** (créé si absent).

    Raises:
        UnsafePathError: ``..`` ou évasion de la racine.
    """
    root = (export_root or get_export_root()).resolve()
    raw = Path(dir_path).expanduser()

    if any(part == ".." for part in raw.parts):
        raise UnsafePathError(f"Composants `..` interdits dans le chemin : {dir_path!r}")

    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafePathError(f"Le dossier doit rester sous {root}. Reçu : {candidate}") from exc

    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


# ── Écriture — profil ifc (aplatissement Path(name).name) ────────────────────


def safe_output_path(name: str, *, overwrite: bool = False) -> Path:
    """Résout un **nom** de fichier de sortie sous la racine d'export.

    Ne garde que ``Path(name).name`` : sous-dossiers et traversals sont **aplatis**
    vers le seul nom de fichier (pas de refus). Conserve ``FileExistsError`` sur
    écrasement (parité stricte).
    """
    root = get_export_root()
    target = (root / Path(name).name).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:  # pragma: no cover - défensif
        raise UnsafePathError(f"Chemin de sortie hors sandbox : {target}") from exc
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} existe déjà (passer overwrite=True pour remplacer).")
    return target


# ── Lecture — dispatch par profil ────────────────────────────────────────────


def safe_input_path(
    path: str | os.PathLike,
    *,
    profile: str = "audit",
    allowed_extensions: set[str] | None = None,
) -> Path:
    """Valide un chemin de lecture exposé via un tool MCP.

    Args:
        profile: ``"audit"`` (base cwd + whitelist défaut + fichier régulier +
            taille max) ou ``"ifc"`` (base ``AUDIT_INPUT_DIR`` + existence +
            extension si fournie). Chaque MCP passe son profil historique.
        allowed_extensions: Whitelist (minuscule, avec le point). Profil audit :
            ``None`` → :data:`ALLOWED_INPUT_EXTENSIONS`. Profil ifc : ``None`` →
            pas de contrôle d'extension.
    """
    if profile == "audit":
        return _safe_input_audit(path, allowed_extensions=allowed_extensions)
    if profile == "ifc":
        return _safe_input_ifc(path, allowed_extensions=allowed_extensions)
    raise ValueError(f"profile inconnu : {profile!r} (attendu 'audit' ou 'ifc')")


def _safe_input_audit(
    input_path: str | os.PathLike, *, allowed_extensions: set[str] | None = None
) -> Path:
    """Profil audit : ban ``..`` → résolution cwd → confinement → extension
    (whitelist défaut) → existence → fichier régulier → taille max."""
    raw = Path(input_path).expanduser()
    if any(part == ".." for part in raw.parts):
        raise UnsafePathError(f"Composants `..` interdits : {input_path!r}")

    candidate = raw.resolve()

    root = input_root()
    if root is not None:
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise UnsafePathError(
                f"Le chemin doit rester sous AUDIT_INPUT_DIR={root}. Reçu : {candidate}"
            ) from exc

    extensions = allowed_extensions or ALLOWED_INPUT_EXTENSIONS
    if candidate.suffix.lower() not in extensions:
        raise UnsafePathError(
            f"Extension {candidate.suffix!r} non autorisée. Autorisées : {sorted(extensions)}"
        )

    if not candidate.exists():
        raise FileNotFoundError(candidate)
    if not candidate.is_file():
        raise UnsafePathError(f"Le chemin n'est pas un fichier régulier : {candidate}")

    size = candidate.stat().st_size
    limit = max_input_bytes()
    if size > limit:
        raise UnsafePathError(
            f"Fichier trop volumineux : {size} octets > limite {limit} (AUDIT_MAX_INPUT_MB)."
        )

    return candidate


def _safe_input_ifc(path: str | os.PathLike, *, allowed_extensions: set[str] | None = None) -> Path:
    """Profil ifc : résolution ``AUDIT_INPUT_DIR/name`` → confinement →
    existence → extension (uniquement si fournie)."""
    p = Path(path).expanduser()
    root = input_root()
    if root is not None:
        candidate = (root / p).resolve() if not p.is_absolute() else p.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise UnsafePathError(f"Chemin hors AUDIT_INPUT_DIR ({root}) : {candidate}") from exc
    else:
        candidate = p.resolve()

    if not candidate.exists():
        raise FileNotFoundError(f"Fichier introuvable : {candidate}")
    if allowed_extensions and candidate.suffix.lower() not in allowed_extensions:
        raise UnsafePathError(
            f"Extension non autorisée ({candidate.suffix}). Attendu : {sorted(allowed_extensions)}"
        )
    return candidate
