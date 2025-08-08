from datetime import datetime
from typing import Optional

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime

# SQLAlchemy base
class Base(DeclarativeBase):
    pass

# ORM model for storing OAuth tokens per client_id and integration
class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    # composite PK so a client can have many integrations
    client_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    integration_type: Mapped[str] = mapped_column(String(64), primary_key=True, default="slack")
    token_json: Mapped[str] = mapped_column(Text, nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)