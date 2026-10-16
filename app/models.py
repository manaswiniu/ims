from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("admin", "staff", name="user_role"), nullable=False, default="staff")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user is None or not user.is_active:
        return None
    return user


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    products = db.relationship("Product", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("unit_price >= 0", name="ck_products_unit_price"),
        db.CheckConstraint("cost_price >= 0", name="ck_products_cost_price"),
        db.CheckConstraint("stock_qty >= 0", name="ck_products_stock_qty"),
        db.CheckConstraint("reorder_level >= 0", name="ck_products_reorder_level"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=0)
    low_stock_alerted_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    category = db.relationship("Category", back_populates="products")
    supplier_links = db.relationship("ProductSupplier", back_populates="product")
    movements = db.relationship("StockMovement", back_populates="product")

    @property
    def is_low_stock(self):
        return self.stock_qty <= self.reorder_level

    @property
    def label(self):
        return f"{self.sku} - {self.name}"

    @property
    def suggested_reorder_qty(self):
        return max(self.reorder_level * 3 - self.stock_qty, 1)

    @property
    def preferred_supplier(self):
        for link in self.supplier_links:
            if link.is_preferred:
                return link.supplier
        return None

    def __repr__(self):
        return f"<Product {self.sku} qty={self.stock_qty}>"


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    product_links = db.relationship("ProductSupplier", back_populates="supplier")
    purchase_orders = db.relationship("PurchaseOrder", back_populates="supplier")

    def __repr__(self):
        return f"<Supplier {self.name}>"


class ProductSupplier(db.Model):
    __tablename__ = "product_suppliers"
    __table_args__ = (
        db.UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    is_preferred = db.Column(db.Boolean, nullable=False, default=False)

    product = db.relationship("Product", back_populates="supplier_links")
    supplier = db.relationship("Supplier", back_populates="product_links")


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    sales_orders = db.relationship("SalesOrder", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.name}>"


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.Enum("draft", "ordered", "received", "cancelled", name="po_status"),
        nullable=False,
        default="ordered",
    )
    auto_generated = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    order_date = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    received_date = db.Column(db.DateTime)
    notes = db.Column(db.String(255))

    supplier = db.relationship("Supplier", back_populates="purchase_orders")
    created_by = db.relationship("User")
    items = db.relationship(
        "PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan"
    )

    @property
    def total(self):
        return sum(item.line_total for item in self.items)

    def __repr__(self):
        return f"<PurchaseOrder #{self.id} {self.status}>"


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_po_items_quantity"),
        db.CheckConstraint("unit_cost >= 0", name="ck_po_items_unit_cost"),
    )

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)

    purchase_order = db.relationship("PurchaseOrder", back_populates="items")
    product = db.relationship("Product")

    @property
    def line_total(self):
        return self.quantity * self.unit_cost


class SalesOrder(db.Model):
    __tablename__ = "sales_orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    notes = db.Column(db.String(255))

    customer = db.relationship("Customer", back_populates="sales_orders")
    created_by = db.relationship("User")
    items = db.relationship(
        "SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan"
    )

    @property
    def total(self):
        return sum(item.line_total for item in self.items)

    def __repr__(self):
        return f"<SalesOrder #{self.id}>"


class SalesOrderItem(db.Model):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_so_items_quantity"),
        db.CheckConstraint("unit_price >= 0", name="ck_so_items_unit_price"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey("sales_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    sales_order = db.relationship("SalesOrder", back_populates="items")
    product = db.relationship("Product")

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity_change = db.Column(db.Integer, nullable=False)
    reason = db.Column(
        db.Enum("sale", "receipt", "adjustment", name="movement_reason"), nullable=False
    )
    sales_order_id = db.Column(db.Integer, db.ForeignKey("sales_orders.id"))
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    product = db.relationship("Product", back_populates="movements")
    sales_order = db.relationship("SalesOrder")
    purchase_order = db.relationship("PurchaseOrder")
    user = db.relationship("User")

    def __repr__(self):
        return f"<StockMovement product={self.product_id} {self.quantity_change:+d} {self.reason}>"
