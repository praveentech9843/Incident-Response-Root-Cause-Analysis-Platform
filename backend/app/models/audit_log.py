from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.core.database import Base


class SecurityAuditLog(Base):
    """
    Append-only security and operational audit trail.
    Tracks authentication, RBAC updates, incident state transitions,
    verification steps, reviews, and integration actions.
    """
    __tablename__ = "security_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_entity = Column(String(64), nullable=False, index=True)
    target_id = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<SecurityAuditLog id={self.id} actor='{self.actor}' action='{self.action}' target='{self.target_entity}:{self.target_id}'>"
