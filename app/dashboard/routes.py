from datetime import date, datetime, time

from flask import render_template
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from app.dashboard import bp
from app.extensions import db
from app.models import Product, ProductSupplier, PurchaseOrder, SalesOrder, SalesOrderItem
from app.services.inventory import products_on_open_orders


@bp.route("/")
@login_required
def index():
    start_of_today = datetime.combine(date.today(), time.min)

    sales_count = db.session.scalar(
        db.select(func.count(SalesOrder.id)).where(SalesOrder.order_date >= start_of_today)
    )
    sales_total = db.session.scalar(
        db.select(func.coalesce(func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price), 0))
        .select_from(SalesOrderItem)
        .join(SalesOrderItem.sales_order)
        .where(SalesOrder.order_date >= start_of_today)
    )
    open_po_count = db.session.scalar(
        db.select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status == "ordered")
    )
    draft_po_count = db.session.scalar(
        db.select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status == "draft")
    )

    low_stock = db.session.scalars(
        db.select(Product)
        .filter_by(is_active=True)
        .where(Product.stock_qty <= Product.reorder_level)
        .options(selectinload(Product.supplier_links).joinedload(ProductSupplier.supplier))
        .order_by((Product.stock_qty - Product.reorder_level), Product.sku)
    ).all()
    on_order = products_on_open_orders([p.id for p in low_stock]) if low_stock else {}

    return render_template(
        "dashboard/index.html",
        sales_count=sales_count,
        sales_total=sales_total,
        open_po_count=open_po_count,
        draft_po_count=draft_po_count,
        low_stock=low_stock,
        on_order=on_order,
    )
