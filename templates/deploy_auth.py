"""Bearer-token auth for HTTP transport. Local/offline-friendly, no OAuth server.

Uses the official MCP Python SDK (`mcp`). The SDK ships the TokenVerifier base
class but no `auth.providers` package, so there is no StaticTokenVerifier to
import -- the six-line subclass below is the whole of what that provided.
"""

from __future__ import annotations

import json
import os

from mcp.server.auth.provider import AccessToken, TokenVerifier


def _named_tokens_from_file(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {str(name): str(token) for name, token in data.items()}


def _named_tokens_from_inline(spec: str) -> dict[str, str]:
    pairs = [p for p in spec.split(",") if p.strip()]
    return {name.strip(): token.strip() for name, token in (p.split(":", 1) for p in pairs)}


class _StaticTokenVerifier(TokenVerifier):
    """Accept a fixed set of bearer tokens, each mapped to a principal name."""

    def __init__(self, named: dict[str, str]) -> None:
        self._by_token = {token: name for name, token in named.items()}

    async def verify_token(self, token: str) -> AccessToken | None:
        name = self._by_token.get(token)
        return AccessToken(token=token, client_id=name, scopes=[]) if name else None


def build_token_verifier(prefix: str) -> TokenVerifier | None:
    """Build bearer auth from env vars, Folio-style priority order.

    <PREFIX>_TOKENS_FILE (named tokens, JSON {name: token})
      > <PREFIX>_TOKENS (inline "name:token,name2:token2")
      > <PREFIX>_API_KEY (single shared token)
      > None (open mode — no auth, for localhost/private-network use only).
    """
    tokens_file = os.environ.get(f"{prefix}_TOKENS_FILE", "").strip()
    if tokens_file:
        named = _named_tokens_from_file(tokens_file)
    else:
        inline = os.environ.get(f"{prefix}_TOKENS", "").strip()
        if inline:
            named = _named_tokens_from_inline(inline)
        else:
            api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()
            named = {"default": api_key} if api_key else {}

    if not named:
        return None

    return _StaticTokenVerifier(named)
