import pytest

from app.extensions import db
from app.models import PurchaseOrder
from app.services import inventory
from app.services.inventory import (
    InventoryError,
    adjust_stock,
    cancel_purchase_order,
    create_sale,
    place_purchase_order,
    receive_purchase_order,
    update_draft_quantities,
)


def drafts():
    return db.session.scalars(db.select(PurchaseOrder).filter_by(status="draft")).all()


def sell(sample, product, quantity):
    return create_sale(sample.customer.id, [(product.id, quantity)], sample.staff.id)


def test_dropping_to_reorder_level_flags_product_and_drafts_po(sample):
    sell(sample, sample.hammer, 7)

    assert sample.hammer.stock_qty == 3
    assert sample.hammer.low_stock_alerted_at is not None

    [po] = drafts()
    assert po.auto_generated
    assert po.supplier_id == sample.supplier.id
    assert [(item.product_id, item.quantity) for item in po.items] == [(sample.hammer.id, 6)]


def test_staying_low_does_not_draft_again(sample):
    sell(sample, sample.hammer, 7)
    sell(sample, sample.hammer, 1)

    [po] = drafts()
    assert len(po.items) == 1


def test_alert_is_sent_once_per_drop(sample, monkeypatch):
    sent = []
    monkeypatch.setattr(
        inventory, "notify_low_stock", lambda products: sent.append([p.sku for p in products])
    )

    sell(sample, sample.hammer, 7)
    sell(sample, sample.hammer, 1)

    assert sent == [["HT-001"]]


def test_product_without_preferred_supplier_is_flagged_but_not_drafted(sample):
    sell(sample, sample.tape, 3)

    assert sample.tape.low_stock_alerted_at is not None
    assert drafts() == []


def test_negative_adjustment_can_trigger_a_draft(sample):
    adjust_stock(sample.hammer.id, -7, sample.admin.id, "Damaged in storage")

    assert sample.hammer.low_stock_alerted_at is not None
    assert len(drafts()) == 1


def test_draft_must_be_placed_before_it_can_be_received(sample):
    sell(sample, sample.hammer, 7)
    [po] = drafts()

    with pytest.raises(InventoryError):
        receive_purchase_order(po.id, sample.admin.id)

    place_purchase_order(po.id)
    receive_purchase_order(po.id, sample.admin.id)

    assert sample.hammer.stock_qty == 9
    assert sample.hammer.low_stock_alerted_at is None


def test_alert_cycle_starts_again_after_restock(sample, monkeypatch):
    sent = []
    monkeypatch.setattr(
        inventory, "notify_low_stock", lambda products: sent.append([p.sku for p in products])
    )

    sell(sample, sample.hammer, 7)
    [po] = drafts()
    place_purchase_order(po.id)
    receive_purchase_order(po.id, sample.admin.id)
    sell(sample, sample.hammer, 6)

    assert sent == [["HT-001"], ["HT-001"]]
    assert len(drafts()) == 1


def test_draft_quantities_can_be_changed(sample):
    sell(sample, sample.hammer, 7)
    [po] = drafts()
    item_id = po.items[0].id

    update_draft_quantities(po.id, {item_id: 12})
    assert po.items[0].quantity == 12

    with pytest.raises(InventoryError):
        update_draft_quantities(po.id, {item_id: 0})
    assert po.items[0].quantity == 12


def test_discarded_draft_is_not_reopened_while_still_low(sample):
    sell(sample, sample.hammer, 7)
    [po] = drafts()
    cancel_purchase_order(po.id)

    sell(sample, sample.hammer, 1)

    assert drafts() == []
