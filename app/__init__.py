import logging

from flask import Flask, render_template

from config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.logger.setLevel(logging.INFO)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models

    from app.auth import bp as auth_bp
    from app.customers import bp as customers_bp
    from app.dashboard import bp as dashboard_bp
    from app.orders import bp as orders_bp
    from app.products import bp as products_bp
    from app.suppliers import bp as suppliers_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(products_bp)
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(orders_bp)

    from app.cli import register_commands
    register_commands(app)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.template_filter("money")
    def money(value):
        return "" if value is None else f"{value:,.2f}"

    @app.template_filter("dt")
    def format_datetime(value):
        return "" if value is None else value.strftime("%d %b %Y %H:%M")

    @app.shell_context_processor
    def make_shell_context():
        return {
            "db": db,
            "User": models.User,
            "Category": models.Category,
            "Product": models.Product,
            "Supplier": models.Supplier,
            "ProductSupplier": models.ProductSupplier,
            "Customer": models.Customer,
            "PurchaseOrder": models.PurchaseOrder,
            "PurchaseOrderItem": models.PurchaseOrderItem,
            "SalesOrder": models.SalesOrder,
            "SalesOrderItem": models.SalesOrderItem,
            "StockMovement": models.StockMovement,
        }

    return app
