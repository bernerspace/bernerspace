import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
import json
from src.utils.database import SessionLocal
from src.models.oauth_token import Base, OAuthToken
from src.utils.env_handler import TOKEN_ENCRYPTION_KEYS
from src.utils.crypto import encrypt_text, decrypt_text

logger = logging.getLogger(__name__)


class TokenStorageManager:
    """DB-backed OAuth token manager using SQLAlchemy"""

    def __init__(self):
        # Tables are created via Alembic migrations
        pass

    def write_token(self, client_id: str, token_data: Dict, integration_type: str = "slack") -> None:
        """Upsert OAuth token for a client ID and integration type"""
        try:
            with SessionLocal() as session:
                existing = session.execute(
                    select(OAuthToken).where(
                        OAuthToken.client_id == client_id,
                        OAuthToken.integration_type == integration_type,
                    )
                ).scalar_one_or_none()

                now = datetime.now(timezone.utc)
                token_json = json.dumps(token_data)

                # Encrypt if keys configured
                if TOKEN_ENCRYPTION_KEYS:
                    try:
                        token_json = encrypt_text(token_json, TOKEN_ENCRYPTION_KEYS)
                    except Exception:
                        logger.exception("Failed to encrypt oauth token; aborting write")
                        raise

                if existing:
                    existing.token_json = token_json
                    existing.stored_at = now
                else:
                    session.add(
                        OAuthToken(
                            client_id=client_id,
                            integration_type=integration_type,
                            token_json=token_json,
                            stored_at=now,
                        )
                    )
                session.commit()
                logger.info(f"Stored OAuth token for client: {client_id} ({integration_type})")
        except SQLAlchemyError as e:
            logger.error(f"DB error writing token: {e}")
            raise

    def read_token(self, client_id: str, integration_type: str = "slack") -> Optional[Dict]:
        """Read OAuth token for a client ID and integration type"""
        try:
            with SessionLocal() as session:
                row = session.execute(
                    select(OAuthToken).where(
                        OAuthToken.client_id == client_id,
                        OAuthToken.integration_type == integration_type,
                    )
                ).scalar_one_or_none()
                if not row:
                    logger.debug(f"No token found for client: {client_id} ({integration_type})")
                    return None
                raw = row.token_json
                data_str, was_encrypted = decrypt_text(raw, TOKEN_ENCRYPTION_KEYS)
                if was_encrypted:
                    if data_str is None:
                        # Encrypted but cannot decrypt
                        logger.error("Token present but cannot decrypt (check keys/rotation)")
                        return None
                else:
                    # plaintext legacy row; keep as-is
                    data_str = raw
                try:
                    data = json.loads(data_str) if data_str else None
                except Exception:
                    logger.exception("Failed to parse token_json as JSON")
                    data = None
                return data
        except SQLAlchemyError as e:
            logger.error(f"DB error reading token: {e}")
            return None

