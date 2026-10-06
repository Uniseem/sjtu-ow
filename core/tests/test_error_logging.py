"""Round 214, C3/C11: the 500 page's request ID comes from the server, and a
500 leaves a line in the application log (design 13.15 / 15.5, v7.17)."""

import logging

import pytest

from core.views import server_error


@pytest.mark.django_db
def test_the_request_id_ignores_the_client_header(client):
    response = client.get("/", headers={"X-Request-ID": "forged-by-client"})
    assert response["X-Request-ID"] != "forged-by-client"
    assert len(response["X-Request-ID"]) == 12


def test_the_500_line_ties_the_request_id_to_the_path(rf, caplog):
    request = rf.get("/boom/")
    request.request_id = "abc123def456"
    with caplog.at_level(logging.ERROR, logger="sjtu_ow.errors"):
        response = server_error(request)
    assert response.status_code == 500
    assert "abc123def456" in caplog.text
    assert "/boom/" in caplog.text
