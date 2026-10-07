def test_health_check(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_check_head(client):
    response = client.head("/api/v1/health")

    assert response.status_code == 200


def test_health_check_without_slash(client):
    response = client.get("/api/v1health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
