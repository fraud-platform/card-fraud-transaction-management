"""Ingestion service using aligned schema.

Handles decision event ingestion with enhanced workflow support.
"""

import logging
from datetime import datetime
from uuid import UUID, uuid4, uuid7

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.persistence.review_repository import ReviewRepository
from app.persistence.transaction_repository import TransactionRepository
from app.schemas.decision_event import (
    DecisionEventCreate,
    EvaluationType,
    IngestionSource,
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for decision event ingestion (idempotent)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TransactionRepository(session)
        self.review_repo = ReviewRepository(session)

    async def ingest_event(
        self,
        event: DecisionEventCreate,
        source: IngestionSource = IngestionSource.HTTP,
        trace_id: str | None = None,
    ) -> dict:
        """Ingest a decision event (idempotent by transaction_id).

        On duplicate: update metadata only, never modify business fields.
        Auto-creates review record for new transactions.
        """
        # Use event.transaction_id as the primary key for idempotency
        # Convert to UUID if valid, otherwise generate a new UUIDv7
        try:
            txn_id = UUID(event.transaction_id)
        except (ValueError, AttributeError):
            txn_id = uuid7()

        transaction_data = {
            "transaction_id": txn_id,
            "evaluation_type": event.evaluation_type.value,
            "occurred_at": event.occurred_at,
            "card_id": event.transaction.card_id,
            "card_last4": event.transaction.card_last4,
            "card_network": event.transaction.card_network.value
            if event.transaction.card_network
            else None,
            "amount": float(event.transaction.amount),
            "currency": event.transaction.currency,
            "merchant_id": event.transaction.merchant_id,
            "merchant_category_code": event.transaction.mcc,
            "decision": event.decision.value,
            "decision_reason": event.decision_reason.value,
            "trace_id": trace_id,
            "raw_payload": event.raw_payload,
            "ingestion_source": source.value,
            # Ruleset metadata
            "ruleset_key": event.ruleset_key,
            "ruleset_id": str(event.ruleset_id) if event.ruleset_id else None,
            "ruleset_version": event.ruleset_version,
            # Enhanced fields for analyst workflow
            "risk_level": event.risk_level.value if event.risk_level else None,
            "transaction_context": event.transaction_context,
            "velocity_snapshot": event.velocity_snapshot,
            "velocity_results": event.velocity_results,
            "engine_metadata": event.engine_metadata,
        }

        created_transaction = await self.repository.upsert_transaction(transaction_data)
        transaction_event_id = None
        if created_transaction and created_transaction.get("id"):
            transaction_event_id = UUID(created_transaction["id"])

        # Store rule matches with enhanced fields
        if event.matched_rules and transaction_event_id:
            for rule in event.matched_rules:
                rule_data = {
                    "rule_id": rule.rule_id,
                    "rule_version_id": str(rule.rule_version_id) if rule.rule_version_id else None,
                    "rule_version": rule.rule_version,
                    "rule_name": rule.rule_name,
                    "rule_action": rule.rule_action.value if rule.rule_action else None,
                    "priority": rule.priority,
                    "match_reason": rule.match_reason_text,
                    "conditions_met": rule.conditions_met,
                    "condition_values": rule.condition_values,
                }
                await self.repository.add_rule_match(transaction_event_id, rule_data)

        # Auto-create review record for new transactions (AUTH only)
        if event.evaluation_type == EvaluationType.AUTH and transaction_event_id:
            settings = get_settings()
            if settings.features.enable_auto_review_creation:
                existing_review = await self.review_repo.get_by_transaction_id(transaction_event_id)
                if not existing_review:
                    # Determine priority based on risk level
                    priority = 3  # Default
                    if event.risk_level:
                        priority_map = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
                        priority = priority_map.get(event.risk_level.value, 3)

                    await self.review_repo.create(
                        review_id=uuid4(),
                        transaction_id=transaction_event_id,
                        priority=priority,
                        status="PENDING",
                    )

        logger.info(
            "Decision event ingested",
            extra={
                "transaction_id": str(transaction_data["transaction_id"]),
                "decision": event.decision.value,
                "decision_reason": event.decision_reason.value,
                "risk_level": event.risk_level.value if event.risk_level else None,
                "source": source.value,
            },
        )

        return {
            "status": "accepted",
            "transaction_id": str(transaction_data["transaction_id"]),
            "ingestion_source": source.value,
            "ingested_at": datetime.utcnow().isoformat(),
        }
