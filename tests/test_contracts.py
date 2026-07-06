"""Smoke tests des contrats bim-core : import + instanciation minimale.

Ces tests garantissent que le package est autonome (pas de dépendance métier)
et que les types se construisent. La non-régression fonctionnelle complète
reste couverte par la suite d'``audit-bim-i3f`` (parité vs legacy-i3f-mcp-v1.0).
"""

from __future__ import annotations

import bim_core as bc


def test_public_api_exported():
    for name in bc.__all__:
        assert hasattr(bc, name), f"{name} manquant dans bim_core"


def test_finding_roundtrip():
    f = bc.Finding(
        theme=bc.Theme.CLASSIFICATION,
        severity=bc.Severity.HIGH,
        error_type=bc.ErrorType.CLASSIFICATION_MISSING,
        element_uuid="abc",
        ifc_type="IfcWall",
        name="Mur R+1",
    )
    data = f.model_dump(mode="json")
    assert bc.Finding.model_validate(data) == f
    assert f.short_label() == "IfcWall — Mur R+1"


def test_finding_field_path_optional_default_none():
    # Rétro-compatible : field_path est optionnel, None par défaut, et présent
    # dans le dump (contrat neutre exploitable par les consommateurs).
    f = bc.Finding(
        theme=bc.Theme.NAMING_ZONE,
        severity=bc.Severity.HIGH,
        error_type=bc.ErrorType.NAMING_MISSING,
    )
    assert f.field_path is None
    assert "field_path" in f.model_dump()


def test_finding_field_path_roundtrip():
    f = bc.Finding(
        theme=bc.Theme.NAMING_ZONE,
        severity=bc.Severity.MEDIUM,
        error_type=bc.ErrorType.NAMING_NOT_IN_LIST,
        element_uuid="z1",
        ifc_type="IfcZone",
        field_path="IfcZone.ObjectType",
    )
    data = f.model_dump(mode="json")
    assert data["field_path"] == "IfcZone.ObjectType"
    assert bc.Finding.model_validate(data) == f


def test_severity_ordered():
    assert bc.Severity.ordered()[0] is bc.Severity.CRITICAL
    assert bc.Severity.ordered()[-1] is bc.Severity.INFO


def test_bim_object_helpers():
    obj = bc.BimObject(
        uuid="u1",
        ifc_type="IfcDoor",
        properties={"Pset_DoorCommon.FireRating": "EI30"},
        classifications=[bc.ClassificationRef(code="B2010.10", system="uniformat")],
    )
    assert obj.has_property("Pset_DoorCommon.FireRating")
    assert obj.get_property("FireRating") == "EI30"
    assert obj.has_classification(system="uniformat")
    assert obj.classifications[0].level_3 == "B2010"


def test_object_filter_validation():
    of = bc.ObjectFilter(ifc_types=["IfcWall"], has_any_classification=False)
    assert of.limit == bc.DEFAULT_LIMIT
    assert bc.ObjectFilter.model_validate(of.model_dump()) == of


def test_write_plan_defaults():
    plan = bc.WritePlan(kind=bc.WritePlanKind.BCF_TOPICS)
    assert plan.requires_confirm is True
    assert plan.plan_id
    res = bc.ActionResult(plan_id=plan.plan_id, kind=plan.kind, succeeded=3)
    assert res.succeeded == 3


def test_model_snapshot_index():
    snap = bc.ModelSnapshot(
        spaces=[{"uuid": "s1", "name": "CHAMBRE"}],
        elements=[{"uuid": "e1", "type": "IfcWall"}],
    ).index()
    assert snap.of_class("IfcWall")[0]["uuid"] == "e1"
    assert snap.element_by_uuid["s1"]["type"] == "IfcSpace"
    assert snap.summary()["n_spaces"] == 1
