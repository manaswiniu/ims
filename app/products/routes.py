from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.decorators import admin_required
from app.extensions import db
from app.models import Category, Product, StockMovement
from app.products import bp
from app.products.forms import CategoryForm, NewProductForm, ProductForm, StockAdjustmentForm
from app.services.inventory import InventoryError, adjust_stock


def _category_choices(current=None):
    categories = db.session.scalars(
        db.select(Category).filter_by(is_active=True).order_by(Category.name)
    ).all()
    if current is not None and current not in categories:
        categories.append(current)
    return [(c.id, c.name) for c in categories]


def _fill_product(product, form):
    product.sku = form.sku.data
    product.name = form.name.data
    product.description = form.description.data or None
    product.category_id = form.category_id.data
    product.unit_price = form.unit_price.data
    product.cost_price = form.cost_price.data
    product.reorder_level = form.reorder_level.data


@bp.route("/products")
@login_required
def products():
    show_inactive = request.args.get("show") == "all"
    stmt = db.select(Product).options(joinedload(Product.category)).order_by(Product.name)
    if not show_inactive:
        stmt = stmt.filter_by(is_active=True)
    return render_template(
        "products/list.html",
        products=db.session.scalars(stmt).all(),
        show_inactive=show_inactive,
    )


@bp.route("/products/<int:product_id>")
@login_required
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    movements = db.session.scalars(
        db.select(StockMovement)
        .filter_by(product_id=product.id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(50)
    ).all()
    return render_template("products/detail.html", product=product, movements=movements)


@bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def new_product():
    form = NewProductForm()
    form.category_id.choices = _category_choices()

    if form.validate_on_submit():
        product = Product(stock_qty=0)
        _fill_product(product, form)
        db.session.add(product)
        db.session.commit()

        if form.opening_stock.data:
            adjust_stock(product.id, form.opening_stock.data, current_user.id, "Opening stock")

        flash(f"Product {product.sku} created.", "success")
        return redirect(url_for("products.product_detail", product_id=product.id))
    return render_template("products/form.html", form=form, product=None)


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    product = db.get_or_404(Product, product_id)
    form = ProductForm(obj=product, editing_id=product.id)
    form.category_id.choices = _category_choices(current=product.category)

    if form.validate_on_submit():
        _fill_product(product, form)
        db.session.commit()
        flash(f"Product {product.sku} updated.", "success")
        return redirect(url_for("products.product_detail", product_id=product.id))
    return render_template("products/form.html", form=form, product=product)


@bp.route("/products/<int:product_id>/toggle", methods=["POST"])
@admin_required
def toggle_product(product_id):
    product = db.get_or_404(Product, product_id)
    product.is_active = not product.is_active
    db.session.commit()
    flash(f"{product.sku} is now {'active' if product.is_active else 'inactive'}.", "success")
    return redirect(url_for("products.product_detail", product_id=product.id))


@bp.route("/products/<int:product_id>/adjust", methods=["GET", "POST"])
@admin_required
def adjust_product_stock(product_id):
    product = db.get_or_404(Product, product_id)
    form = StockAdjustmentForm()

    if form.validate_on_submit():
        try:
            adjust_stock(product.id, form.quantity_change.data, current_user.id, form.note.data)
        except InventoryError as error:
            flash(str(error), "danger")
        else:
            flash("Stock adjusted.", "success")
            return redirect(url_for("products.product_detail", product_id=product.id))
    return render_template("products/adjust.html", form=form, product=product)


@bp.route("/categories")
@login_required
def categories():
    show_inactive = request.args.get("show") == "all"
    stmt = db.select(Category).order_by(Category.name)
    if not show_inactive:
        stmt = stmt.filter_by(is_active=True)
    return render_template(
        "products/categories.html",
        categories=db.session.scalars(stmt).all(),
        show_inactive=show_inactive,
    )


@bp.route("/categories/new", methods=["GET", "POST"])
@admin_required
def new_category():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(name=form.name.data, description=form.description.data or None)
        db.session.add(category)
        db.session.commit()
        flash(f"Category {category.name} created.", "success")
        return redirect(url_for("products.categories"))
    return render_template("products/category_form.html", form=form, category=None)


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_category(category_id):
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(obj=category, editing_id=category.id)
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data or None
        db.session.commit()
        flash(f"Category {category.name} updated.", "success")
        return redirect(url_for("products.categories"))
    return render_template("products/category_form.html", form=form, category=category)


@bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@admin_required
def toggle_category(category_id):
    category = db.get_or_404(Category, category_id)
    category.is_active = not category.is_active
    db.session.commit()
    flash(f"{category.name} is now {'active' if category.is_active else 'inactive'}.", "success")
    return redirect(url_for("products.categories"))
