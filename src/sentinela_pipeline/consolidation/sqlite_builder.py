"""SQLite database compiler with native spatial R*Tree extension for Sentinela."""

from datetime import datetime, timezone
import os
import sqlite3
from typing import Any, Dict, List, Optional

# Mapping from POI type strings to Sentinela Flutter PoiType enum integer indexes
POI_TYPE_MAP = {
    "FIXED_RADAR": 1,
    "MOBILE_RADAR": 2,
    "TRAFFIC_LIGHT_RADAR": 3,
    "RED_LIGHT_CAMERA": 4,
    "ELECTRONIC_SPEED_BUMP": 5,
    "PHYSICAL_SPEED_BUMP": 6,
    "TOLL_BOOTH": 7,
    "FREE_FLOW_TOLL": 8,
    "HIGHWAY_PATROL": 9,
}


class SQLiteRadarBuilder:
    """Compiles consolidated POIs into Sentinela SQLite database with R*Tree indexing."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def initialize_schema(self, conn: sqlite3.Connection) -> None:
        """Initializes tables, metadata and R*Tree virtual table."""
        cursor = conn.cursor()

        # Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Consolidated POIs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pois (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed_limit INTEGER,
                direction INTEGER,
                road_name TEXT,
                operator TEXT,
                city TEXT,
                state TEXT,
                toll_fee_car REAL,
                toll_fee_truck REAL,
                source TEXT,
                created_at TEXT
            );
        """)

        # Spatial R*Tree virtual index
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS pois_index USING rtree(
                id,
                minX, maxX,
                minY, maxY
            );
        """)

        # Custom POIs table for user marks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_pois (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed_limit INTEGER,
                road_name TEXT,
                created_at TEXT NOT NULL
            );
        """)

        conn.commit()

    def build_database(
        self,
        consolidated_pois: List[Dict[str, Any]],
        source_summaries: Optional[Dict[str, int]] = None,
        schema_version: str = "1",
    ) -> int:
        """Writes consolidated POIs into the SQLite database and populates R*Tree."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)

        try:
            self.initialize_schema(conn)
            cursor = conn.cursor()

            insert_poi_sql = """
                INSERT INTO pois (
                    id, type, latitude, longitude, speed_limit, direction,
                    road_name, operator, city, state, toll_fee_car,
                    toll_fee_truck, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """

            insert_rtree_sql = """
                INSERT INTO pois_index (id, minX, maxX, minY, maxY)
                VALUES (?, ?, ?, ?, ?);
            """

            now_iso = datetime.now(timezone.utc).isoformat()
            poi_rows = []
            rtree_rows = []

            for idx, p in enumerate(consolidated_pois, start=1):
                lat = float(p["latitude"])
                lon = float(p["longitude"])
                poi_type_str = str(p.get("poi_type") or "FIXED_RADAR")
                poi_type_int = POI_TYPE_MAP.get(poi_type_str, 1)

                speed_limit = p.get("speed_limit")
                direction = p.get("direction")
                road = p.get("road_name") or p.get("rodovia") or p.get("rodovia_via") or ""
                operator = p.get("operator") or p.get("concessionaria") or ""
                city = p.get("city") or p.get("municipio") or ""
                state = p.get("state") or p.get("uf") or ""
                toll_car = p.get("tarifa_automovel") or p.get("toll_fee_car")
                toll_truck = p.get("tarifa_comercial") or p.get("toll_fee_truck")
                src = p.get("source") or "SENTINELA_DATA_PIPELINE"

                poi_rows.append((
                    idx, poi_type_int, lat, lon, speed_limit, direction,
                    road, operator, city, state, toll_car, toll_truck,
                    src, now_iso
                ))

                # Point bounding box for R*Tree (minX=lon, maxX=lon, minY=lat, maxY=lat)
                rtree_rows.append((idx, lon, lon, lat, lat))

            cursor.executemany(insert_poi_sql, poi_rows)
            cursor.executemany(insert_rtree_sql, rtree_rows)

            # Metadata
            meta_sql = "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?);"
            cursor.execute(meta_sql, ("total_count", str(len(poi_rows))))
            cursor.execute(meta_sql, ("last_updated", now_iso))
            cursor.execute(meta_sql, ("schema_version", schema_version))
            cursor.execute(meta_sql, ("source", "Sentinela Data Pipeline (BigQuery Lakehouse)"))

            if source_summaries:
                for src_key, src_count in source_summaries.items():
                    cursor.execute(meta_sql, (f"source_count_{src_key}", str(src_count)))

            conn.commit()
            return len(poi_rows)
        finally:
            conn.close()
