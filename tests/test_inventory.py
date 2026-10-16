import pytest
from sqlalchemy import func

from app.extensions import db
from app.models import SalesOrder, StockMovement
from app.services.inventory import (
    InsufficientStockError,
    InventoryError,
    adjust_stock,
    create_purchase_order,
    create_sale,
    receive_purchase_order,
)


def count(model, **filters):
    return db.session.scalar(db.select(func.count()).select_from(model).filter_by(**filters))


def test_sale_reduces_stock_and_writes_one_movement_per_line(sample):
    order = create_sale(
        sample.customer.id,
        [(sample.hammer.id, 3), (sample.tape.id, 2)],
        sample.staff.id,
    )

    assert sample.hammer.stock_qty == 7
    assert sample.tape.stock_qty == 3

    movements = db.session.scalars(
        db.select(StockMovement).filter_by(sales_order_id=order.id)
    ).all()
    assert sorted(m.quantity_change for m in movements) == [-3, -2]
    assert all(m.reason == "sale" for m in movements)


def test_sale_copies_current_price_onto_items(sample):
    order = create_sale(sample.customer.id, [(sample.hammer.id, 1)], sample.staff.id)
    assert order.items[0].unit_price == sample.hammer.unit_price


def test_sale_larger_than_stock_saves_nothing(sample):
    with pytest.raises(InsufficientStockError) as error:
        create_sale(
            sample.customer.id,
            [(sample.hammer.id, 3), (sample.tape.id, 99)],
            sample.staff.id,
        )

    assert error.value.shortages[0][0] == "HT-002"
    assert sample.hammer.stock_qty == 10
    assert sample.tape.stock_qty == 5
    assert count(SalesOrder) == 0
    assert count(StockMovement, reason="sale") == 0


def test_same_product_on_two_lines_is_combined(sample):
    order = create_sale(
        sample.customer.id,
        [(sample.hammer.id, 2), (sample.hammer.id, 3)],
        sample.staff.id,
    )
    assert len(order.items) == 1
    assert order.items[0].quantity == 5
    assert sample.hammer.stock_qty == 5


def test_receiving_purchase_order_adds_stock_once(sample):
    po = create_purchase_order(sample.supplier.id, [(sample.hammer.id, 10, None)], sample.admin.id)
    assert sample.hammer.stock_qty == 10

    receive_purchase_order(po.id, sample.admin.id)
    assert sample.hammer.stock_qty == 20
    assert po.status == "received"
    assert po.received_date is not None
    assert count(StockMovement, purchase_order_id=po.id, reason="receipt") == 1

    with pytest.raises(InventoryError):
        receive_purchase_order(po.id, sample.admin.id)
    assert sample.hammer.stock_qty == 20
    assert count(StockMovement, purchase_order_id=po.id) == 1


def test_purchase_order_uses_cost_price_when_unit_cost_blank(sample):
    po = create_purchase_order(sample.supplier.id, [(sample.tape.id, 4, None)], sample.admin.id)
    assert po.items[0].unit_cost == sample.tape.cost_price


def test_adjustment_cannot_take_stock_below_zero(sample):
    with pytest.raises(InsufficientStockError):
        adjust_stock(sample.tape.id, -6, sample.admin.id, "Damaged")
    assert sample.tape.stock_qty == 5
