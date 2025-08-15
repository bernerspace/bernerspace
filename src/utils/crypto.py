import logging
from typing import List, Optional, Tuple
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

logger = logging.getLogger(__name__)

CIPHERTEXT_PREFIX = "enc:v1:"


def _build_fernet(keys: List[str]) -> Optional[MultiFernet]:
    """Create a MultiFernet from a list of base64 urlsafe-encoded 32-byte keys.
    Newest key should be first in the list for rotation semantics.
    """
    clean_keys = [k.strip() for k in keys if k and k.strip()]
    if not clean_keys:
        return None
    try:
        fernets = [Fernet(k) for k in clean_keys]
        return MultiFernet(fernets)
    except Exception:
        logger.exception("Failed to construct MultiFernet. Check TOKEN_ENCRYPTION_KEYS format.")
        return None


def encrypt_text(plaintext: str, keys: List[str]) -> str:
    """Encrypt a UTF-8 plaintext string. Returns prefixed ciphertext suitable for DB storage.
    Raises ValueError if no valid keys are provided.
    """
    f = _build_fernet(keys)
    if not f:
        raise ValueError("TOKEN_ENCRYPTION_KEYS not configured or invalid")
    token = f.encrypt(plaintext.encode("utf-8"))  # bytes
    return f"{CIPHERTEXT_PREFIX}{token.decode('utf-8')}"


def decrypt_text(maybe_ciphertext: str, keys: List[str]) -> Tuple[Optional[str], bool]:
    """Decrypt a previously encrypted string.
    Returns (plaintext, encrypted_flag). If not prefixed/encrypted, returns (input, False).
    If decryption fails, returns (None, True).
    """
    if not isinstance(maybe_ciphertext, str):
        return None, False
    if not maybe_ciphertext.startswith(CIPHERTEXT_PREFIX):
        # Not encrypted by us
        return maybe_ciphertext, False
    ct = maybe_ciphertext[len(CIPHERTEXT_PREFIX):]
    f = _build_fernet(keys)
    if not f:
        logger.error("Encrypted value found but TOKEN_ENCRYPTION_KEYS are not configured")
        return None, True
    try:
        pt = f.decrypt(ct.encode("utf-8")).decode("utf-8")
        return pt, True
    except InvalidToken:
        logger.error("Failed to decrypt oauth token: Invalid token or wrong keys")
        return None, True
    except Exception:
        logger.exception("Unexpected error decrypting oauth token")
        return None, True
