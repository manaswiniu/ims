from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.customers import bp
from app.customers.forms import CustomerForm
from app.decorators import admin_required
from app.extensions import db
from app.models import Customer, SalesOrder, SalesOrderItem


def _fill_customer(customer, form):
    customer.name = form.name.data
    customer.email = form.email.data or None
    customer.phone = form.phone.data or None
    customer.address = form.address.data or None


@bp.route("/")
@login_required
def customers():
    show_inactive = request.args.get("show") == "all"
    search = request.args.get("q", "").strip()

    stmt = db.select(Customer).order_by(Customer.name)
    if not show_inactive:
        stmt = stmt.filter_by(is_active=True)
    if search:
        stmt = stmt.where(Customer.name.contains(search, autoescape=True))

    return render_template(
        "customers/list.html",
        customers=db.session.scalars(stmt).all(),
        show_inactive=show_inactive,
        search=search,
    )


@bp.route("/<int:customer_id>")
@login_required
def customer_detail(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    orders = db.session.scalars(
        db.select(SalesOrder)
        .filter_by(customer_id=customer.id)
        .options(selectinload(SalesOrder.items))
        .order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())
        .limit(50)
    ).all()
    order_count, lifetime_total = db.session.execute(
        db.select(
            func.count(func.distinct(SalesOrder.id)),
            func.coalesce(func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price), 0),
        )
        .select_from(SalesOrder)
        .join(SalesOrder.items)
        .where(SalesOrder.customer_id == customer.id)
    ).one()
    return render_template(
        "customers/detail.html",
        customer=customer,
        orders=orders,
        order_count=order_count,
        lifetime_total=lifetime_total,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer()
        _fill_customer(customer, form)
        db.session.add(customer)
        db.session.commit()
        flash(f"Customer {customer.name} added.", "success")
        if request.args.get("next") == "sale":
            return redirect(url_for("orders.new_sale", customer_id=customer.id))
        return redirect(url_for("customers.customer_detail", customer_id=customer.id))
    return render_template("customers/form.html", form=form, customer=None)


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    form = CustomerForm(obj=customer)
    if form.validate_on_submit():
        _fill_customer(customer, form)
        db.session.commit()
        flash(f"Customer {customer.name} updated.", "success")
        return redirect(url_for("customers.customer_detail", customer_id=customer.id))
    return render_template("customers/form.html", form=form, customer=customer)


@bp.route("/<int:customer_id>/toggle", methods=["POST"])
@admin_required
def toggle_customer(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    customer.is_active = not customer.is_active
    db.session.commit()
    flash(f"{customer.name} is now {'active' if customer.is_active else 'inactive'}.", "success")
    return redirect(url_for("customers.customer_detail", customer_id=customer.id))
