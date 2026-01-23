import os
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure test uses a temporary auth file to avoid mutating repo state
TEST_AUTH = Path('auth.test.json')
os.environ['AUTH_FILE'] = str(TEST_AUTH)
os.environ['MCP_JWT_SECRET'] = 'testsecret'

from src.modules import mcp_auth

# import app after env vars configured
from server_mcp import app


def setup_module(module):
    # ensure clean test auth file
    if TEST_AUTH.exists():
        TEST_AUTH.unlink()


def teardown_module(module):
    if TEST_AUTH.exists():
        TEST_AUTH.unlink()


def test_jwt_roundtrip():
    token = mcp_auth.generate_jwt(42, os.environ['MCP_JWT_SECRET'], expires_seconds=60)
    assert token is not None
    uid = mcp_auth.verify_jwt(token, os.environ['MCP_JWT_SECRET'])
    assert uid == 42


def test_auth_token_endpoint():
    client = TestClient(app)
    # create api key for user 99
    key = mcp_auth.create_key_for_user(99)
    assert key
    res = client.post('/auth/token', json={'api_key': key})
    assert res.status_code == 200
    data = res.json()
    assert 'access_token' in data
    # verify token decodes to user 99
    token = data['access_token']
    assert mcp_auth.verify_jwt(token, os.environ['MCP_JWT_SECRET']) == 99
