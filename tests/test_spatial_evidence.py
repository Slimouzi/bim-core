"""Contrat ``spatial_evidence/v1`` — ce que la validation doit refuser.

Ces tests portent surtout sur les **refus**. Un contrat de preuves n'a de valeur
que s'il rend impossible de faire passer une non-mesure pour une mesure.
"""

from __future__ import annotations

import warnings

import pytest

from bim_core.contracts import (
    SCHEMA_SPATIAL_EVIDENCE_V1,
    Containment,
    ContractValidationError,
    MissingSchemaError,
    ObjectEvidence,
    SpaceEvidence,
    SpatialEvidenceV1,
    UnknownSchemaError,
    parse_spatial_evidence,
)
from bim_core.contracts.errors import LegacySchemaWarning


def _doc(**overrides):
    doc = {
        "schema": SCHEMA_SPATIAL_EVIDENCE_V1,
        "source": {"producer": "ifc-geometry", "tool": "extract_spatial_evidence"},
        "created_at": "2026-08-06T10:00:00+00:00",
        "selection": {"classes": ["IfcSpace", "IfcDoor"], "n_selected": 2},
        "coverage": {"n_objects": 1, "n_with_bbox": 1, "n_spaces": 1},
        "objects": [
            {
                "global_id": "0aBcDeF",
                "ifc_class": "IfcDoor",
                "bbox": {
                    "x_min": 0.0,
                    "x_max": 0.9,
                    "y_min": 0.0,
                    "y_max": 0.1,
                    "z_min": 0.0,
                    "z_max": 2.1,
                },
                "opening_width_m": 0.9,
                "opening_height_m": 2.1,
                "container": {
                    "space_global_id": "1SpAcE",
                    "method": "centroid_in_footprint",
                    "overlap_ratio": 1.0,
                },
            }
        ],
        "spaces": [
            {
                "global_id": "1SpAcE",
                "ifc_class": "IfcSpace",
                "long_name": "SEJOUR",
                "area_declared_m2": 21.0,
                "min_rect_width_m": 4.2,
                "inscribed_diameter_m": 3.1,
                "contained_global_ids": ["0aBcDeF"],
            }
        ],
    }
    doc.update(overrides)
    return doc


def test_document_valide_est_accepte():
    payload = parse_spatial_evidence(_doc())
    assert isinstance(payload, SpatialEvidenceV1)
    assert payload.spaces[0].inscribed_diameter_m == 3.1
    assert payload.objects[0].container.method == "centroid_in_footprint"


def test_espace_est_aussi_un_objet():
    """``SpaceEvidence`` hérite d'``ObjectEvidence`` : un consommateur qui itère
    sur les deux listes lit les mêmes champs de base sans cas particulier."""
    payload = parse_spatial_evidence(_doc())
    assert payload.spaces[0].ifc_class == "IfcSpace"
    assert payload.spaces[0].geometry_status == "ok"


def test_payload_sans_schema_est_refuse_hors_mode_strict(monkeypatch):
    """Le point dur du contrat : né versionné, donc aucune tolérance legacy.

    Les deux autres contrats acceptent un payload sans ``schema`` quand sa forme
    est reconnue, pour ne pas casser les fichiers déjà produits. Ici il n'existe
    aucun fichier antérieur : accepter serait ouvrir une dette sans dette.
    """
    monkeypatch.delenv("BIM_CORE_JSON_STRICT_SCHEMA", raising=False)
    doc = _doc()
    del doc["schema"]
    with pytest.raises(MissingSchemaError):
        parse_spatial_evidence(doc)


def test_payload_sans_schema_n_emet_aucun_avertissement_de_migration(monkeypatch):
    monkeypatch.delenv("BIM_CORE_JSON_STRICT_SCHEMA", raising=False)
    doc = _doc()
    del doc["schema"]
    with warnings.catch_warnings():
        warnings.simplefilter("error", LegacySchemaWarning)
        with pytest.raises(MissingSchemaError):
            parse_spatial_evidence(doc)


@pytest.mark.parametrize("declared", ["envelope_quantities/v1", "spatial_evidence/v2", None])
def test_autre_schema_est_refuse_durement(declared):
    with pytest.raises(UnknownSchemaError):
        parse_spatial_evidence(_doc(schema=declared))


def test_methode_de_rattachement_inconnue_est_refusee():
    """Une méthode inventée ferait passer une déduction pour une déclaration IFC."""
    doc = _doc()
    doc["objects"][0]["container"]["method"] = "probablement"
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(doc)


@pytest.mark.parametrize("ratio", [-0.1, 1.5, 4.2])
def test_overlap_ratio_hors_bornes_est_refuse(ratio):
    """Une part d'empreinte est une fraction, pas un nombre libre.

    Un producteur qui rendrait 4,2 aurait un bug — probablement une somme de
    recouvrements au lieu d'une union. L'accepter ferait porter l'erreur au
    consommateur, qui n'a aucun moyen de la distinguer d'une mesure valide.
    """
    doc = _doc()
    doc["objects"][0]["container"]["overlap_ratio"] = ratio
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(doc)


@pytest.mark.parametrize("ratio", [0.0, 0.5, 1.0])
def test_overlap_ratio_dans_les_bornes_est_accepte(ratio):
    doc = _doc()
    doc["objects"][0]["container"]["overlap_ratio"] = ratio
    payload = parse_spatial_evidence(doc)
    assert payload.objects[0].container.overlap_ratio == ratio


def test_statut_de_geometrie_inconnu_est_refuse():
    doc = _doc()
    doc["objects"][0]["geometry_status"] = "peut_etre"
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(doc)


def test_objet_sans_geometrie_reste_dans_le_document():
    """Ne pas le supprimer : une maquette sans représentation est un fait à
    rapporter, pas une absence de problème."""
    doc = _doc()
    doc["objects"].append(
        {"global_id": "2NoGeo", "ifc_class": "IfcDoor", "geometry_status": "no_representation"}
    )
    payload = parse_spatial_evidence(doc)
    absent = [o for o in payload.objects if o.geometry_status == "no_representation"]
    assert len(absent) == 1
    assert absent[0].bbox is None


def test_bbox_partielle_est_refusee():
    """Une boîte à cinq bornes n'est pas une boîte."""
    doc = _doc()
    del doc["objects"][0]["bbox"]["z_max"]
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(doc)


def test_bbox_refuse_un_champ_inconnu():
    """``extra=forbid`` sur la boîte : ``width`` mal orthographié doit échouer,
    pas se ranger silencieusement à côté des vraies bornes."""
    doc = _doc()
    doc["objects"][0]["bbox"]["z_moy"] = 1.0
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(doc)


def test_aucun_champ_de_conformite_n_est_prevu():
    """Garde-fou d'intention : le contrat porte des mesures, pas des verdicts.

    Si un jour ``conforme`` / ``statut`` / ``seuil`` apparaît dans le modèle,
    c'est que le référentiel d'un client a fui dans un contrat partagé.
    """
    interdits = {"conforme", "conformite", "statut", "status", "seuil", "threshold", "verdict"}
    for model in (SpatialEvidenceV1, ObjectEvidence, SpaceEvidence, Containment):
        fuite = set(model.model_fields) & interdits
        assert not fuite, f"{model.__name__} porte {fuite}"


def test_document_non_objet_est_refuse():
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(["pas", "un", "objet"])


def test_created_at_non_iso_est_refuse():
    with pytest.raises(ContractValidationError):
        parse_spatial_evidence(_doc(created_at="hier"))
