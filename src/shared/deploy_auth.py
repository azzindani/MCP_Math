"""Bearer-token auth for HTTP transport. Local/offline-friendly.

Optionally bridges an OAuth 2.0 surface (see oauth_bridge.py) for clients that
require it, such as claude.ai's Custom Connector — the OAuth-issued token maps
back to the same principal the plain bearer token would. Plain bearer tokens
keep working unchanged either way.

Built on the official MCP Python SDK (`mcp`), not the third-party `fastmcp`
package. The two are easy to confuse: the official SDK's own high-level API is
*also* called FastMCP (`mcp.server.fastmcp.FastMCP`, donated as FastMCP v1),
and `fastmcp` 2.x is a separate continuation layered on top of `mcp`. This
fleet ran both for a while, and the split had a real cost -- a single
choke-point fix needed three separate accommodations for the two flavours
(different exception class, different call_tool signature, and get_tool being a
coroutine function in one and not the other). One flavour, one behaviour.

The auth surface maps almost exactly: TokenVerifier and AccessToken are the
same concepts, and FastMCP takes `token_verifier` plus an `auth` AuthSettings
rather than a single `auth=` verifier.
"""

from __future__ import annotations

import json
import os

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from .oauth_bridge import OAuthBridge


def _named_tokens_from_file(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {str(name): str(token) for name, token in data.items()}


def _named_tokens_from_inline(spec: str) -> dict[str, str]:
    pairs = [p for p in spec.split(",") if p.strip()]
    return {name.strip(): token.strip() for name, token in (p.split(":", 1) for p in pairs)}


def load_named_tokens(prefix: str) -> dict[str, str]:
    """Resolve name -> token from env vars, Folio-style priority order.

    <PREFIX>_TOKENS_FILE (named tokens, JSON {name: token})
      > <PREFIX>_TOKENS (inline "name:token,name2:token2")
      > <PREFIX>_API_KEY (single shared token)
      > {} (open mode — no auth, for localhost/private-network use only).
    """
    tokens_file = os.environ.get(f"{prefix}_TOKENS_FILE", "").strip()
    if tokens_file:
        return _named_tokens_from_file(tokens_file)

    inline = os.environ.get(f"{prefix}_TOKENS", "").strip()
    if inline:
        return _named_tokens_from_inline(inline)

    api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()
    return {"default": api_key} if api_key else {}


class _DynamicTokenVerifier(TokenVerifier):
    """Checks the static named-tokens dict first, then OAuth-issued tokens."""

    def __init__(self, named: dict[str, str], oauth_bridge: OAuthBridge | None) -> None:
        super().__init__()
        self._by_token = {token: name for name, token in named.items()}
        self._oauth_bridge = oauth_bridge

    async def verify_token(self, token: str) -> AccessToken | None:
        name = self._by_token.get(token)
        if name is not None:
            return AccessToken(token=token, client_id=name, scopes=[])
        if self._oauth_bridge is not None:
            principal = self._oauth_bridge.resolve_oauth_token(token)
            if principal is not None:
                return AccessToken(token=token, client_id=principal, scopes=[])
        return None


def build_token_verifier(prefix: str, oauth_bridge: OAuthBridge | None = None) -> TokenVerifier | None:
    """Build bearer (+ optional OAuth) auth from env vars.

    Returns None in open mode (no tokens configured at all) — no auth, for
    localhost/private-network use only. oauth_bridge, if given, is consulted
    as a fallback whenever a presented token doesn't match a static one.
    """
    named = load_named_tokens(prefix)
    if not named:
        return None
    return _DynamicTokenVerifier(named, oauth_bridge)


def build_auth(
    prefix: str, host: str, port: int, oauth_bridge: OAuthBridge | None = None
) -> tuple[TokenVerifier, AuthSettings] | tuple[None, None]:
    """Build (token_verifier, auth_settings) for the official SDK's FastMCP.

    Same env-var priority as build_token_verifier, which this wraps; the
    official FastMCP wants the verifier and the settings as two arguments
    rather than one combined `auth=`, and the settings carry the issuer and
    resource-server URLs it puts in the WWW-Authenticate hint on a 401.

    (None, None) in open mode — no auth, localhost/private-network use only.
    """
    verifier = build_token_verifier(prefix, oauth_bridge)
    if verifier is None:
        return None, None
    base_url = AnyHttpUrl(f"http://{host}:{port}")
    return verifier, AuthSettings(issuer_url=base_url, resource_server_url=base_url)


def build_oauth_bridge(prefix: str, state_dir: str | None = None) -> OAuthBridge | None:
    """Build the OAuthBridge for this server, or None in open mode.

    state_dir defaults to a path derived from prefix alone (see oauth_bridge.py).
    Pass it explicitly when multiple sub-servers share one token prefix (e.g.
    ML's basic/medium/advanced tiers) — each is a separate OS process, and
    without distinct state dirs they'd all persist to the same file and
    corrupt each other's state via uncoordinated concurrent writes.
    """
    named = load_named_tokens(prefix)
    if not named:
        return None
    by_token = {token: name for name, token in named.items()}

    def lookup_principal(presented: str) -> str | None:
        return by_token.get(presented)

    return OAuthBridge(prefix, lookup_principal, state_dir=state_dir)
