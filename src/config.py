"""
Central path and constant configuration for the Q2 pipeline.

All scripts import paths from here rather than hardcoding them, so the
pipeline can be run from any working directory and so there is a single
place to change locations.
"""

from pathlib import Path

# Repo root = parent of this file's parent (src/ -> repo root)
ROOT = Path(__file__).resolve().parent.parent

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
LOGS = OUTPUTS / "logs"
MAPS = OUTPUTS / "maps"
TABLES = OUTPUTS / "tables"
DOCS = ROOT / "docs"

# Raw input files
F_HEALTH_FACILITIES = RAW / "health_facilities.csv"
F_MIN_STAFFING_NORMS = RAW / "minimum_staffing_norms.csv"
F_WARD_POPULATION = RAW / "ward_population.csv"
F_SCORES_MIF = RAW / "facility_personnel_scores.mif"
F_SCORES_MID = RAW / "facility_personnel_scores.mid"
F_LGA_SEN_XLSX = RAW / "LGA_SEN_Districts.xlsx"
F_ADMIN_BOUNDARIES_GPKG = RAW / "admin_boundaries.gpkg"
F_ROAD_NETWORK = RAW / "road_network.geojson"

# The single spatially-enabled database the whole pipeline builds into.
# DuckDB with the spatial extension: a real relational engine (declared
# PK/FK constraints, typed columns, indexable) that ships as a single
# embedded file, so "runs end to end with no manual intervention" doesn't
# require standing up a PostGIS server. See docs/methodological_note.md
# for the fuller justification of this choice over PostGIS/GeoPackage.
DUCKDB_PATH = PROCESSED / "facility_access.duckdb"

for d in (PROCESSED, LOGS, MAPS, TABLES):
    d.mkdir(parents=True, exist_ok=True)
