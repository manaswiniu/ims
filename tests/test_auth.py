import pytest

from app.extensions import db
from tests.conftest import login

ADMIN_ONLY_URLS = [
    "/products/new",
    "/categories/new",
    "/suppliers/new",
    "/auth/users",
    "/auth/users/new",
]


def test_logged_out_user_is_sent_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_wrong_password_is_rejected(client, sample):
    response = login(client, "staff", "not-the-password")
    assert b"Invalid username or password" in response.data


def test_inactive_user_cannot_log_in(client, sample):
    sample.staff.is_active = False
    db.session.commit()
    response = login(client, "staff")
    assert b"Invalid username or password" in response.data


@pytest.mark.parametrize("url", ADMIN_ONLY_URLS)
def test_staff_gets_403_on_admin_routes(client, sample, url):
    login(client, "staff")
    assert client.get(url).status_code == 403


@pytest.mark.parametrize("url", ADMIN_ONLY_URLS)
def test_admin_can_open_admin_routes(client, sample, url):
    login(client, "admin")
    assert client.get(url).status_code == 200


def test_staff_can_record_a_sale_through_the_form(client, sample):
    login(client, "staff")
    response = client.post(
        "/sales/new",
        data={
            "customer_id": sample.customer.id,
            "lines-0-product_id": sample.hammer.id,
            "lines-0-quantity": 3,
        },
        follow_redirects=True,
    )
    assert b"recorded" in response.data

    db.session.rollback()
    assert sample.hammer.stock_qty == 7
