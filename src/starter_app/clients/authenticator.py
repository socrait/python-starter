from abc import ABC, abstractmethod
from collections.abc import Mapping


class Authenticator(ABC):
    """Turns request credentials into the id of an authenticated user.

    Swap in a real implementation (OIDC/JWT verification, session cookies) by passing it
    to `make_app`. Implementations read headers only, so they stay framework-free.
    """

    @abstractmethod
    def authenticate(self, headers: Mapping[str, str]) -> str | None:
        """The authenticated user id, or None when the credentials are missing or invalid."""


class DevHeaderAuthenticator(Authenticator):
    """Trusts an `X-User-Id` header. For local development and tests only: refused when deployed."""

    HEADER = "x-user-id"

    def authenticate(self, headers: Mapping[str, str]) -> str | None:
        return headers.get(self.HEADER) or None
