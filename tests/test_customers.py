import pytest

from app.extensions import db
from app.models import Customer
from app.services.inventory import InventoryError, create_sale
from tests.conftest import login


def test_staff_can_add_a_customer(client, sample):
    login(client, "staff")
    response = client.post(
        "/customers/new",
        data={"name": "Acme Builders", "phone": "555-1000"},
        follow_redirects=True,
    )

    assert b"Acme Builders" in response.data
    customer = db.session.scalar(db.select(Customer).filter_by(name="Acme Builders"))
    assert customer is not None
    assert customer.phone == "555-1000"


def test_adding_a_customer_from_the_sale_form_goes_back_to_the_sale(client, sample):
    login(client, "staff")
    response = client.post("/customers/new?next=sale", data={"name": "Bob Smith"})

    assert response.status_code == 302
    assert "/sales/new?customer_id=" in response.headers["Location"]


def test_staff_cannot_deactivate_a_customer(client, sample):
    login(client, "staff")
    response = client.post(f"/customers/{sample.customer.id}/toggle")
    assert response.status_code == 403


def test_admin_can_deactivate_a_customer(client, sample):
    login(client, "admin")
    client.post(f"/customers/{sample.customer.id}/toggle")
    db.session.rollback()
    assert sample.customer.is_active is False


def test_inactive_customer_cannot_buy(sample):
    sample.customer.is_active = False
    db.session.commit()

    with pytest.raises(InventoryError):
        create_sale(sample.customer.id, [(sample.hammer.id, 1)], sample.staff.id)
    assert sample.hammer.stock_qty == 10


def test_customer_page_shows_their_sales(client, sample):
    order = create_sale(sample.customer.id, [(sample.hammer.id, 2)], sample.staff.id)
    login(client, "staff")
    response = client.get(f"/customers/{sample.customer.id}")

    assert response.status_code == 200
    assert f"/sales/{order.id}".encode() in response.data
