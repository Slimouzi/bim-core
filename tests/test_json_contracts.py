"""Contrats JSON versionnés : politique de schéma, migration legacy, garde-fous.

Politique testée (identique pour tous les contrats) :

- ``schema`` V1 valide → accepté ;
- ``schema`` présent mais inconnu → refus dur ;
- ``schema`` absent + forme legacy connue → accepté, migré, averti ;
- ``schema`` absent + forme inconnue → refusé ;
- ``schema`` absent + mode strict → refusé ;
- champ requis manquant → refusé.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from bim_core.contracts import (
    SCHEMA_COMPUTED_BASE_QUANTITIES_V1,
    SCHEMA_ENVELOPE_QUANTITIES_V1,
    STRICT_SCHEMA_ENV,
    WARN_LEGACY_SCHEMA_MISSING,
    ContractError,
    ContractSource,
    ContractValidationError,
    LegacySchemaWarning,
    LegacyShapeError,
    MissingSchemaError,
    UnknownSchemaError,
    load_envelope_quantities,
    migrate_computed_base_quantities_legacy_to_v1,
    migrate_envelope_quantities_legacy_to_v1,
    parse_computed_base_quantities,
    parse_envelope_quantities,
    utc_now_iso,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Fichier d'enveloppe RÉEL (projet MN_BAT), antérieur aux contrats versionnés :
# aucun champ ``schema``, clés ``layer_pattern`` / ``seuil_i3f``.
MN_BAT_LEGACY = FIXTURES / "mn_bat_envelope_legacy.json"


def _legacy_envelope() -> dict:
    return {
        "file": "modele.ifc",
        "superficie_facades_m2": 2071.18,
        "superficie_menuiseries_m2": 120.5,
        "shab_m2": 2164.68,
        "ratio_fac_shab": 0.9568,
        "seuil_3f": 0.9,
        "par_type": [
            {"type": "ME_36", "n": 24, "etages": ["RDC", "R+1"], "net_side_area_m2": 872.01},
        ],
        "hors_filtre_type": [{"type": "RE 20", "n": 10, "netsidearea_m2": 367.89}],
    }


def _legacy_quantities() -> dict:
    return {
        "source_ifc": "/in/modele.ifc",
        "quantities": [
            {
                "global_id": "1AbC",
                "ifc_class": "IfcSpace",
                "qto": "Qto_SpaceBaseQuantities",
                "quantity": "NetFloorArea",
                "value": 12.98,
                "unit": "m2",
                "status": "computed",
            },
            {
                "global_id": "2DeF",
                "quantity": "NetArea",
                "status": "skipped",
                "reason": "no_geometry",
            },
        ],
    }


# ── schema V1 valide accepté ───────────────────────────────────────────


def test_envelope_v1_accepted():
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope())
    payload = parse_envelope_quantities(doc)
    assert payload.schema_ == SCHEMA_ENVELOPE_QUANTITIES_V1
    assert payload.summary.superficie_facades_m2 == 2071.18
    assert [r.type for r in payload.par_type] == ["ME_36"]


def test_computed_v1_accepted_and_indexed_by_global_id():
    doc = migrate_computed_base_quantities_legacy_to_v1(_legacy_quantities())
    payload = parse_computed_base_quantities(doc)
    index = payload.by_global_id()
    # Seules les entrées fusionnables sont indexées (``skipped`` écarté).
    assert set(index) == {"1AbC"}
    assert index["1AbC"][0].value == 12.98
    assert set(payload.by_global_id(computed_only=False)) == {"1AbC", "2DeF"}


def test_v1_payload_carries_schema_source_created_at():
    stamp = utc_now_iso()
    doc = migrate_envelope_quantities_legacy_to_v1(
        _legacy_envelope(),
        source=ContractSource(producer="ifc-geometry", tool="extract_envelope_surfaces"),
        created_at=stamp,
    )
    payload = parse_envelope_quantities(doc)
    assert payload.schema_ == SCHEMA_ENVELOPE_QUANTITIES_V1
    assert payload.source.producer == "ifc-geometry"
    assert payload.created_at == stamp


def test_created_at_must_be_iso8601():
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope(), created_at="hier")
    with pytest.raises(ContractValidationError, match="ISO-8601"):
        parse_envelope_quantities(doc)


# ── schema inconnu refusé ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "parse",
    [parse_envelope_quantities, parse_computed_base_quantities],
)
def test_unknown_schema_is_hard_refusal(parse):
    with pytest.raises(UnknownSchemaError) as exc:
        parse({"schema": "envelope_quantities/v2", "summary": {}, "quantities": []})
    assert "envelope_quantities/v2" in str(exc.value)


def test_other_known_schema_is_still_refused():
    """Un contrat valide mais d'une AUTRE famille ne passe pas en douce."""
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope())
    with pytest.raises(UnknownSchemaError):
        parse_computed_base_quantities(doc)


@pytest.mark.parametrize("declared", [None, "", 0, False, 1, {"v": 1}])
def test_schema_key_present_but_invalid_is_hard_refusal(declared):
    """``"schema": null`` (ou toute valeur invalide) = schéma **présent** et
    inconnu → refus dur. Le traiter comme absent l'enverrait en migration
    legacy, donc l'accepterait sous simple avertissement."""
    doc = _legacy_envelope()  # forme legacy par ailleurs parfaitement reconnue
    doc["schema"] = declared
    with pytest.raises(UnknownSchemaError):
        parse_envelope_quantities(doc)


def test_schema_null_is_refused_even_out_of_strict_mode(monkeypatch):
    monkeypatch.delenv(STRICT_SCHEMA_ENV, raising=False)
    doc = _legacy_quantities()
    doc["schema"] = None
    with pytest.raises(UnknownSchemaError):
        parse_computed_base_quantities(doc)


# ── schema absent + forme legacy connue → accepté avec warning ─────────


def test_legacy_envelope_accepted_with_warning():
    with pytest.warns(LegacySchemaWarning, match=WARN_LEGACY_SCHEMA_MISSING):
        payload = parse_envelope_quantities(_legacy_envelope())
    assert payload.schema_ == SCHEMA_ENVELOPE_QUANTITIES_V1
    assert payload.summary.shab_m2 == 2164.68


def test_legacy_quantities_accepted_with_warning():
    with pytest.warns(LegacySchemaWarning, match=WARN_LEGACY_SCHEMA_MISSING):
        payload = parse_computed_base_quantities(_legacy_quantities())
    assert payload.schema_ == SCHEMA_COMPUTED_BASE_QUANTITIES_V1
    assert payload.source.ifc_file == "/in/modele.ifc"


def test_v1_payload_emits_no_warning():
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope())
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # toute alerte devient une erreur
        parse_envelope_quantities(doc)


# ── schema absent + forme inconnue → refusé ────────────────────────────


@pytest.mark.parametrize(
    "doc",
    [
        {},
        {"hello": "world"},
        {"par_type": "pas une liste", "superficie_facades_m2": 1, "shab_m2": 2},
        {"par_type": [], "superficie_facades_m2": 1},  # shab_m2 manquant
        {"superficie_facades_m2": 1, "shab_m2": 2},  # par_type manquant
    ],
)
def test_unknown_shape_without_schema_is_refused(doc):
    with pytest.raises(LegacyShapeError):
        parse_envelope_quantities(doc)


@pytest.mark.parametrize(
    "doc",
    [
        {"quantities": []},  # vide → non reconnaissable
        {"quantities": [{"quantity": "NetArea"}]},  # global_id manquant
        {"quantities": "pas une liste"},
    ],
)
def test_unknown_quantities_shape_is_refused(doc):
    with pytest.raises(LegacyShapeError):
        parse_computed_base_quantities(doc)


def test_non_object_document_refused():
    with pytest.raises(ContractValidationError):
        parse_envelope_quantities([1, 2, 3])


# ── champ requis manquant → refusé ─────────────────────────────────────


def test_v1_missing_required_summary_field_refused():
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope())
    del doc["summary"]["shab_m2"]
    with pytest.raises(ContractValidationError):
        parse_envelope_quantities(doc)


def test_v1_missing_quantities_refused():
    doc = migrate_computed_base_quantities_legacy_to_v1(_legacy_quantities())
    del doc["quantities"]
    with pytest.raises(ContractValidationError):
        parse_computed_base_quantities(doc)


# ── mode strict : plus aucune tolérance ────────────────────────────────


def test_strict_env_refuses_payload_without_schema(monkeypatch):
    monkeypatch.setenv(STRICT_SCHEMA_ENV, "true")
    with pytest.raises(MissingSchemaError, match=STRICT_SCHEMA_ENV):
        parse_envelope_quantities(_legacy_envelope())


def test_strict_env_still_accepts_v1(monkeypatch):
    monkeypatch.setenv(STRICT_SCHEMA_ENV, "true")
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope())
    assert parse_envelope_quantities(doc).summary.shab_m2 == 2164.68


def test_strict_parameter_overrides_environment(monkeypatch):
    monkeypatch.delenv(STRICT_SCHEMA_ENV, raising=False)
    with pytest.raises(MissingSchemaError):
        parse_envelope_quantities(_legacy_envelope(), strict=True)


# ── migration : produit EXACTEMENT le contrat V1 ───────────────────────


def test_envelope_migration_produces_exact_v1_document():
    doc = migrate_envelope_quantities_legacy_to_v1(_legacy_envelope())
    assert doc == {
        "schema": SCHEMA_ENVELOPE_QUANTITIES_V1,
        "source": {"producer": None, "tool": None, "version": None, "ifc_file": "modele.ifc"},
        "created_at": None,
        "summary": {
            "superficie_facades_m2": 2071.18,
            "shab_m2": 2164.68,
            "superficie_facades_nette_m2": None,
            "superficie_calque_total_m2": None,
            "superficie_menuiseries_m2": 120.5,
            "superficie_menuiseries_fenetres_m2": None,
            "superficie_menuiseries_portes_m2": None,
            "ratio_fac_shab": 0.9568,
            "seuil_i3f": 0.9,  # alias `seuil_3f` normalisé
            "conforme_seuil": None,
            "methode_facade": None,
        },
        "par_type": [
            {
                "type": "ME_36",
                "n": 24,
                "etages": ["RDC", "R+1"],
                "net_side_area_m2": 872.01,
                "surface_ifc_openshell_m2": None,
                "menuiseries_m2": None,
                "fenetres_m2": None,
                "portes_m2": None,
                "superficie_ouvertures_exterieures_m2": None,
            }
        ],
        "hors_filtre_type": [
            {
                "type": "RE 20",
                "n": 10,
                "etages": [],
                "net_side_area_m2": 367.89,  # alias `netsidearea_m2` normalisé
                "surface_ifc_openshell_m2": None,
                "menuiseries_m2": None,
                "fenetres_m2": None,
                "portes_m2": None,
                "superficie_ouvertures_exterieures_m2": None,
            }
        ],
        "diagnostics": {},
    }


def test_migration_is_idempotent_through_parse():
    """Migrer puis valider donne le même payload que valider le document migré."""
    legacy = _legacy_envelope()
    with pytest.warns(LegacySchemaWarning):
        from_legacy = parse_envelope_quantities(legacy)
    from_v1 = parse_envelope_quantities(migrate_envelope_quantities_legacy_to_v1(legacy))
    assert from_legacy.to_document() == from_v1.to_document()


def test_migration_refuses_unrecognized_shape_directly():
    with pytest.raises(ContractValidationError):
        migrate_envelope_quantities_legacy_to_v1({"nope": 1})


def test_quantities_migration_derives_coverage_when_absent():
    doc = migrate_computed_base_quantities_legacy_to_v1(_legacy_quantities())
    # Dérivé par comptage des statuts — jamais inventé ; n_elements reste inconnu
    # (plusieurs quantités peuvent porter sur le même élément).
    assert doc["coverage"] == {"n_elements": None, "n_computed": 1, "n_failed": 1}


def test_quantities_migration_keeps_producer_coverage():
    legacy = _legacy_quantities()
    legacy["coverage"] = {"n_elements": 2, "n_computed": 1, "n_failed": 1}
    doc = migrate_computed_base_quantities_legacy_to_v1(legacy)
    assert doc["coverage"] == {"n_elements": 2, "n_computed": 1, "n_failed": 1}


# ── roundtrip sur le fichier MN_BAT réel ───────────────────────────────


def test_mn_bat_legacy_fixture_has_no_schema():
    """Garde-fou : la fixture doit rester le fichier legacy d'origine."""
    doc = json.loads(MN_BAT_LEGACY.read_text(encoding="utf-8"))
    assert "schema" not in doc
    assert "layer_pattern" in doc


def test_mn_bat_legacy_file_accepted_via_migration():
    with pytest.warns(LegacySchemaWarning, match=WARN_LEGACY_SCHEMA_MISSING):
        payload = load_envelope_quantities(str(MN_BAT_LEGACY))

    # Valeurs métier pré-validées sur le projet réel (8 lignes, ratio 0,9568).
    assert len(payload.par_type) == 8
    assert payload.summary.superficie_facades_m2 == 2071.18
    assert payload.summary.shab_m2 == 2164.68
    assert payload.summary.ratio_fac_shab == 0.9568
    assert payload.summary.seuil_i3f == 0.9
    assert round(sum(r.net_side_area_m2 for r in payload.par_type), 2) == 2071.19

    # Lignes normalisées : `n` et `etages` exploitables directement.
    first = payload.par_type[0]
    assert first.n == 24
    assert first.etages and all(isinstance(e, str) for e in first.etages)

    # Les types hors filtre restent hors du total métier.
    assert len(payload.hors_filtre_type) == 11


def test_mn_bat_diagnostics_preserve_producer_fields():
    """Aucune donnée du producteur n'est perdue par la migration."""
    with pytest.warns(LegacySchemaWarning):
        payload = load_envelope_quantities(str(MN_BAT_LEGACY))
    for key in ("layer_pattern", "n_murs_calque", "shab_types_exclus"):
        assert key in payload.diagnostics


def test_mn_bat_refused_in_strict_mode(monkeypatch):
    """La compat est bien temporaire : le mode strict la coupe."""
    monkeypatch.setenv(STRICT_SCHEMA_ENV, "1")
    with pytest.raises(MissingSchemaError):
        load_envelope_quantities(str(MN_BAT_LEGACY))


def test_missing_file_raises_typed_error():
    with pytest.raises(ContractValidationError, match="introuvable"):
        load_envelope_quantities(str(FIXTURES / "nope.json"))


def test_all_errors_are_value_errors():
    """Les consommateurs historiques attrapent ``ValueError`` — contrat préservé."""
    for exc in (
        UnknownSchemaError,
        MissingSchemaError,
        LegacyShapeError,
        ContractValidationError,
    ):
        assert issubclass(exc, ContractError)
        assert issubclass(exc, ValueError)
