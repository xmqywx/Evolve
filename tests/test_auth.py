import pytest
from myagent.auth import create_token, verify_token


def test_create_and_verify_token():
    token = create_token("test-secret", expiry_hours=1)
    assert token is not None
    payload = verify_token(token, "test-secret")
    assert payload is not None
    assert "exp" in payload


def test_verify_invalid_token():
    result = verify_token("invalid.token.here", "test-secret")
    assert result is None


def test_verify_wrong_secret():
    token = create_token("secret-a", expiry_hours=1)
    result = verify_token(token, "secret-b")
    assert result is None
