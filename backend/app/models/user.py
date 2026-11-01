from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from app.core.database import Base


class User(Base):
    """
    User entity for authentication and Role-Based Access Control (RBAC).
    Supported roles: ADMIN, DEVELOPER, VIEWER.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="DEVELOPER", nullable=False)  # ADMIN, DEVELOPER, VIEWER
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}' active={self.is_active}>"
