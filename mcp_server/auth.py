import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier


class StaticBearerTokenVerifier(TokenVerifier):
    """Validate the assignment's shared Bearer token without timing leaks."""

    def __init__(self, expected_token: str, resource: str) -> None:
        self._expected_token = expected_token
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self._expected_token):
            return None

        return AccessToken(
            token=token,
            client_id="nextjs-agent",
            scopes=["mcp:read"],
            resource=self._resource,
        )
