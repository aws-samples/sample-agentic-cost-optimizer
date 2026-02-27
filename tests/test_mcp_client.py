"""Unit tests for src/mcp_client/client.py."""

from unittest.mock import MagicMock, patch

import pytest

from src.mcp_client.client import _token_cache, get_mcp_client, get_oauth_token

GATEWAY_ENV = {
    "GATEWAY_TOKEN_ENDPOINT": "https://auth.example.com/token",
    "GATEWAY_CLIENT_ID": "test-client-id",
    "GATEWAY_CLIENT_SECRET": "test-secret",
    "GATEWAY_SCOPE": "test-scope",
    "GATEWAY_MCP_URL": "https://gateway.example.com/mcp",
}


class TestGetOAuthToken:
    def setup_method(self):
        _token_cache["token"] = None
        _token_cache["expires_at"] = None

    @patch.dict("os.environ", GATEWAY_ENV)
    @patch("src.mcp_client.client.httpx")
    def test_fetches_token(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "tok-123",
            "expires_in": 3600,
        }
        mock_httpx.post.return_value = mock_response

        token = get_oauth_token()

        assert token == "tok-123"
        mock_httpx.post.assert_called_once()

    @patch.dict("os.environ", GATEWAY_ENV)
    @patch("src.mcp_client.client.httpx")
    def test_returns_cached_token(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "tok-123",
            "expires_in": 3600,
        }
        mock_httpx.post.return_value = mock_response

        get_oauth_token()
        get_oauth_token()

        assert mock_httpx.post.call_count == 1

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_env_vars_raises(self):
        with pytest.raises(ValueError, match="Missing required env vars"):
            get_oauth_token()

    @patch.dict("os.environ", GATEWAY_ENV)
    @patch("src.mcp_client.client.httpx")
    def test_failed_response_raises(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_httpx.post.return_value = mock_response

        with pytest.raises(Exception, match="OAuth token request failed"):
            get_oauth_token()


class TestGetMcpClient:
    def setup_method(self):
        _token_cache["token"] = None
        _token_cache["expires_at"] = None

    @patch.dict("os.environ", GATEWAY_ENV)
    def test_returns_mcp_client(self):
        client = get_mcp_client()
        assert client is not None

    @patch.dict("os.environ", {"GATEWAY_MCP_URL": ""}, clear=True)
    def test_missing_gateway_url_raises(self):
        with pytest.raises(ValueError, match="GATEWAY_MCP_URL"):
            get_mcp_client()
