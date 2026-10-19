import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.modules.iam.models import User

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(encoded: str | None, password: str) -> bool:
    try:
        result = hasher.verify(encoded or DUMMY_HASH, password)
        return bool(encoded) and result
    except (VerificationError, InvalidHashError):
        return False


class MfaVerifier(Protocol):
    available: bool

    def verify(self, user: User, code: str) -> bool:
        """Verify and consume a factor, rejecting replay inside the provider."""
        ...


class UnconfiguredMfa:
    available = False

    def verify(self, user: User, code: str) -> bool:
        return False


def _cipher() -> Fernet:
    key = settings.identity_encryption_key.get_secret_value()
    if not key:
        raise RuntimeError("IDENTITY_ENCRYPTION_KEY is required for MFA.")
    return Fernet(key.encode())


def encrypt_mfa_secret(secret: str) -> str:
    return _cipher().encrypt(secret.encode()).decode()


def decrypt_mfa_secret(ciphertext: str) -> str:
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError) as error:
        raise RuntimeError("The MFA secret cannot be decrypted.") from error


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, timestamp: int | None = None) -> str:
    counter = (timestamp if timestamp is not None else int(time.time())) // 30
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest_value = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest_value[-1] & 15
    value = (struct.unpack(">I", digest_value[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: str) -> bool:
    clean = code.strip().replace(" ", "")
    return (
        clean.isdigit()
        and len(clean) == 6
        and any(
            secrets.compare_digest(totp(secret, int(time.time()) + offset), clean)
            for offset in (-30, 0, 30)
        )
    )


def recovery_hash(code: str) -> str:
    return digest("happy-mfa-recovery:" + code.strip().upper())


class TotpMfa:
    def __init__(self) -> None:
        self.available = bool(settings.identity_encryption_key.get_secret_value())

    def verify(self, user: User, code: str) -> bool:
        hashed = recovery_hash(code)
        if hashed in user.mfa_recovery_hashes:
            user.mfa_recovery_hashes = [item for item in user.mfa_recovery_hashes if item != hashed]
            return True
        ciphertext = user.mfa_secret_ciphertext
        return bool(ciphertext) and verify_totp(decrypt_mfa_secret(ciphertext or ""), code)


def get_mfa_verifier() -> MfaVerifier:
    return TotpMfa()
