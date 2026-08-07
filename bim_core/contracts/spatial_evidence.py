"""Contrat ``spatial_evidence/v1`` — preuves géométriques neutres.

Produit par le MCP géométrique (IfcOpenShell) à partir d'une maquette IFC,
consommé par les profils AMO qui doivent trancher des contrôles portant sur des
dimensions, des contenances et des encombrements — et non sur des propriétés
IFC.

Ce contrat porte des **mesures**, jamais des verdicts. On n'y trouve ni statut
de conformité, ni seuil, ni référence à un référentiel client : un seuil
appartient au maître d'ouvrage qui l'écrit, une mesure appartient à la maquette.
Mélanger les deux rendrait le document inutilisable par un second AMO.

Trois précautions structurent le document :

- **Ce qui n'a pas été mesuré est compté.** ``selection`` dit quelles classes
  ont été balayées, ``coverage`` combien d'objets n'ont pas rendu de géométrie.
  Un objet sans représentation reste dans ``objects`` avec un
  ``geometry_status`` explicite : le supprimer ferait passer un défaut de
  maquette pour une absence de problème.
- **Aucun champ ne s'appelle « largeur ».** La largeur d'une pièce n'est pas une
  grandeur définie dès qu'elle n'est pas rectangulaire. Le contrat porte deux
  approximations nommées par leur méthode : ``min_rect_width_m`` (petit côté du
  rectangle englobant orienté) et ``inscribed_diameter_m`` (diamètre du plus
  grand cercle inscrit).

  Sur une pièce **convexe** les deux coïncident et valent la largeur. Sur une
  pièce non convexe, **aucune des deux n'est la largeur du passage le plus
  étroit** : mesuré sur un L à branches de 2,00 m, le rectangle rend 6,00 (il
  enveloppe le L entier) et le cercle inscrit 2,34 (il se loge dans l'angle, où
  il déborde en diagonale dans les deux branches). ``inscribed_diameter_m`` dit
  « la pièce fait au moins ce diamètre QUELQUE PART », jamais « au moins ça
  PARTOUT ». Trancher un contrôle de largeur de circulation demande un axe
  médian, qui n'est pas dans ce contrat.
- **Le rattachement d'un objet à un espace porte sa méthode.** Déclaré par
  l'IFC, déduit du centroïde, ou déduit du recouvrement : ces trois-là n'ont pas
  la même force de preuve, et un consommateur doit pouvoir refuser les deux
  derniers.

Contrat né versionné : **aucune forme legacy n'est tolérée**. Un document sans
``schema`` est refusé, en mode strict comme en mode permissif — il n'existe pas
de parc de fichiers antérieurs à protéger.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import ContractPayload, read_json_document
from .errors import ContractValidationError, MissingSchemaError, UnknownSchemaError

SCHEMA_SPATIAL_EVIDENCE_V1 = "spatial_evidence/v1"

#: État de la géométrie d'un objet — **pourquoi** une mesure manque, quand elle
#: manque. Quatre causes, qui n'appellent pas la même conclusion :
#:
#: - ``ok`` : empreinte et boîte englobante mesurées.
#: - ``no_representation`` : l'élément ne porte aucune forme dans le fichier.
#:   Lacune de maquette.
#: - ``shape_failed`` : l'élément déclare une forme, mais aucun maillage n'a pu
#:   en être tiré. Cas typique : un composant dont la matière vit dans ses
#:   sous-éléments, écartés par la sélection. C'est une conséquence du périmètre
#:   demandé, pas un défaut de la maquette — la conclusion à en tirer est
#:   d'élargir ``selection``, pas d'alerter le maître d'ouvrage.
#: - ``degenerate`` : maillage obtenu, boîte englobante disponible, mais aucune
#:   facette ne se projette en surface exploitable. Cas typique : une menuiserie,
#:   plaque verticale sans face horizontale. Les dimensions restent mesurables,
#:   l'empreinte non.
GEOMETRY_STATUS = ("ok", "no_representation", "shape_failed", "degenerate")

#: Comment le rattachement objet → espace a été établi, par force de preuve
#: décroissante. ``ifc_declared`` vient du fichier ; les deux autres sont déduits.
CONTAINMENT_METHODS = ("ifc_declared", "centroid_in_footprint", "footprint_overlap")


class BoundingBox(BaseModel):
    """Boîte englobante alignée sur les axes, en coordonnées monde (m)."""

    model_config = ConfigDict(extra="forbid")

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    @property
    def dx(self) -> float:
        return self.x_max - self.x_min

    @property
    def dy(self) -> float:
        return self.y_max - self.y_min

    @property
    def dz(self) -> float:
        return self.z_max - self.z_min


class Containment(BaseModel):
    """Rattachement d'un objet à un espace, avec la méthode qui l'a établi."""

    model_config = ConfigDict(extra="allow")

    space_global_id: str
    method: str
    overlap_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Part de l'empreinte de l'objet incluse dans celle de l'espace (0..1). "
            "Renseignée pour les méthodes déduites, absente pour `ifc_declared`."
        ),
    )

    @field_validator("method")
    @classmethod
    def _check_method(cls, value: str) -> str:
        if value not in CONTAINMENT_METHODS:
            raise ContractValidationError(
                f"`method` de rattachement inconnue : {value!r} "
                f"(attendu l'une de {CONTAINMENT_METHODS})."
            )
        return value


class ObjectEvidence(BaseModel):
    """Mesures géométriques d'un objet IFC quelconque."""

    model_config = ConfigDict(extra="allow")

    global_id: str
    ifc_class: str
    name: str | None = None
    type_name: str | None = None
    storey: str | None = None
    geometry_status: str = "ok"

    bbox: BoundingBox | None = None
    centroid: tuple[float, float, float] | None = None
    footprint_area_m2: float | None = Field(
        default=None,
        description="Aire de l'empreinte projetée sur XY — pas une surface de plancher.",
    )
    opening_width_m: float | None = Field(
        default=None,
        description=(
            "Largeur d'une menuiserie : diagonale horizontale de l'emprise. "
            "Renseignée pour les portes et fenêtres, `null` ailleurs."
        ),
    )
    opening_height_m: float | None = None
    is_external: bool | None = None
    container: Containment | None = None

    @field_validator("geometry_status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in GEOMETRY_STATUS:
            raise ContractValidationError(
                f"`geometry_status` inconnu : {value!r} (attendu l'une de {GEOMETRY_STATUS})."
            )
        return value


class SpaceEvidence(ObjectEvidence):
    """Mesures d'un ``IfcSpace`` — tout ``ObjectEvidence``, plus le contenu."""

    long_name: str | None = None
    room_type: str | None = Field(
        default=None,
        description="Type normalisé déduit du libellé (chambre, sejour…). Indicatif.",
    )
    zones: list[str] = Field(default_factory=list)

    area_declared_m2: float | None = Field(
        default=None, description="Surface lue dans les BaseQuantities de la pièce."
    )
    area_recalc_m2: float | None = Field(
        default=None, description="Aire de l'empreinte recalculée géométriquement."
    )
    min_rect_width_m: float | None = Field(
        default=None,
        description=(
            "Petit côté du rectangle englobant orienté. Exact si la pièce est "
            "convexe ; majore sinon."
        ),
    )
    inscribed_diameter_m: float | None = Field(
        default=None,
        description=(
            "Diamètre du plus grand cercle inscrit. Exact si la pièce est convexe ; "
            "sinon dit seulement que la pièce atteint ce diamètre QUELQUE PART — "
            "ce n'est PAS la largeur du passage le plus étroit."
        ),
    )
    clear_height_m: float | None = Field(
        default=None, description="Extension verticale de l'espace (z_max − z_min)."
    )

    contained_global_ids: list[str] = Field(
        default_factory=list,
        description="Objets rattachés à cet espace, toutes méthodes confondues.",
    )
    occupancy_area_m2: float | None = Field(
        default=None,
        description=(
            "Aire de l'empreinte de l'espace recouverte par ses objets rattachés "
            "(union, jamais une somme). Mesure d'encombrement, pas un verdict."
        ),
    )


class EvidenceSelection(BaseModel):
    """Périmètre balayé — ce qui n'y est pas n'a pas été mesuré."""

    model_config = ConfigDict(extra="allow")

    classes: list[str] = Field(default_factory=list)
    excluded_classes: list[str] = Field(default_factory=list)
    n_products_total: int | None = None
    n_selected: int | None = None


class EvidenceCoverage(BaseModel):
    """Combien d'objets ont réellement rendu une mesure, et pourquoi pas.

    ``n_without_bbox`` est ventilé par cause : agréger « pas de forme du tout »
    et « forme déléguée à des sous-éléments écartés » sous un unique compteur
    ferait passer un choix de périmètre pour un défaut de maquette.
    """

    model_config = ConfigDict(extra="allow")

    n_objects: int = 0
    n_with_bbox: int = 0
    n_without_bbox: int = 0
    n_no_representation: int = 0
    n_shape_failed: int = 0
    n_degenerate: int = 0
    n_spaces: int = 0
    n_spaces_with_footprint: int = 0
    n_contained: int = 0
    n_uncontained: int = 0
    n_contained_by_method: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Rattachements par méthode. Un document où tout vient de "
            "`footprint_overlap` n'a pas la même valeur de preuve qu'un document "
            "où l'IFC déclare les contenances."
        ),
    )


class SpatialEvidenceV1(ContractPayload):
    """Payload ``spatial_evidence/v1``."""

    schema_: str = Field(default=SCHEMA_SPATIAL_EVIDENCE_V1, alias="schema")
    selection: EvidenceSelection = Field(default_factory=EvidenceSelection)
    coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)
    objects: list[ObjectEvidence] = Field(default_factory=list)
    spaces: list[SpaceEvidence] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_")
    @classmethod
    def _check_schema(cls, value: str) -> str:
        if value != SCHEMA_SPATIAL_EVIDENCE_V1:
            raise ContractValidationError(
                f"`schema` invalide : {value!r} (attendu {SCHEMA_SPATIAL_EVIDENCE_V1!r})."
            )
        return value


def parse_spatial_evidence(
    doc: Any, *, strict: bool | None = None, origin: str | None = None
) -> SpatialEvidenceV1:
    """Valide un document ``spatial_evidence/v1`` déjà désérialisé.

    ``strict`` est accepté pour l'homogénéité des contrats mais n'a aucun effet :
    ce contrat n'a pas de forme legacy, donc un payload sans ``schema`` est
    refusé dans tous les modes. L'accepter « juste en permissif » ouvrirait la
    porte à un producteur qui n'appose pas son schéma.
    """
    del strict  # documenté ci-dessus : aucune tolérance à moduler
    where = f" ({origin})" if origin else ""
    if not isinstance(doc, dict):
        raise ContractValidationError(
            f"Le document doit être un objet JSON, reçu {type(doc).__name__}{where}."
        )
    if "schema" not in doc:
        raise MissingSchemaError(
            f"Payload sans `schema`{where} refusé : {SCHEMA_SPATIAL_EVIDENCE_V1!r} est "
            "né versionné et n'admet aucune forme legacy."
        )
    if doc["schema"] != SCHEMA_SPATIAL_EVIDENCE_V1:
        raise UnknownSchemaError(
            f"Schéma non reconnu : {doc['schema']!r}{where} — "
            f"attendu {SCHEMA_SPATIAL_EVIDENCE_V1!r}."
        )
    try:
        return SpatialEvidenceV1.model_validate(doc)
    except ContractValidationError:
        raise
    except ValueError as exc:
        raise ContractValidationError(
            f"Payload {SCHEMA_SPATIAL_EVIDENCE_V1!r} invalide{where} : {exc}"
        ) from exc


def load_spatial_evidence(path: str, *, strict: bool | None = None) -> SpatialEvidenceV1:
    """Lit et valide un fichier de preuves géométriques."""
    return parse_spatial_evidence(read_json_document(path), strict=strict, origin=str(path))


__all__ = [
    "CONTAINMENT_METHODS",
    "GEOMETRY_STATUS",
    "SCHEMA_SPATIAL_EVIDENCE_V1",
    "BoundingBox",
    "Containment",
    "EvidenceCoverage",
    "EvidenceSelection",
    "ObjectEvidence",
    "SpaceEvidence",
    "SpatialEvidenceV1",
    "load_spatial_evidence",
    "parse_spatial_evidence",
]
