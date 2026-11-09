"""Address cache manager using SHA-256 normalized hash for BigQuery & local persistence."""

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def normalize_address(address_text: str) -> str:
    """Normalizes address string: strips accents, removes special characters, uppercase."""
    if not address_text:
        return ""
    # Normalize unicode (NFD decomposes accents)
    nfkd = unicodedata.normalize("NFKD", address_text)
    ascii_text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Remove punctuation, keep alphanumeric and spaces
    cleaned = re.sub(r"[^\w\s]", " ", ascii_text)
    # Collapse multiple spaces and uppercase
    return " ".join(cleaned.split()).upper()


def compute_address_hash(address_text: str) -> str:
    """Computes deterministic SHA-256 hash of normalized address."""
    normalized = normalize_address(address_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class AddressCacheManager:
    """Manages address geocoding cache in memory and BigQuery."""

    def __init__(self, bq_client: Optional[Any] = None, table_id: Optional[str] = None) -> None:
        self.bq_client = bq_client
        self.table_id = table_id
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def get(self, address_text: str) -> Optional[Dict[str, Any]]:
        """Lookups coordinates for address from memory cache."""
        addr_hash = compute_address_hash(address_text)
        return self._memory_cache.get(addr_hash)

    def set(
        self,
        address_text: str,
        latitude: Optional[float],
        longitude: Optional[float],
        source: str = "CACHE",
        precision: str = "EXACT",
    ) -> None:
        """Stores resolved address in memory cache."""
        addr_hash = compute_address_hash(address_text)
        self._memory_cache[addr_hash] = {
            "address_hash": addr_hash,
            "raw_address": address_text,
            "normalized_address": normalize_address(address_text),
            "latitude": latitude,
            "longitude": longitude,
            "geocoding_source": source,
            "precision_level": precision,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }

    def load_from_records(self, records: List[Dict[str, Any]]) -> int:
        """Loads a list of existing cache records (e.g. from BigQuery query)."""
        loaded = 0
        for rec in records:
            addr_hash = rec.get("address_hash")
            if not addr_hash and rec.get("raw_address"):
                addr_hash = compute_address_hash(rec["raw_address"])
            if addr_hash:
                self._memory_cache[addr_hash] = rec
                loaded += 1
        return loaded

    def flush_to_bigquery(self, bq_client: Optional[Any] = None, table_id: Optional[str] = None) -> int:
        """Flushes in-memory cache rows to BigQuery table."""
        client = bq_client or self.bq_client
        target_table = table_id or self.table_id
        if not client or not target_table or not self._memory_cache:
            return 0

        rows_to_insert = list(self._memory_cache.values())
        try:
            errors = client.insert_rows_json(target_table, rows_to_insert)
            if errors:
                logger.error("Errors inserting cache rows to BigQuery: %s", errors)
                return 0
            return len(rows_to_insert)
        except Exception as exc:
            logger.error("Failed to flush cache to BigQuery: %s", exc)
            return 0

    @property
    def size(self) -> int:
        """Returns the number of cached addresses in memory."""
        return len(self._memory_cache)
