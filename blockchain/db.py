"""
TruthChain Off-Chain Database Layer (Neon PostgreSQL)
=====================================================
Stores full off-chain assessment records, prediction payloads, image metadata,
and blockchain commitment receipts.

Uses Neon PostgreSQL when available, with automatic SQLite / in-memory fallback
to ensure zero disruption in any development or offline environment.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default Neon PostgreSQL connection string
DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_zW8oQAj7SBuK@ep-fancy-cell-ay3onbd2-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# Local fallback SQLite path
# blockchain/db.py -> .parent = blockchain/, .parent.parent = project root
_LOCAL_FALLBACK_DB = (
    Path(__file__).resolve().parent.parent / "database"
)

class DatabaseManager:
    """
    Manages off-chain persistence for TruthChain assessments.
    Supports Neon PostgreSQL and SQLite local fallback.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or DEFAULT_DATABASE_URL
        self._pg_conn = None
        self._driver_type = "none"
        self._in_memory_cache: Dict[str, Dict[str, Any]] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Attempt connection to Neon PostgreSQL; fallback to SQLite if needed."""
        # Try psycopg2 or psycopg3
        connected = False
        try:
            import psycopg2  # type: ignore[import]
            from psycopg2.extras import RealDictCursor  # type: ignore[import]
            self._pg_conn = psycopg2.connect(self.database_url)
            self._pg_conn.autocommit = True
            self._driver_type = "psycopg2"
            connected = True
            logger.info("Connected to Neon PostgreSQL via psycopg2")
        except Exception as err1:
            logger.info("psycopg2 connection not established: %s. Trying psycopg...", err1)
            try:
                import psycopg  # type: ignore[import]
                self._pg_conn = psycopg.connect(self.database_url, autocommit=True)
                self._driver_type = "psycopg3"
                connected = True
                logger.info("Connected to Neon PostgreSQL via psycopg3")
            except Exception as err2:
                logger.warning(
                    "PostgreSQL drivers unavailable or direct network connection failed (%s, %s). Using SQLite local fallback.",
                    err1, err2
                )
                self._driver_type = "sqlite"

        self._create_tables()

    def _create_tables(self) -> None:
        """Create the assessments table if it doesn't already exist."""
        if self._driver_type in ("psycopg2", "psycopg3") and self._pg_conn:
            try:
                with self._pg_conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS assessments (
                            record_id VARCHAR(64) PRIMARY KEY,
                            vehicle_id VARCHAR(64),
                            image_hash VARCHAR(64) NOT NULL,
                            image_storage_uri TEXT,
                            prediction_hash VARCHAR(64) NOT NULL,
                            canonical_prediction JSONB,
                            model_version VARCHAR(128) NOT NULL,
                            blockchain_tx VARCHAR(128),
                            blockchain_block BIGINT,
                            blockchain_network VARCHAR(64),
                            blockchain_verified BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE INDEX IF NOT EXISTS idx_assessments_image_hash ON assessments(image_hash);
                        CREATE INDEX IF NOT EXISTS idx_assessments_pred_hash ON assessments(prediction_hash);
                    """)
                logger.info("Neon PostgreSQL tables initialized successfully")
                return
            except Exception as e:
                logger.warning("Failed to initialize Neon PostgreSQL tables: %s. Switching to SQLite fallback.", e)
                self._driver_type = "sqlite"

        # SQLite Fallback initialization
        try:
            _LOCAL_FALLBACK_DB.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(_LOCAL_FALLBACK_DB) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS assessments (
                        record_id TEXT PRIMARY KEY,
                        vehicle_id TEXT,
                        image_hash TEXT NOT NULL,
                        image_storage_uri TEXT,
                        prediction_hash TEXT NOT NULL,
                        canonical_prediction TEXT,
                        model_version TEXT NOT NULL,
                        blockchain_tx TEXT,
                        blockchain_block INTEGER,
                        blockchain_network TEXT,
                        blockchain_verified INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            logger.info("SQLite local fallback database initialized at %s", _LOCAL_FALLBACK_DB)
        except Exception as e:
            logger.warning("SQLite initialization error: %s. Using in-memory fallback.", e)
            self._driver_type = "memory"

    def save_assessment(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert or update a complete TruthChain assessment record.
        """
        record_id = record.get("record_id")
        vehicle_id = record.get("vehicle_id", "V-UNSPECIFIED")
        image_info = record.get("image", {})
        image_hash = image_info.get("sha256", "")
        image_uri = image_info.get("storage_uri", "")

        vision_info = record.get("vision", {})
        model_version = vision_info.get("model", "TruthChain Vision ResNet-50")
        canonical_pred = record.get("canonical_prediction", vision_info)
        prediction_hash = record.get("blockchain", {}).get("prediction_hash", "")

        bc_info = record.get("blockchain", {})
        tx_hash = bc_info.get("transaction", "")
        block_num = bc_info.get("block_number", 0)
        network = bc_info.get("network", "EVM Audit Layer")
        verified = bc_info.get("verified", True)
        created_at = record.get("created_at", datetime.utcnow().isoformat())

        # Always update in-memory cache
        self._in_memory_cache[record_id] = record

        # Persist to Neon PostgreSQL if connected
        if self._driver_type in ("psycopg2", "psycopg3") and self._pg_conn:
            try:
                with self._pg_conn.cursor() as cur:
                    pred_json = json.dumps(canonical_pred)
                    cur.execute("""
                        INSERT INTO assessments (
                            record_id, vehicle_id, image_hash, image_storage_uri,
                            prediction_hash, canonical_prediction, model_version,
                            blockchain_tx, blockchain_block, blockchain_network,
                            blockchain_verified, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (record_id) DO UPDATE SET
                            blockchain_tx = EXCLUDED.blockchain_tx,
                            blockchain_block = EXCLUDED.blockchain_block,
                            blockchain_verified = EXCLUDED.blockchain_verified;
                    """, (
                        record_id, vehicle_id, image_hash, image_uri,
                        prediction_hash, pred_json, model_version,
                        tx_hash, block_num, network, verified
                    ))
                return record
            except Exception as e:
                logger.warning("Neon PostgreSQL save failed: %s. Writing to SQLite fallback.", e)

        # Fallback to SQLite
        try:
            with sqlite3.connect(_LOCAL_FALLBACK_DB) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO assessments (
                        record_id, vehicle_id, image_hash, image_storage_uri,
                        prediction_hash, canonical_prediction, model_version,
                        blockchain_tx, blockchain_block, blockchain_network,
                        blockchain_verified, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id, vehicle_id, image_hash, image_uri,
                    prediction_hash, json.dumps(canonical_pred), model_version,
                    tx_hash, block_num, network, 1 if verified else 0, created_at
                ))
        except Exception as e:
            logger.warning("SQLite fallback save failed: %s", e)

        return record

    def get_assessment(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve assessment record by ID."""
        # Check in-memory cache first
        if record_id in self._in_memory_cache:
            return self._in_memory_cache[record_id]

        # Query Neon PostgreSQL
        if self._driver_type in ("psycopg2", "psycopg3") and self._pg_conn:
            try:
                with self._pg_conn.cursor() as cur:
                    cur.execute("""
                        SELECT record_id, vehicle_id, image_hash, image_storage_uri,
                               prediction_hash, canonical_prediction, model_version,
                               blockchain_tx, blockchain_block, blockchain_network,
                               blockchain_verified, created_at
                        FROM assessments WHERE record_id = %s
                    """, (record_id,))
                    row = cur.fetchone()
                    if row:
                        return self._format_db_row(row)
            except Exception as e:
                logger.warning("Neon PostgreSQL query failed: %s", e)

        # Query SQLite
        try:
            with sqlite3.connect(_LOCAL_FALLBACK_DB) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM assessments WHERE record_id = ?", (record_id,))
                row = cur.fetchone()
                if row:
                    return self._format_sqlite_row(dict(row))
        except Exception as e:
            logger.warning("SQLite query failed: %s", e)

        return None

    def list_assessments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent assessments."""
        results = []
        if self._driver_type in ("psycopg2", "psycopg3") and self._pg_conn:
            try:
                with self._pg_conn.cursor() as cur:
                    cur.execute("""
                        SELECT record_id, vehicle_id, image_hash, image_storage_uri,
                               prediction_hash, canonical_prediction, model_version,
                               blockchain_tx, blockchain_block, blockchain_network,
                               blockchain_verified, created_at
                        FROM assessments ORDER BY created_at DESC LIMIT %s
                    """, (limit,))
                    rows = cur.fetchall()
                    for r in rows:
                        results.append(self._format_db_row(r))
                    return results
            except Exception as e:
                logger.warning("Neon PostgreSQL list failed: %s", e)

        try:
            with sqlite3.connect(_LOCAL_FALLBACK_DB) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM assessments ORDER BY created_at DESC LIMIT ?", (limit,))
                for row in cur.fetchall():
                    results.append(self._format_sqlite_row(dict(row)))
                if results:
                    return results
        except Exception as e:
            logger.warning("SQLite list failed: %s", e)

        # In-memory fallback
        return list(self._in_memory_cache.values())[:limit]

    def _format_db_row(self, row: tuple) -> Dict[str, Any]:
        """Format PostgreSQL tuple into canonical TruthChain record dict."""
        (record_id, vehicle_id, image_hash, image_uri,
         pred_hash, canon_pred, model_ver,
         tx, block, net, verified, created_at) = row

        pred_obj = canon_pred if isinstance(canon_pred, dict) else json.loads(canon_pred or "{}")

        return {
            "record_id": record_id,
            "vehicle_id": vehicle_id,
            "image": {
                "storage_uri": image_uri,
                "sha256": image_hash,
            },
            "vision": {
                "model": model_ver,
                "detections": pred_obj.get("detected_damages", []),
                "probabilities": pred_obj.get("probabilities", {}),
                "thresholds": pred_obj.get("thresholds", {}),
            },
            "canonical_prediction": pred_obj,
            "blockchain": {
                "network": net,
                "transaction": tx,
                "block_number": block,
                "prediction_hash": pred_hash,
                "image_hash": image_hash,
                "verified": bool(verified),
            },
            "created_at": str(created_at),
        }

    def _format_sqlite_row(self, row_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Format SQLite row dict into canonical TruthChain record dict."""
        pred_raw = row_dict.get("canonical_prediction", "{}")
        pred_obj = json.loads(pred_raw) if isinstance(pred_raw, str) else (pred_raw or {})

        return {
            "record_id": row_dict.get("record_id"),
            "vehicle_id": row_dict.get("vehicle_id"),
            "image": {
                "storage_uri": row_dict.get("image_storage_uri"),
                "sha256": row_dict.get("image_hash"),
            },
            "vision": {
                "model": row_dict.get("model_version"),
                "detections": pred_obj.get("detected_damages", []),
                "probabilities": pred_obj.get("probabilities", {}),
                "thresholds": pred_obj.get("thresholds", {}),
            },
            "canonical_prediction": pred_obj,
            "blockchain": {
                "network": row_dict.get("blockchain_network"),
                "transaction": row_dict.get("blockchain_tx"),
                "block_number": row_dict.get("blockchain_block"),
                "prediction_hash": row_dict.get("prediction_hash"),
                "image_hash": row_dict.get("image_hash"),
                "verified": bool(row_dict.get("blockchain_verified")),
            },
            "created_at": str(row_dict.get("created_at")),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return status and active database provider info."""
        return {
            "active_driver": self._driver_type,
            "is_postgres": self._driver_type in ("psycopg2", "psycopg3"),
            "database_target": "Neon PostgreSQL Cloud" if self._driver_type in ("psycopg2", "psycopg3") else "Local SQLite Fallback",
            "fallback_db_path": str(_LOCAL_FALLBACK_DB) if self._driver_type == "sqlite" else None,
        }


# Module singleton
_db_manager: Optional[DatabaseManager] = None

def get_db() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
