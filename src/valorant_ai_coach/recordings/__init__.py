"""Private recording catalog: intake, splits, exposure, lineage and leakage guard (#62)."""

from .catalog import (
    ARTIFACT_KINDS,
    EXPOSURE_KINDS,
    PURPOSES,
    SPLITS,
    CatalogError,
    CatalogIntegrityError,
    LeakageError,
    RecordingCatalog,
    RegistrationResult,
    SplitImmutableError,
)

__all__ = [
    "ARTIFACT_KINDS",
    "EXPOSURE_KINDS",
    "PURPOSES",
    "SPLITS",
    "CatalogError",
    "CatalogIntegrityError",
    "LeakageError",
    "RecordingCatalog",
    "RegistrationResult",
    "SplitImmutableError",
]
