import duckdb
import pandas as pd
from config import EXCEL_PATH

_conn: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _conn


def init_db() -> duckdb.DuckDBPyConnection:
    global _conn
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial;")

    _load_forces(conn)
    _load_sector_boundaries(conn)
    _load_settlements(conn)

    _conn = conn
    return conn


def _load_forces(conn: duckdb.DuckDBPyConnection):
    df = pd.read_excel(EXCEL_PATH, sheet_name="Forces")
    conn.register("_forces_raw", df)
    conn.execute("""
        CREATE TABLE forces AS
        SELECT
            id,
            name,
            normalized_name,
            longitude,
            latitude,
            timestamp,
            type,
            company,
            gdud,
            hativa,
            ST_GeomFromText(location_wkt) AS geom
        FROM _forces_raw
    """)
    conn.unregister("_forces_raw")


def _load_sector_boundaries(conn: duckdb.DuckDBPyConnection):
    df = pd.read_excel(EXCEL_PATH, sheet_name="Sector boundaries")
    conn.register("_sb_raw", df)
    conn.execute("""
        CREATE TABLE sector_boundaries AS
        SELECT
            ID AS id,
            name,
            eshelon_name,
            unit_name,
            lut,
            ST_GeomFromText(geometry_wkt) AS geom
        FROM _sb_raw
    """)
    conn.unregister("_sb_raw")


def _load_settlements(conn: duckdb.DuckDBPyConnection):
    df = pd.read_excel(EXCEL_PATH, sheet_name="Settlements")
    conn.register("_set_raw", df)
    conn.execute("""
        CREATE TABLE settlements AS
        SELECT
            id,
            name,
            country,
            type,
            area,
            ST_GeomFromText(geojson_position) AS geom,
            ST_Centroid(ST_GeomFromText(geojson_position)) AS centroid
        FROM _set_raw
    """)
    conn.unregister("_set_raw")
