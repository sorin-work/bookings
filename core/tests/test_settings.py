import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import env_bool, env_int, env_list


@pytest.mark.parametrize(
    "value, expected",
    [("true", True), ("1", True), ("Yes", True), ("false", False), ("0", False), ("", False)],
)
def test_env_bool(monkeypatch, value, expected):
    monkeypatch.setenv("SOME_FLAG", value)

    assert env_bool("SOME_FLAG") is expected


def test_env_bool_default(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)

    assert env_bool("SOME_FLAG", True) is True


def test_env_list(monkeypatch):
    monkeypatch.setenv("HOSTS", " a.example , b.example,, ")

    assert env_list("HOSTS") == ["a.example", "b.example"]


def test_env_int(monkeypatch):
    monkeypatch.setenv("PORT", "1025")
    assert env_int("PORT", 25) == 1025

    monkeypatch.setenv("PORT", "lots")
    with pytest.raises(ImproperlyConfigured):
        env_int("PORT", 25)


@pytest.mark.django_db
def test_security_headers(client):
    response = client.get("/healthz")

    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
