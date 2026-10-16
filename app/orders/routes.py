from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import Customer, Product, PurchaseOrder, SalesOrder, Supplier
from app.orders import bp
from app.orders.forms import PurchaseOrderForm, SaleForm
from app.services.inventory import (
    InsufficientStockError,
    InventoryError,
    cancel_purchase_order,
    create_purchase_order,
    create_sale,
    place_purchase_order,
    receive_purchase_order,
    update_draft_quantities,
)

BLANK_PRODUCT = (0, "-- choose a product --")


def _active_products():
    return db.session.scalars(
        db.select(Product).filter_by(is_active=True).order_by(Product.sku)
    ).all()


@bp.route("/sales")
@login_required
def sales():
    orders = db.session.scalars(
        db.select(SalesOrder)
        .options(joinedload(SalesOrder.customer), selectinload(SalesOrder.items))
        .order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())
        .limit(100)
    ).all()
    return render_template("orders/sales_list.html", orders=orders)


@bp.route("/sales/new", methods=["GET", "POST"])
@login_required
def new_sale():
    form = SaleForm()
    customers = db.session.scalars(
        db.select(Customer).filter_by(is_active=True).order_by(Customer.name)
    ).all()
    form.customer_id.choices = [(c.id, c.name) for c in customers]
    form.set_product_choices(
        [BLANK_PRODUCT]
        + [(p.id, f"{p.label} ({p.stock_qty} in stock)") for p in _active_products()]
    )

    if request.method == "GET" and request.args.get("customer_id", type=int):
        form.customer_id.data = request.args.get("customer_id", type=int)

    if form.validate_on_submit():
        try:
            order = create_sale(
                form.customer_id.data,
                form.line_items(),
                current_user.id,
                notes=form.notes.data or None,
            )
        except InsufficientStockError as error:
            for sku, name, requested, available in error.shortages:
                flash(
                    f"Not enough {sku} ({name}): you asked for {requested}, "
                    f"only {available} in stock. Nothing was saved.",
                    "danger",
                )
        except InventoryError as error:
            flash(str(error), "danger")
        else:
            flash(f"Sale #{order.id} recorded.", "success")
            return redirect(url_for("orders.sale_detail", order_id=order.id))
    return render_template("orders/sale_form.html", form=form, has_customers=bool(customers))


@bp.route("/sales/<int:order_id>")
@login_required
def sale_detail(order_id):
    order = db.get_or_404(SalesOrder, order_id)
    return render_template("orders/sale_detail.html", order=order)


@bp.route("/purchases")
@login_required
def purchases():
    status = request.args.get("status")
    stmt = (
        db.select(PurchaseOrder)
        .options(joinedload(PurchaseOrder.supplier), selectinload(PurchaseOrder.items))
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .limit(100)
    )
    if status in ("draft", "ordered", "received", "cancelled"):
        stmt = stmt.filter_by(status=status)
    return render_template(
        "orders/purchases_list.html", orders=db.session.scalars(stmt).all(), status=status
    )


@bp.route("/purchases/new", methods=["GET", "POST"])
@login_required
def new_purchase():
    form = PurchaseOrderForm()
    suppliers = db.session.scalars(
        db.select(Supplier).filter_by(is_active=True).order_by(Supplier.name)
    ).all()
    form.supplier_id.choices = [(s.id, s.name) for s in suppliers]
    form.set_product_choices([BLANK_PRODUCT] + [(p.id, p.label) for p in _active_products()])

    if request.method == "GET":
        if request.args.get("supplier_id", type=int):
            form.supplier_id.data = request.args.get("supplier_id", type=int)
        if request.args.get("product_id", type=int):
            form.lines[0].product_id.data = request.args.get("product_id", type=int)

    if form.validate_on_submit():
        try:
            po = create_purchase_order(
                form.supplier_id.data,
                form.line_items(),
                current_user.id,
                notes=form.notes.data or None,
            )
        except InventoryError as error:
            flash(str(error), "danger")
        else:
            flash(f"Purchase order #{po.id} created.", "success")
            return redirect(url_for("orders.purchase_detail", po_id=po.id))
    return render_template("orders/purchase_form.html", form=form, has_suppliers=bool(suppliers))


@bp.route("/purchases/<int:po_id>")
@login_required
def purchase_detail(po_id):
    po = db.get_or_404(PurchaseOrder, po_id)
    return render_template("orders/purchase_detail.html", po=po)


@bp.route("/purchases/<int:po_id>/receive", methods=["POST"])
@login_required
def receive_purchase(po_id):
    try:
        receive_purchase_order(po_id, current_user.id)
    except InventoryError as error:
        flash(str(error), "danger")
    else:
        flash(f"Purchase order #{po_id} received. Stock updated.", "success")
    return redirect(url_for("orders.purchase_detail", po_id=po_id))


@bp.route("/purchases/<int:po_id>/cancel", methods=["POST"])
@login_required
def cancel_purchase(po_id):
    try:
        cancel_purchase_order(po_id)
    except InventoryError as error:
        flash(str(error), "danger")
    else:
        flash(f"Purchase order #{po_id} cancelled.", "success")
    return redirect(url_for("orders.purchase_detail", po_id=po_id))


@bp.route("/purchases/<int:po_id>/place", methods=["POST"])
@login_required
def place_purchase(po_id):
    try:
        place_purchase_order(po_id)
    except InventoryError as error:
        flash(str(error), "danger")
    else:
        flash(f"Purchase order #{po_id} placed with the supplier.", "success")
    return redirect(url_for("orders.purchase_detail", po_id=po_id))


@bp.route("/purchases/<int:po_id>/quantities", methods=["POST"])
@login_required
def update_purchase_quantities(po_id):
    quantities = {}
    for key, value in request.form.items():
        if not key.startswith("qty-"):
            continue
        try:
            quantities[int(key[4:])] = int(value)
        except ValueError:
            flash("Quantities must be whole numbers.", "danger")
            return redirect(url_for("orders.purchase_detail", po_id=po_id))

    try:
        update_draft_quantities(po_id, quantities)
    except InventoryError as error:
        flash(str(error), "danger")
    else:
        flash("Draft updated.", "success")
    return redirect(url_for("orders.purchase_detail", po_id=po_id))
