from datetime import datetime

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models import (
    Customer,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    SalesOrderItem,
    StockMovement,
    Supplier,
)
from app.services.notifications import notify_low_stock

OPEN_PO_STATUSES = ("draft", "ordered")


class InventoryError(Exception):
    pass


class InsufficientStockError(InventoryError):
    def __init__(self, shortages):
        self.shortages = shortages
        details = ", ".join(
            f"{sku} (wanted {requested}, only {available} in stock)"
            for sku, _name, requested, available in shortages
        )
        super().__init__(f"Not enough stock: {details}")


def _lock_products(product_ids):
    stmt = (
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {product.id: product for product in db.session.scalars(stmt)}


def _lock_purchase_order(po_id):
    stmt = (
        select(PurchaseOrder)
        .where(PurchaseOrder.id == po_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    po = db.session.scalar(stmt)
    if po is None:
        raise InventoryError("That purchase order doesn't exist.")
    return po


def _flag_if_newly_low(product, when):
    if product.stock_qty <= product.reorder_level and product.low_stock_alerted_at is None:
        product.low_stock_alerted_at = when
        return True
    return False


def _clear_flag_if_restocked(product):
    if product.stock_qty > product.reorder_level:
        product.low_stock_alerted_at = None


def products_on_open_orders(product_ids):
    stmt = (
        select(PurchaseOrderItem.product_id, PurchaseOrder.id, PurchaseOrder.status)
        .join(PurchaseOrderItem.purchase_order)
        .where(
            PurchaseOrder.status.in_(OPEN_PO_STATUSES),
            PurchaseOrderItem.product_id.in_(product_ids),
        )
        .order_by(PurchaseOrder.id)
    )
    return {product_id: (po_id, status) for product_id, po_id, status in db.session.execute(stmt)}


def _draft_reorders(products, user_id, when):
    already_open = products_on_open_orders([p.id for p in products])
    drafts = {}
    for product in products:
        if product.id in already_open:
            continue
        supplier = product.preferred_supplier
        if supplier is None or not supplier.is_active:
            continue

        po = drafts.get(supplier.id)
        if po is None:
            po = db.session.scalar(
                select(PurchaseOrder)
                .filter_by(supplier_id=supplier.id, status="draft", auto_generated=True)
                .order_by(PurchaseOrder.id.desc())
                .limit(1)
            )
        if po is None:
            po = PurchaseOrder(
                supplier_id=supplier.id,
                created_by_id=user_id,
                status="draft",
                auto_generated=True,
                order_date=when,
                notes="Auto-drafted for low stock",
            )
            db.session.add(po)
        drafts[supplier.id] = po

        po.items.append(
            PurchaseOrderItem(
                product=product,
                quantity=product.suggested_reorder_qty,
                unit_cost=product.cost_price,
            )
        )


def _send_alerts(products):
    try:
        notify_low_stock(products)
    except Exception:
        current_app.logger.exception("Low-stock alert failed")


def create_sale(customer_id, lines, user_id, notes=None, when=None, send_alerts=True):
    quantities = {}
    for product_id, quantity in lines:
        if not quantity or quantity < 1:
            raise InventoryError("Every line needs a quantity of at least 1.")
        quantities[product_id] = quantities.get(product_id, 0) + quantity
    if not quantities:
        raise InventoryError("A sale needs at least one product.")

    when = when or datetime.now()
    try:
        customer = db.session.get(Customer, customer_id)
        if customer is None or not customer.is_active:
            raise InventoryError("That customer doesn't exist or is inactive.")

        products = _lock_products(quantities.keys())

        shortages = []
        for product_id, quantity in quantities.items():
            product = products.get(product_id)
            if product is None or not product.is_active:
                raise InventoryError(f"Product #{product_id} doesn't exist or is inactive.")
            if quantity > product.stock_qty:
                shortages.append((product.sku, product.name, quantity, product.stock_qty))
        if shortages:
            raise InsufficientStockError(shortages)

        order = SalesOrder(
            customer_id=customer_id, created_by_id=user_id, notes=notes, order_date=when
        )
        db.session.add(order)

        newly_low = []
        for product_id, quantity in quantities.items():
            product = products[product_id]
            order.items.append(
                SalesOrderItem(product=product, quantity=quantity, unit_price=product.unit_price)
            )
            product.stock_qty -= quantity
            db.session.add(
                StockMovement(
                    product=product,
                    quantity_change=-quantity,
                    reason="sale",
                    sales_order=order,
                    user_id=user_id,
                    created_at=when,
                )
            )
            if _flag_if_newly_low(product, when):
                newly_low.append(product)

        if newly_low:
            _draft_reorders(newly_low, user_id, when)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if newly_low and send_alerts:
        _send_alerts(newly_low)
    return order


def create_purchase_order(supplier_id, lines, user_id, notes=None, when=None):
    if not lines:
        raise InventoryError("A purchase order needs at least one product.")

    when = when or datetime.now()
    try:
        supplier = db.session.get(Supplier, supplier_id)
        if supplier is None or not supplier.is_active:
            raise InventoryError("That supplier doesn't exist or is inactive.")

        po = PurchaseOrder(
            supplier_id=supplier_id, created_by_id=user_id, notes=notes, order_date=when
        )
        for product_id, quantity, unit_cost in lines:
            if not quantity or quantity < 1:
                raise InventoryError("Every line needs a quantity of at least 1.")
            product = db.session.get(Product, product_id)
            if product is None:
                raise InventoryError(f"Product #{product_id} doesn't exist.")
            po.items.append(
                PurchaseOrderItem(
                    product=product,
                    quantity=quantity,
                    unit_cost=product.cost_price if unit_cost is None else unit_cost,
                )
            )
        db.session.add(po)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return po


def update_draft_quantities(po_id, quantities):
    try:
        po = _lock_purchase_order(po_id)
        if po.status != "draft":
            raise InventoryError(f"Purchase order #{po.id} is {po.status}, not a draft.")

        for item in list(po.items):
            quantity = quantities.get(item.id)
            if quantity is None:
                continue
            if quantity < 0:
                raise InventoryError("Quantities can't be negative.")
            if quantity == 0:
                po.items.remove(item)
            else:
                item.quantity = quantity

        if not po.items:
            raise InventoryError("A purchase order needs at least one line. Cancel it instead.")
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return po


def place_purchase_order(po_id, when=None):
    when = when or datetime.now()
    try:
        po = _lock_purchase_order(po_id)
        if po.status != "draft":
            raise InventoryError(f"Purchase order #{po.id} is {po.status}, not a draft.")
        if not po.supplier.is_active:
            raise InventoryError(f"{po.supplier.name} is inactive. Cancel this draft instead.")
        po.status = "ordered"
        po.order_date = when
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return po


def receive_purchase_order(po_id, user_id, when=None, send_alerts=True):
    when = when or datetime.now()
    try:
        po = _lock_purchase_order(po_id)
        if po.status != "ordered":
            raise InventoryError(
                f"Only ordered purchase orders can be received. #{po.id} is {po.status}."
            )

        products = _lock_products({item.product_id for item in po.items})
        for item in po.items:
            product = products[item.product_id]
            product.stock_qty += item.quantity
            db.session.add(
                StockMovement(
                    product=product,
                    quantity_change=item.quantity,
                    reason="receipt",
                    purchase_order=po,
                    user_id=user_id,
                    created_at=when,
                )
            )
        po.status = "received"
        po.received_date = when

        newly_low = []
        for product in products.values():
            product.low_stock_alerted_at = None
            if _flag_if_newly_low(product, when):
                newly_low.append(product)
        if newly_low:
            _draft_reorders(newly_low, user_id, when)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if newly_low and send_alerts:
        _send_alerts(newly_low)
    return po


def cancel_purchase_order(po_id):
    try:
        po = _lock_purchase_order(po_id)
        if po.status not in OPEN_PO_STATUSES:
            raise InventoryError(f"Purchase order #{po.id} is already {po.status}.")
        po.status = "cancelled"
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return po


def adjust_stock(product_id, quantity_change, user_id, note, when=None, send_alerts=True):
    if not quantity_change:
        raise InventoryError("An adjustment can't be zero.")

    when = when or datetime.now()
    newly_low = False
    try:
        product = _lock_products([product_id]).get(product_id)
        if product is None:
            raise InventoryError(f"Product #{product_id} doesn't exist.")
        if product.stock_qty + quantity_change < 0:
            raise InsufficientStockError(
                [(product.sku, product.name, -quantity_change, product.stock_qty)]
            )

        product.stock_qty += quantity_change
        db.session.add(
            StockMovement(
                product=product,
                quantity_change=quantity_change,
                reason="adjustment",
                user_id=user_id,
                note=note,
                created_at=when,
            )
        )

        if quantity_change > 0:
            _clear_flag_if_restocked(product)
        elif _flag_if_newly_low(product, when):
            newly_low = True
            _draft_reorders([product], user_id, when)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if newly_low and send_alerts:
        _send_alerts([product])
    return product
