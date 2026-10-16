from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.orm import contains_eager

from app.decorators import admin_required
from app.extensions import db
from app.models import Product, ProductSupplier, PurchaseOrder, Supplier
from app.suppliers import bp
from app.suppliers.forms import LinkProductForm, SupplierForm


def _fill_supplier(supplier, form):
    supplier.name = form.name.data
    supplier.contact_name = form.contact_name.data or None
    supplier.email = form.email.data or None
    supplier.phone = form.phone.data or None
    supplier.address = form.address.data or None


def _link_form_for(supplier):
    linked_ids = {link.product_id for link in supplier.product_links}
    products = db.session.scalars(
        db.select(Product).filter_by(is_active=True).order_by(Product.sku)
    ).all()
    form = LinkProductForm()
    form.product_id.choices = [(p.id, p.label) for p in products if p.id not in linked_ids]
    return form


def _get_link_or_404(supplier_id, link_id):
    link = db.get_or_404(ProductSupplier, link_id)
    if link.supplier_id != supplier_id:
        abort(404)
    return link


def _make_preferred(link):
    db.session.execute(
        db.update(ProductSupplier)
        .where(ProductSupplier.product_id == link.product_id)
        .values(is_preferred=False)
    )
    link.is_preferred = True


@bp.route("/")
@login_required
def suppliers():
    show_inactive = request.args.get("show") == "all"
    stmt = db.select(Supplier).order_by(Supplier.name)
    if not show_inactive:
        stmt = stmt.filter_by(is_active=True)
    return render_template(
        "suppliers/list.html",
        suppliers=db.session.scalars(stmt).all(),
        show_inactive=show_inactive,
    )


@bp.route("/<int:supplier_id>")
@login_required
def supplier_detail(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    links = db.session.scalars(
        db.select(ProductSupplier)
        .filter_by(supplier_id=supplier.id)
        .join(ProductSupplier.product)
        .options(contains_eager(ProductSupplier.product))
        .order_by(Product.sku)
    ).all()
    recent_pos = db.session.scalars(
        db.select(PurchaseOrder)
        .filter_by(supplier_id=supplier.id)
        .order_by(PurchaseOrder.order_date.desc())
        .limit(10)
    ).all()
    return render_template(
        "suppliers/detail.html",
        supplier=supplier,
        links=links,
        recent_pos=recent_pos,
        link_form=_link_form_for(supplier),
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def new_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier()
        _fill_supplier(supplier, form)
        db.session.add(supplier)
        db.session.commit()
        flash(f"Supplier {supplier.name} created.", "success")
        return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier.id))
    return render_template("suppliers/form.html", form=form, supplier=None)


@bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_supplier(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    form = SupplierForm(obj=supplier)
    if form.validate_on_submit():
        _fill_supplier(supplier, form)
        db.session.commit()
        flash(f"Supplier {supplier.name} updated.", "success")
        return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier.id))
    return render_template("suppliers/form.html", form=form, supplier=supplier)


@bp.route("/<int:supplier_id>/toggle", methods=["POST"])
@admin_required
def toggle_supplier(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    supplier.is_active = not supplier.is_active
    db.session.commit()
    flash(f"{supplier.name} is now {'active' if supplier.is_active else 'inactive'}.", "success")
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier.id))


@bp.route("/<int:supplier_id>/products", methods=["POST"])
@admin_required
def link_product(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    form = _link_form_for(supplier)
    if form.validate_on_submit():
        link = ProductSupplier(supplier_id=supplier.id, product_id=form.product_id.data)
        db.session.add(link)
        if form.is_preferred.data:
            _make_preferred(link)
        db.session.commit()
        flash("Product linked.", "success")
    else:
        flash("Pick a product to link.", "warning")
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier.id))


@bp.route("/<int:supplier_id>/products/<int:link_id>/preferred", methods=["POST"])
@admin_required
def set_preferred(supplier_id, link_id):
    link = _get_link_or_404(supplier_id, link_id)
    _make_preferred(link)
    db.session.commit()
    flash(f"{link.supplier.name} is now the preferred supplier for {link.product.sku}.", "success")
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier_id))


@bp.route("/<int:supplier_id>/products/<int:link_id>/remove", methods=["POST"])
@admin_required
def unlink_product(supplier_id, link_id):
    link = _get_link_or_404(supplier_id, link_id)
    db.session.delete(link)
    db.session.commit()
    flash("Product unlinked.", "success")
    return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier_id))
