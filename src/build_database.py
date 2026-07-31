"""
Step 5: Build the governed spatial database.

Engine: DuckDB with the spatial extension (pinned to duckdb==1.5.5 --
RTree index support requires this; confirmed empirically, see commit
"Pin duckdb to 1.5.5"). Chosen over PostGIS because it ships as a single
embedded file with no server to stand up -- matters for "runs end to end
with no manual intervention" -- and over plain GeoPackage because DuckDB
is a real relational engine: it enforces declared PRIMARY KEY / FOREIGN
KEY constraints and supports spatial (RTree) indexes, neither of which
GeoPackage does natively.

NOTE on schema construction: DuckDB does not support adding PRIMARY KEY
or FOREIGN KEY constraints via ALTER TABLE (confirmed empirically --
raises "NotImplementedException: No support for that ALTER TABLE option
yet!"). Every table below is therefore built as: (1) read the raw source
into an unconstrained staging table, (2) CREATE TABLE with the real
schema, constraints declared inline on each column, (3) INSERT INTO ...
SELECT from staging, (4) drop staging. This is more verbose than
CREATE TABLE ... AS SELECT but is what the engine actually supports.

All geometry is EPSG:4326 (WGS84 lon/lat), confirmed for every source:
  - admin_boundaries.gpkg layers: declared 4326 in gpkg_spatial_ref_sys.
  - facility_personnel_scores.mif: independently verified via
    fiona.open(...).crs -> EPSG:4326 (see README "Key decisions").
  - facilities_with_scores.csv canonical_lon/canonical_lat: derived from
    the above two sources in Step 4, so also 4326.
This is a lon/lat CRS, unsuitable for area or distance measurement as-is
-- that reprojection happens in Step 6, not here. ST_Within point-in-
polygon containment is valid in any consistent CRS including 4326, so no
reprojection is needed for the ward-assignment spatial join below.

Output:
  - data/processed/facility_access.duckdb
  - outputs/logs/database_build_log.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import duckdb
import pandas as pd


def build():
    log = ["# Spatial Database Build Log\n"]

    if config.DUCKDB_PATH.exists():
        config.DUCKDB_PATH.unlink()
        log.append("- Removed existing database file to rebuild from scratch (idempotent run).\n")

    con = duckdb.connect(str(config.DUCKDB_PATH))
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")
    gpkg = str(config.F_ADMIN_BOUNDARIES_GPKG)

    # ---------------------------------------------------------------
    # states
    # ---------------------------------------------------------------
    con.execute(f"CREATE TABLE stg_states AS SELECT * FROM ST_Read('{gpkg}', layer='states')")
    con.execute("""
        CREATE TABLE states (
            state_code VARCHAR PRIMARY KEY,
            state_name VARCHAR,
            geom GEOMETRY
        )
    """)
    con.execute("INSERT INTO states SELECT state_code, state_name, geom FROM stg_states")
    con.execute("DROP TABLE stg_states")

    # ---------------------------------------------------------------
    # senatorial_districts
    # ---------------------------------------------------------------
    con.execute(f"CREATE TABLE stg_sen AS SELECT * FROM ST_Read('{gpkg}', layer='senatorial_districts')")
    con.execute("""
        CREATE TABLE senatorial_districts (
            sen_code VARCHAR PRIMARY KEY,
            sen_district VARCHAR,
            state_code VARCHAR REFERENCES states(state_code),
            geom GEOMETRY
        )
    """)
    con.execute("INSERT INTO senatorial_districts SELECT sen_code, sen_district, state_code, geom FROM stg_sen")
    con.execute("DROP TABLE stg_sen")

    # ---------------------------------------------------------------
    # lgas
    # ---------------------------------------------------------------
    con.execute(f"CREATE TABLE stg_lgas AS SELECT * FROM ST_Read('{gpkg}', layer='lgas')")
    con.execute("""
        CREATE TABLE lgas (
            lga_code VARCHAR PRIMARY KEY,
            lga_name VARCHAR,
            sen_code VARCHAR REFERENCES senatorial_districts(sen_code),
            state_code VARCHAR,
            geom GEOMETRY
        )
    """)
    con.execute("INSERT INTO lgas SELECT lga_code, lga_name, sen_code, state_code, geom FROM stg_lgas")
    con.execute("DROP TABLE stg_lgas")

    # ---------------------------------------------------------------
    # wards. population_source is merged in from ward_population.csv at load
    # time. NOTE: that csv has 14 nulls in total_population that the gpkg
    # wards layer does NOT have -- an earlier check wrongly reported the two
    # sources as "identical" (a fillna(0) masked a real NaN-vs-value
    # difference; see outputs/logs/population_reconciliation_correction.md
    # for the correction). The gpkg is used here as the authoritative,
    # complete population source; the csv contributes only the
    # population_source label, which is present for all 620 wards
    # regardless of whether that csv's own population figure was blank.
    # ---------------------------------------------------------------
    con.execute(f"CREATE TABLE stg_wards AS SELECT * FROM ST_Read('{gpkg}', layer='wards')")
    wp = pd.read_csv(config.F_WARD_POPULATION)[["ward_code", "population_source"]]
    con.register("wp_tmp", wp)
    con.execute("""
        CREATE TABLE wards (
            ward_code VARCHAR PRIMARY KEY,
            ward_name VARCHAR,
            lga_code VARCHAR REFERENCES lgas(lga_code),
            total_population BIGINT,
            population_under5 BIGINT,
            population_source VARCHAR,
            geom GEOMETRY
        )
    """)
    con.execute("""
        INSERT INTO wards
        SELECT sw.ward_code, sw.ward_name, sw.lga_code, sw.total_population,
               sw.population_under5, wp.population_source, sw.geom
        FROM stg_wards sw
        LEFT JOIN wp_tmp wp ON sw.ward_code = wp.ward_code
    """)
    con.execute("DROP TABLE stg_wards")

    n_states = con.execute("SELECT COUNT(*) FROM states").fetchone()[0]
    n_sen = con.execute("SELECT COUNT(*) FROM senatorial_districts").fetchone()[0]
    n_lgas = con.execute("SELECT COUNT(*) FROM lgas").fetchone()[0]
    n_wards = con.execute("SELECT COUNT(*) FROM wards").fetchone()[0]
    log.append(f"\n## Boundary layers (from admin_boundaries.gpkg, EPSG:4326)\n")
    log.append(f"- states: {n_states}, senatorial_districts: {n_sen}, "
               f"lgas: {n_lgas}, wards: {n_wards}. PK on each *_code, FK chain "
               f"wards -> lgas -> senatorial_districts -> states enforced.\n")
    log.append(f"- `wards.population_source` merged in from `ward_population.csv`. "
               f"Correction: an earlier check wrongly reported this csv's population "
               f"figures as identical to the gpkg's; the csv actually has 14 nulls in "
               f"total_population that the gpkg does not. The gpkg is used as the "
               f"authoritative, complete population source; only population_source is "
               f"taken from the csv. See outputs/logs/population_reconciliation_correction.md.\n")

    # ---------------------------------------------------------------
    # minimum_staffing_norms
    # ---------------------------------------------------------------
    con.execute(f"CREATE TABLE stg_norms AS SELECT * FROM read_csv_auto('{config.F_MIN_STAFFING_NORMS}')")
    con.execute("""
        CREATE TABLE minimum_staffing_norms (
            facility_type VARCHAR PRIMARY KEY,
            min_medical_officers BIGINT,
            min_nurses_midwives BIGINT,
            min_chews BIGINT,
            min_lab_scientists BIGINT,
            min_pharmacy_technicians BIGINT,
            adequacy_rule VARCHAR
        )
    """)
    con.execute("INSERT INTO minimum_staffing_norms SELECT * FROM stg_norms")
    con.execute("DROP TABLE stg_norms")
    log.append(f"\n## minimum_staffing_norms\n- {con.execute('SELECT COUNT(*) FROM minimum_staffing_norms').fetchone()[0]} rows, PK facility_type.\n")

    # ---------------------------------------------------------------
    # lga_senatorial_crosswalk: Step 2 reconciled artifact, audit trail only
    # ---------------------------------------------------------------
    xwalk_path = config.PROCESSED / "lga_sen_crosswalk.csv"
    con.execute(f"CREATE TABLE stg_xwalk AS SELECT * FROM read_csv_auto('{xwalk_path}')")
    con.execute("""
        CREATE TABLE lga_senatorial_crosswalk (
            state_name VARCHAR,
            lga_name_raw VARCHAR,
            lga_name_norm VARCHAR,
            sen_district VARCHAR,
            n_wards BIGINT,
            lga_code VARCHAR PRIMARY KEY,
            remarks VARCHAR
        )
    """)
    con.execute("INSERT INTO lga_senatorial_crosswalk SELECT * FROM stg_xwalk")
    con.execute("DROP TABLE stg_xwalk")
    log.append(f"\n## lga_senatorial_crosswalk (audit trail, Step 2 output)\n"
               f"- {con.execute('SELECT COUNT(*) FROM lga_senatorial_crosswalk').fetchone()[0]} rows, PK lga_code. "
               f"Not used operationally (the `lgas` table's sen_code, taken directly from "
               f"the boundary layer, is what facilities/wards actually join against) -- kept "
               f"as the documented, automated transformation of the source spreadsheet, "
               f"per the task requirement, with its full reconciliation log in "
               f"outputs/logs/crosswalk_reconciliation_log.md.\n")

    # ---------------------------------------------------------------
    # facilities: Step 4 output, geometry built, ward_code populated
    # afterward via spatial join (column exists from the start, just NULL
    # until the UPDATE below -- no ALTER TABLE needed).
    # ---------------------------------------------------------------
    fac_path = config.PROCESSED / "facilities_with_scores.csv"
    con.execute(f"CREATE TABLE stg_fac AS SELECT * FROM read_csv_auto('{fac_path}')")
    con.execute("""
        CREATE TABLE facilities (
            facility_id VARCHAR PRIMARY KEY,
            facility_name VARCHAR,
            facility_type VARCHAR REFERENCES minimum_staffing_norms(facility_type),
            ownership VARCHAR,
            ward_name_stated VARCHAR,
            lga_name_stated VARCHAR,
            sen_district_stated VARCHAR,
            state_name_stated VARCHAR,
            coord_status VARCHAR,
            geometry_source VARCHAR,
            geometry_note VARCHAR,
            med_officers DOUBLE,
            nurses_midwives DOUBLE,
            chews DOUBLE,
            lab_scientists DOUBLE,
            pharm_techs DOUBLE,
            personnel_score DOUBLE,
            sen_rank DOUBLE,
            canonical_lon DOUBLE,
            canonical_lat DOUBLE,
            geom GEOMETRY,
            ward_code VARCHAR REFERENCES wards(ward_code)
        )
    """)
    con.execute("""
        INSERT INTO facilities (
            facility_id, facility_name, facility_type, ownership,
            ward_name_stated, lga_name_stated, sen_district_stated, state_name_stated,
            coord_status, geometry_source, geometry_note,
            med_officers, nurses_midwives, chews, lab_scientists, pharm_techs,
            personnel_score, sen_rank, canonical_lon, canonical_lat, geom
        )
        SELECT
            facility_id, facility_name, facility_type, ownership,
            ward_name, lga_name, sen_district, state_name,
            coord_status, geometry_source, geometry_note,
            med_officers, nurses_midwives, chews, lab_scientists, pharm_techs,
            personnel_score, sen_rank, canonical_lon, canonical_lat,
            CASE WHEN canonical_lon IS NOT NULL AND canonical_lat IS NOT NULL
                 THEN ST_Point(canonical_lon, canonical_lat)
                 ELSE NULL END
        FROM stg_fac
    """)
    con.execute("DROP TABLE stg_fac")

    n_fac = con.execute("SELECT COUNT(*) FROM facilities").fetchone()[0]
    n_geom = con.execute("SELECT COUNT(*) FROM facilities WHERE geom IS NOT NULL").fetchone()[0]
    log.append(f"\n## facilities\n")
    log.append(f"- {n_fac} rows loaded, PK facility_id, FK facility_type -> "
               f"minimum_staffing_norms.\n")
    log.append(f"- {n_geom} have a usable geometry; {n_fac - n_geom} carry NULL geometry "
               f"(the 24 rows flagged `coord_status='missing_coordinates'` back in Step 3 -- "
               f"kept as attribute-only rows, never dropped, but necessarily excluded from "
               f"every spatial operation below and in Steps 6-8).\n")

    # Spatial join: point-in-polygon against wards.
    con.execute("""
        UPDATE facilities SET ward_code = w.ward_code
        FROM wards w
        WHERE facilities.geom IS NOT NULL AND ST_Within(facilities.geom, w.geom)
    """)
    n_assigned = con.execute("SELECT COUNT(*) FROM facilities WHERE ward_code IS NOT NULL").fetchone()[0]
    n_unassigned = con.execute(
        "SELECT COUNT(*) FROM facilities WHERE geom IS NOT NULL AND ward_code IS NULL"
    ).fetchone()[0]
    log.append(f"\n## Spatial ward assignment (point-in-polygon, ST_Within)\n")
    log.append(f"- {n_assigned} facilities assigned to a ward by falling inside its polygon.\n")
    log.append(f"- {n_unassigned} facilities have valid geometry but fall outside every ward "
               f"polygon (edge-of-boundary digitization gaps). Nearest-ward fallback applied "
               f"below rather than left unassigned.\n")

    n_fallback = 0
    if n_unassigned:
        unassigned_ids = con.execute("""
            SELECT facility_id FROM facilities
            WHERE geom IS NOT NULL AND ward_code IS NULL
        """).fetchdf()

        con.execute("""
            UPDATE facilities SET ward_code = (
                SELECT w.ward_code FROM wards w
                ORDER BY ST_Distance(facilities.geom, w.geom) ASC
                LIMIT 1
            )
            WHERE facilities.geom IS NOT NULL AND facilities.ward_code IS NULL
        """)
        n_fallback = len(unassigned_ids)
        log.append(f"- {n_fallback} resolved via nearest-ward fallback "
                   f"(ST_Distance to nearest ward polygon):\n")
        if n_fallback:
            id_list = ",".join("'" + x + "'" for x in unassigned_ids.facility_id)
            fb = con.execute(f"""
                SELECT f.facility_id, f.facility_name, w.ward_name
                FROM facilities f JOIN wards w ON f.ward_code = w.ward_code
                WHERE f.facility_id IN ({id_list})
            """).fetchdf()
            log.append("\n```\n" + fb.to_string(index=False) + "\n```\n")

    # Cross-check spatial assignment vs. the free-text ward_name_stated.
    n_ward_name_mismatch = con.execute("""
        SELECT COUNT(*) FROM facilities f
        JOIN wards w ON f.ward_code = w.ward_code
        WHERE f.ward_code IS NOT NULL
          AND upper(replace(replace(f.ward_name_stated, '-', ''), ' ', ''))
              != upper(replace(replace(w.ward_name, '-', ''), ' ', ''))
    """).fetchone()[0]
    n_ward_name_checked = con.execute(
        "SELECT COUNT(*) FROM facilities WHERE ward_code IS NOT NULL"
    ).fetchone()[0]
    log.append(f"\n## Cross-check: spatial ward assignment vs. stated ward_name\n")
    log.append(f"- Of {n_ward_name_checked} spatially assigned facilities, "
               f"{n_ward_name_mismatch} have a `ward_name_stated` that does not match "
               f"(after normalizing case/hyphens/spaces) the ward the point actually falls "
               f"in. Not auto-corrected, listed below for review.\n")

    if n_ward_name_mismatch:
        mismatches = con.execute("""
            SELECT f.facility_id, f.facility_name, f.ward_name_stated, w.ward_name AS ward_name_spatial
            FROM facilities f
            JOIN wards w ON f.ward_code = w.ward_code
            WHERE f.ward_code IS NOT NULL
              AND upper(replace(replace(f.ward_name_stated, '-', ''), ' ', ''))
                  != upper(replace(replace(w.ward_name, '-', ''), ' ', ''))
        """).fetchdf()
        log.append("\n```\n" + mismatches.to_string(index=False) + "\n```\n")

    # ---------------------------------------------------------------
    # Spatial indexes
    # ---------------------------------------------------------------
    for tbl in ["states", "senatorial_districts", "lgas", "wards", "facilities"]:
        con.execute(f"CREATE INDEX {tbl}_geom_idx ON {tbl} USING RTREE (geom)")
    log.append(f"\n## Spatial indexes\n- RTree index created on the geometry column of "
               f"every table (states, senatorial_districts, lgas, wards, facilities).\n")

    con.close()

    log_path = config.LOGS / "database_build_log.md"
    log_path.write_text("\n".join(log))
    print(f"Wrote {config.DUCKDB_PATH}")
    print(f"Wrote {log_path}")
    print(f"\nfacilities: {n_fac} total, {n_geom} with geometry, "
          f"{n_assigned} ward-assigned by containment, {n_fallback} by nearest-fallback")
    print(f"Ward name mismatch: {n_ward_name_mismatch} / {n_ward_name_checked}")


if __name__ == "__main__":
    build()
