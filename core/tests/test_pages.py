import json

import pytest
from django.db.backends.utils import CursorWrapper
from django.db.utils import OperationalError
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_returns_200(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["ok"] is True
    assert payload["checks"]["disk"]["ok"] is True


@pytest.mark.django_db(transaction=True)
def test_healthz_returns_503_when_database_not_writable(client, monkeypatch):
    original = CursorWrapper.execute

    def execute(self, sql, params=None):
        stripped = sql.lstrip().upper()
        writes = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")
        if stripped.startswith(writes):
            raise OperationalError("attempt to write a readonly database")
        if params is None:
            return original(self, sql)
        return original(self, sql, params)

    monkeypatch.setattr(CursorWrapper, "execute", execute)
    response = client.get(reverse("healthz"))
    assert response.status_code == 503
    payload = json.loads(response.content)
    assert payload["status"] == "error"
    assert payload["checks"]["database"]["ok"] is False


@pytest.mark.django_db
def test_home_returns_200(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert "上海交通大学守望先锋社区" in response.content.decode("utf-8")
