from tests.conftest import get_client


def test_register_login_and_me():
    client = get_client()

    register_response = client.post(
        "/auth/register",
        json={
            "name": "Demo User",
            "email": "demo@wellpredict.io",
            "password": "demo1234",
        },
    )
    assert register_response.status_code == 201
    user = register_response.json()
    assert user["email"] == "demo@wellpredict.io"
    assert user["role"] == "operator"

    login_response = client.post(
        "/auth/login",
        json={"email": "demo@wellpredict.io", "password": "demo1234"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "demo@wellpredict.io"


def test_register_duplicate_email():
    client = get_client()
    payload = {
        "name": "Demo User",
        "email": "duplicate@example.com",
        "password": "demo1234",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409
