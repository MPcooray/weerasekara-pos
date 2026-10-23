def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness(client):
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
