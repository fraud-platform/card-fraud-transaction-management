"""Transaction query service with workflow support."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for transaction query operations with fraud_gov schema."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TransactionRepository(session)

    async def get_transaction(
        self,
        transaction_id: str | UUID,
        include_rules: bool = True,
    ) -> dict | None:
        """Get a transaction by ID."""
        # Convert string to UUID if needed
        if isinstance(transaction_id, str):
            try:
                transaction_id = UUID(transaction_id)
            except ValueError:
                return None

        transaction = await self.repository.get_by_transaction_id(transaction_id)
        if transaction is None:
            return None

        if include_rules:
            transaction_event_id = UUID(transaction["id"]) if transaction.get("id") else None
            if transaction_event_id:
                rule_matches = await self.repository.get_rule_matches_for_event(  # noqa: E501
                    transaction_event_id
                )
                transaction["matched_rules"] = rule_matches

        return transaction

    async def get_transaction_combined(
        self,
        transaction_id: str | UUID,
        include_rules: bool = True,
    ) -> dict | None:
        """Get combined AUTH + MONITORING view for a transaction_id."""
        if isinstance(transaction_id, str):
            try:
                transaction_id = UUID(transaction_id)
            except ValueError:
                return None

        preauth = await self.repository.get_by_transaction_id(transaction_id, "AUTH")
        postauth = await self.repository.get_by_transaction_id(transaction_id, "MONITORING")

        if preauth is None and postauth is None:
            return None

        if include_rules:
            if preauth and preauth.get("id"):
                preauth_id = UUID(preauth["id"])
                preauth["matched_rules"] = await self.repository.get_rule_matches_for_event(  # noqa: E501
                    preauth_id
                )
            if postauth and postauth.get("id"):
                postauth_id = UUID(postauth["id"])
                postauth["matched_rules"] = await self.repository.get_rule_matches_for_event(  # noqa: E501
                    postauth_id
                )

        return {
            "transaction_id": str(transaction_id),
            "auth": preauth,
            "monitoring": postauth,
        }

    async def get_transaction_overview(
        self,
        transaction_id: str | UUID,
        include_rules: bool = False,
        analyst_id: str | None = None,
    ) -> dict | None:
        """Get combined transaction overview for analyst UI.

        Returns transaction, review, notes, case, and matched_rules in a single call.
        """
        if isinstance(transaction_id, str):
            try:
                transaction_id = UUID(transaction_id)
            except ValueError:
                return None

        return await self.repository.get_transaction_overview(
            transaction_id=transaction_id,
            include_rules=include_rules,
            analyst_id=analyst_id,
        )

    async def list_transactions(
        self,
        page_size: int = 50,
        card_id: str | None = None,
        decision: str | None = None,
        country: str
        | None = None,  # Not persisted in DB (lean table), accepted for API compatibility
        merchant_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        review_status: str | None = None,
        risk_level: str | None = None,
        case_id: UUID | None = None,
        rule_id: UUID | None = None,
        ruleset_id: UUID | None = None,
        assigned_to_me: bool = False,
        assigned_analyst_id: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        cursor: str | None = None,
    ) -> dict:
        """List transactions with keyset pagination.

        Note: `country` filter is accepted for API compatibility but not applied
        since country is not persisted in the database (lean hot table design).

        Supports review status, risk level, case, rule, ruleset, assigned analyst,
        and amount range filters for workflow.
        """
        transactions, next_cursor, total = await self.repository.list(
            card_id=card_id,
            decision=decision,
            merchant_id=merchant_id,
            from_date=from_date,
            to_date=to_date,
            review_status=review_status,
            risk_level=risk_level,
            case_id=case_id,
            rule_id=rule_id,
            ruleset_id=ruleset_id,
            assigned_to_me=assigned_to_me,
            assigned_analyst_id=assigned_analyst_id,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=page_size,
            cursor=cursor,
        )

        return {
            "items": transactions,
            "total": total,
            "page_size": page_size,
            "has_more": next_cursor is not None,
            "next_cursor": next_cursor,
        }

    async def get_metrics(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict:
        """Get transaction metrics."""
        return await self.repository.get_metrics(from_date, to_date)
