"""MCP Client for AgentCore Gateway with OAuth2 auth."""

import logging
import os
from datetime import datetime, timedelta

import httpx
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

_token_cache: dict = {"token": None, "expires_at": None}


def get_oauth_token() -> str:
    """Get OAuth2 token with caching."""
    if _token_cache["token"] and _token_cache["expires_at"] and datetime.now() < _token_cache["expires_at"]:
        return _token_cache["token"]

    token_endpoint = os.environ.get("GATEWAY_TOKEN_ENDPOINT")
    client_id = os.environ.get("GATEWAY_CLIENT_ID")
    client_secret = os.environ.get("GATEWAY_CLIENT_SECRET")
    scope = os.environ.get("GATEWAY_SCOPE")

    if not all([token_endpoint, client_id, client_secret, scope]):
        raise ValueError(
            "Missing required env vars: GATEWAY_TOKEN_ENDPOINT, GATEWAY_CLIENT_ID, GATEWAY_CLIENT_SECRET, GATEWAY_SCOPE"
        )

    response = httpx.post(
        str(token_endpoint),
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code != 200:
        logger.debug("OAuth token request failed - response body: %s", response.text)
        raise Exception(f"OAuth token request failed: {response.status_code}")

    data = response.json()
    token = data["access_token"]
    expires_in = data.get("expires_in", 3600) - 300
    _token_cache["token"] = token
    _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in)
    return token


def get_mcp_client() -> MCPClient:
    """Create MCPClient configured for AgentCore Gateway.

    Token fetch is deferred to connection time (inside the lambda),
    so this can be called at module level without making network calls.
    """
    gateway_url = os.environ.get("GATEWAY_MCP_URL")
    if not gateway_url:
        raise ValueError("GATEWAY_MCP_URL environment variable is required")

    return MCPClient(
        lambda: streamablehttp_client(gateway_url, headers={"Authorization": f"Bearer {get_oauth_token()}"})
    )
