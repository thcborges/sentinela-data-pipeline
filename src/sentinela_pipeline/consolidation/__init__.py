"""Consolidation, spatial deduplication and SQLite R*Tree compilation modules."""

from .deduplicator import SpatialDeduplicator, haversine_distance_meters
from .sqlite_builder import SQLiteRadarBuilder
from .dataset_exporter import DatasetExporter

__all__ = [
    "SpatialDeduplicator",
    "haversine_distance_meters",
    "SQLiteRadarBuilder",
    "DatasetExporter",
]
