from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.incident_context import IncidentContext
from app.context.base import ContextResult


class IncidentContextRepository:
    """Repository managing persistence and retrieval of incident operational context entities."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_incident_and_category(
        self, incident_id: int, category: str
    ) -> Optional[IncidentContext]:
        """Fetch a specific context record for an incident by category."""
        return (
            self.db.query(IncidentContext)
            .filter(
                IncidentContext.incident_id == incident_id,
                IncidentContext.context_category == category.lower(),
            )
            .first()
        )

    def get_all_for_incident(self, incident_id: int) -> List[IncidentContext]:
        """Retrieve all operational context records associated with an incident."""
        return (
            self.db.query(IncidentContext)
            .filter(IncidentContext.incident_id == incident_id)
            .order_by(IncidentContext.id.asc())
            .all()
        )

    def upsert_context(
        self,
        incident_id: int,
        category: str,
        status: str,
        data: Dict,
        source: str,
    ) -> IncidentContext:
        """
        Idempotently create or update an incident context record.
        Maintains unique (incident_id, context_category) constraint.
        """
        now = datetime.now(timezone.utc)
        record = self.get_by_incident_and_category(incident_id, category)

        if record:
            record.status = status
            record.data = data
            record.source = source
            record.collected_at = now
            record.updated_at = now
        else:
            record = IncidentContext(
                incident_id=incident_id,
                context_category=category.lower(),
                status=status,
                data=data,
                source=source,
                collected_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(record)

        self.db.commit()
        self.db.refresh(record)
        return record

    def save_all_contexts(
        self,
        incident_id: int,
        results: List[ContextResult],
    ) -> List[IncidentContext]:
        """
        Persist a batch of context collection results within a single transaction.
        Updates existing categories or inserts new ones idempotently.
        """
        now = datetime.now(timezone.utc)
        saved_records = []

        for res in results:
            cat_name = res.category.value
            record = self.get_by_incident_and_category(incident_id, cat_name)
            if record:
                record.status = res.status.value
                record.data = res.data
                record.source = res.source
                record.collected_at = now
                record.updated_at = now
            else:
                record = IncidentContext(
                    incident_id=incident_id,
                    context_category=cat_name,
                    status=res.status.value,
                    data=res.data,
                    source=res.source,
                    collected_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(record)
            saved_records.append(record)

        self.db.commit()
        for rec in saved_records:
            self.db.refresh(rec)

        return saved_records
