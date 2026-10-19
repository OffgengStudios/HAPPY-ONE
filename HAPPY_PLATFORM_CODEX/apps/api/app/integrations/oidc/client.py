from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class OidcIdentity:
    issuer: str
    subject: str
    email: str
    email_verified: bool
    nonce: str
    mfa_verified: bool = False


class OidcClient(Protocol):
    available: bool
    provider_name: str

    def authorization_url(self, state: str, nonce: str) -> str: ...

    def exchange(self, code: str) -> OidcIdentity: ...


class OpenIdConnectClient:
    def __init__(self) -> None:
        self.available = all(
            (
                settings.oidc_issuer,
                settings.oidc_client_id,
                settings.oidc_client_secret.get_secret_value(),
                settings.oidc_redirect_uri,
            )
        )
        self.provider_name = settings.oidc_provider_name
        self._metadata: dict[str, Any] | None = None

    def metadata(self) -> dict[str, Any]:
        if not self.available:
            raise ApiError(503, "SSO_NOT_CONFIGURED", "Single sign-on is not configured.")
        if self._metadata is None:
            url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
            try:
                response = httpx.get(url, timeout=10, follow_redirects=False)
                response.raise_for_status()
                metadata = response.json()
            except (httpx.HTTPError, ValueError) as error:
                raise ApiError(503, "SSO_UNAVAILABLE", "Single sign-on is unavailable.") from error
            required = {"authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"}
            if not required <= metadata.keys() or metadata["issuer"] != settings.oidc_issuer:
                raise ApiError(503, "SSO_INVALID_METADATA", "SSO provider metadata is invalid.")
            self._metadata = metadata
        return self._metadata

    def authorization_url(self, state: str, nonce: str) -> str:
        endpoint = str(self.metadata()["authorization_endpoint"])
        return (
            endpoint
            + "?"
            + urlencode(
                {
                    "response_type": "code",
                    "client_id": settings.oidc_client_id,
                    "redirect_uri": settings.oidc_redirect_uri,
                    "scope": "openid email profile",
                    "state": state,
                    "nonce": nonce,
                }
            )
        )

    def exchange(self, code: str) -> OidcIdentity:
        metadata = self.metadata()
        try:
            response = httpx.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret.get_secret_value(),
                    "redirect_uri": settings.oidc_redirect_uri,
                },
                timeout=15,
                follow_redirects=False,
            )
            response.raise_for_status()
            token = response.json()["id_token"]
            key = PyJWKClient(metadata["jwks_uri"]).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                audience=settings.oidc_client_id,
                issuer=settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce", "email"]},
            )
        except (httpx.HTTPError, KeyError, ValueError, jwt.PyJWTError) as error:
            raise ApiError(
                401, "SSO_EXCHANGE_FAILED", "Single sign-on could not be verified."
            ) from error
        return OidcIdentity(
            issuer=str(claims["iss"]),
            subject=str(claims["sub"]),
            email=str(claims["email"]).lower(),
            email_verified=claims.get("email_verified") is True,
            nonce=str(claims["nonce"]),
            mfa_verified="mfa" in claims.get("amr", []),
        )


def get_oidc_client() -> OidcClient:
    return OpenIdConnectClient()
