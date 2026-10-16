from decimal import Decimal
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import Category, Customer, Product, ProductSupplier, Supplier, User
from app.services.inventory import adjust_stock
from config import TestConfig

PASSWORD = "password123"


@pytest.fixture(scope="session")
def app():
    uri = TestConfig.SQLALCHEMY_DATABASE_URI
    if not uri or "test" not in uri:
        pytest.exit(
            "Set TEST_DATABASE_URL in .env to a separate database whose name "
            "contains 'test' (e.g. ims_test)."
        )

    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture(autouse=True)
def app_context(app):
    with app.app_context():
        yield
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample(app):
    admin = User(username="admin", role="admin")
    staff = User(username="staff", role="staff")
    admin.set_password(PASSWORD)
    staff.set_password(PASSWORD)

    tools = Category(name="Hand Tools")
    hammer = Product(sku="HT-001", name="Claw Hammer", category=tools,
                     unit_price=Decimal("18.99"), cost_price=Decimal("9.50"), reorder_level=3)
    tape = Product(sku="HT-002", name="Tape Measure", category=tools,
                   unit_price=Decimal("12.99"), cost_price=Decimal("5.60"), reorder_level=2)
    customer = Customer(name="Walk-in Customer")
    supplier = Supplier(name="Northline Tool Supply")

    hammer_link = ProductSupplier(product=hammer, supplier=supplier, is_preferred=True)

    db.session.add_all([admin, staff, tools, hammer, tape, customer, supplier, hammer_link])
    db.session.commit()

    adjust_stock(hammer.id, 10, admin.id, "Opening stock")
    adjust_stock(tape.id, 5, admin.id, "Opening stock")

    return SimpleNamespace(
        admin=admin, staff=staff, hammer=hammer, tape=tape,
        customer=customer, supplier=supplier, category=tools,
    )


def login(client, username, password=PASSWORD):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
