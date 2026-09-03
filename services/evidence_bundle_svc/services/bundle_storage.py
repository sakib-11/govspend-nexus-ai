"""Bundle storage — persist, retrieve, query, and archive evidence bundles."""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from ..models.evidence_bundle import (
    EvidenceBundle,
    BundleStatus,
    BundleReference,
    EvidenceItem,
    EvidenceSource,
)
from ..utils.serialization import BundleSerializer
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BundleStorage:
    """Store and retrieve evidence bundles.

    When a DB pool is available, bundles are persisted to the
    ``evidence_bundles`` table (full JSON blob + individual evidence items
    for querying).  Otherwise, an in-memory dict serves as a local cache.
    """

    def __init__(self, db_pool=None, config=None):
        self.db_pool = db_pool
        self.config = config
        # Fallback in-memory store for standalone / testing
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    # ── Store ─────────────────────────────────────────────────────

    async def store_bundle(
        self,
        bundle: EvidenceBundle,
        store_raw: bool = True,
    ) -> BundleReference:
        """Persist an assembled bundle to storage."""
        if self.db_pool:
            ref = await self._store_to_db(bundle, store_raw)
        else:
            ref = self._store_to_memory(bundle)

        bundle.mark_stored(ref.storage_location)

        logger.info(
            "Stored bundle %s for tx %s — %d bytes, location=%s",
            bundle.bundle_id,
            bundle.transaction_id,
            bundle.size_bytes,
            ref.storage_location,
        )

        return ref

    async def store_bundles_bulk(
        self,
        bundles: Dict[str, EvidenceBundle],
    ) -> Dict[str, BundleReference]:
        """Store multiple bundles."""
        refs: Dict[str, BundleReference] = {}
        for tx_id, bundle in bundles.items():
            if bundle.status == BundleStatus.ERROR:
                logger.warning("Skipping error bundle for %s", tx_id)
                continue
            ref = await self.store_bundle(bundle)
            refs[tx_id] = ref
        return refs

    # ── Retrieve ──────────────────────────────────────────────────

    async def retrieve_bundle(
        self,
        bundle_id: str,
        include_raw: bool = True,
    ) -> Optional[EvidenceBundle]:
        """Retrieve a full bundle by ID."""
        if self.db_pool:
            return await self._retrieve_from_db(bundle_id, include_raw)
        return self._retrieve_from_memory(bundle_id)

    async def retrieve_by_transaction(
        self,
        transaction_id: str,
    ) -> Optional[EvidenceBundle]:
        """Retrieve the latest bundle for a given transaction."""
        if self.db_pool:
            rows = await self._query_db(transaction_id=transaction_id, limit=1)
            if rows:
                return await self.retrieve_bundle(rows[0]["bundle_id"])

        # Memory fallback — scan
        for bundle_data in self._memory_store.values():
            if bundle_data.get("transaction_id") == transaction_id:
                return BundleSerializer.from_db_row(bundle_data)
        return None

    # ── Query ─────────────────────────────────────────────────────

    async def query_bundles(
        self,
        transaction_id: Optional[str] = None,
        risk_tier: Optional[str] = None,
        detector_types: Optional[List[str]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: Optional[BundleStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query bundles with filters — returns lightweight summaries."""
        if self.db_pool:
            return await self._query_db(
                transaction_id=transaction_id,
                risk_tier=risk_tier,
                detector_types=detector_types,
                from_date=from_date,
                to_date=to_date,
                status=status,
                limit=limit,
                offset=offset,
            )

        # Memory fallback
        results = []
        for bd in self._memory_store.values():
            if transaction_id and bd.get("transaction_id") != transaction_id:
                continue
            if risk_tier and bd.get("risk_tier") != risk_tier:
                continue
            if status and bd.get("status") != status.value:
                continue
            results.append(bd)

        return results[offset : offset + limit]

    # ── Archive / cleanup ─────────────────────────────────────────

    async def archive_bundle(
        self,
        bundle_id: str,
        archive_reason: str = "retention_policy",
    ) -> bool:
        """Soft-delete a bundle by transitioning to ARCHIVED status."""
        if self.db_pool:
            return await self._archive_in_db(bundle_id, archive_reason)

        if bundle_id in self._memory_store:
            self._memory_store[bundle_id]["status"] = "ARCHIVED"
            self._memory_store[bundle_id]["archived_at"] = (
                datetime.now(timezone.utc).isoformat()
            )
            return True
        return False

    async def delete_old_bundles(self, days: int = 365) -> int:
        """Delete bundles older than ``days`` that are already archived."""
        if self.db_pool:
            return await self._delete_old_from_db(days)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        to_remove = []
        for bid, bd in self._memory_store.items():
            created = bd.get("created_at", "")
            if isinstance(created, str) and bd.get("status") == "ARCHIVED":
                try:
                    created_dt = datetime.fromisoformat(created)
                    if created_dt < cutoff:
                        to_remove.append(bid)
                except ValueError:
                    pass

        for bid in to_remove:
            del self._memory_store[bid]
        return len(to_remove)

    # ── Stats ─────────────────────────────────────────────────────

    async def get_stats(self) -> Dict[str, Any]:
        """Aggregate bundle statistics."""
        if self.db_pool:
            return await self._stats_from_db()

        total = len(self._memory_store)
        tiers: Dict[str, int] = {}
        risk_scores = []
        for bd in self._memory_store.values():
            tier = bd.get("risk_tier", "UNKNOWN")
            tiers[tier] = tiers.get(tier, 0) + 1
            rs = bd.get("risk_score")
            if rs is not None:
                risk_scores.append(float(rs))

        return {
            "total_bundles": total,
            "unique_transactions": len(
                {bd.get("transaction_id") for bd in self._memory_store.values()}
            ),
            "avg_risk_score": sum(risk_scores) / len(risk_scores) if risk_scores else 0,
            "tier_counts": tiers,
        }

    # ══════════════════════════════════════════════════════════════
    # Database implementations
    # ══════════════════════════════════════════════════════════════

    async def _store_to_db(
        self, bundle: EvidenceBundle, store_raw: bool
    ) -> BundleReference:
        """INSERT bundle into evidence_bundles table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO evidence_bundles (
                    bundle_id, transaction_id, version, status, bundle_format,
                    bundle_data, weights_version, risk_score, risk_tier,
                    confidence_factor, detector_types, evidence_count,
                    size_bytes, storage_checksum, tags, metadata,
                    assembled_at, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19
                )
                ON CONFLICT (bundle_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    bundle_data = EXCLUDED.bundle_data,
                    risk_score = EXCLUDED.risk_score,
                    risk_tier = EXCLUDED.risk_tier,
                    updated_at = EXCLUDED.updated_at
                """,
                bundle.bundle_id,
                bundle.transaction_id,
                bundle.version,
                bundle.status.value,
                bundle.format.value,
                bundle.to_json() if store_raw else None,
                bundle.weights_version,
                bundle.risk_score,
                bundle.risk_tier,
                bundle.confidence_factor,
                bundle.get_detector_types(),
                bundle.get_evidence_count(),
                bundle.size_bytes,
                bundle.storage_checksum,
                bundle.tags,
                json.dumps(bundle.metadata, default=str),
                bundle.assembled_at,
                bundle.created_at,
                bundle.updated_at,
            )

            # Store individual evidence items for granular querying
            all_items = bundle.get_all_evidence_items()
            if all_items:
                rows = BundleSerializer.evidence_items_to_db_rows(
                    bundle.bundle_id, all_items
                )
                await conn.executemany(
                    """
                    INSERT INTO bundle_evidence_items (
                        bundle_id, evidence_id, source, source_type,
                        confidence, relevance_score, data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (bundle_id, evidence_id) DO NOTHING
                    """,
                    rows,
                )

        location = f"db://evidence_bundles/{bundle.bundle_id}"
        return BundleReference(
            bundle_id=bundle.bundle_id,
            transaction_id=bundle.transaction_id,
            storage_location=location,
            storage_checksum=bundle.storage_checksum or "",
            size_bytes=bundle.size_bytes,
            created_at=bundle.created_at,
            metadata={"version": bundle.version},
        )

    async def _retrieve_from_db(
        self, bundle_id: str, include_raw: bool
    ) -> Optional[EvidenceBundle]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT bundle_id, transaction_id, version, status,
                       bundle_format, bundle_data, weights_version,
                       risk_score, risk_tier, confidence_factor,
                       detector_types, evidence_count, size_bytes,
                       storage_checksum, tags, metadata,
                       assembled_at, created_at, updated_at
                FROM evidence_bundles
                WHERE bundle_id = $1
                """,
                bundle_id,
            )

        if not row:
            return None

        return BundleSerializer.from_db_row(dict(row))

    async def _query_db(
        self,
        transaction_id: Optional[str] = None,
        risk_tier: Optional[str] = None,
        detector_types: Optional[List[str]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: Optional[BundleStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if transaction_id:
            conditions.append(f"transaction_id = ${idx}")
            params.append(transaction_id)
            idx += 1
        if risk_tier:
            conditions.append(f"risk_tier = ${idx}")
            params.append(risk_tier)
            idx += 1
        if detector_types:
            conditions.append(f"detector_types && ${idx}")
            params.append(detector_types)
            idx += 1
        if from_date:
            conditions.append(f"assembled_at >= ${idx}")
            params.append(from_date)
            idx += 1
        if to_date:
            conditions.append(f"assembled_at <= ${idx}")
            params.append(to_date)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status.value)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT bundle_id, transaction_id, risk_score, risk_tier,
                   detector_types, evidence_count, size_bytes, tags,
                   assembled_at, status
            FROM evidence_bundles
            {where}
            ORDER BY assembled_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def _archive_in_db(self, bundle_id: str, reason: str) -> bool:
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE evidence_bundles
                SET status = 'ARCHIVED', archived_at = NOW(),
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'),
                        '{archive_reason}',
                        to_jsonb($2::text)
                    ),
                    updated_at = NOW()
                WHERE bundle_id = $1 AND status != 'ARCHIVED'
                """,
                bundle_id,
                reason,
            )
            return result.split()[-1] == "1"

    async def _delete_old_from_db(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM evidence_bundles
                WHERE created_at < $1
                AND status = 'ARCHIVED'
                """,
                cutoff,
            )
            return int(result.split()[-1])

    async def _stats_from_db(self) -> Dict[str, Any]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total_bundles,
                    COUNT(DISTINCT transaction_id) AS unique_transactions,
                    COALESCE(AVG(risk_score), 0) AS avg_risk_score,
                    COALESCE(MAX(risk_score), 0) AS max_risk_score
                FROM evidence_bundles
                WHERE status != 'ARCHIVED'
                """
            )
            tier_rows = await conn.fetch(
                """
                SELECT risk_tier, COUNT(*) AS cnt
                FROM evidence_bundles
                WHERE status != 'ARCHIVED'
                GROUP BY risk_tier
                """
            )

        return {
            "total_bundles": row["total_bundles"],
            "unique_transactions": row["unique_transactions"],
            "avg_risk_score": float(row["avg_risk_score"]),
            "max_risk_score": float(row["max_risk_score"]),
            "tier_counts": {r["risk_tier"]: r["cnt"] for r in tier_rows},
        }

    # ══════════════════════════════════════════════════════════════
    # In-memory implementations (testing / standalone)
    # ══════════════════════════════════════════════════════════════

    def _store_to_memory(self, bundle: EvidenceBundle) -> BundleReference:
        blob = BundleSerializer.to_db_row(bundle)
        self._memory_store[bundle.bundle_id] = blob
        location = f"memory://{bundle.bundle_id}"
        return BundleReference(
            bundle_id=bundle.bundle_id,
            transaction_id=bundle.transaction_id,
            storage_location=location,
            storage_checksum=bundle.storage_checksum or "",
            size_bytes=bundle.size_bytes,
            created_at=bundle.created_at,
        )

    def _retrieve_from_memory(
        self, bundle_id: str
    ) -> Optional[EvidenceBundle]:
        blob = self._memory_store.get(bundle_id)
        if not blob:
            return None
        return BundleSerializer.from_db_row(blob)
