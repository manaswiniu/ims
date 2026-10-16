from sqlalchemy import func

from app.extensions import db
from app.models import Product, StockMovement
from app.seed import seed_demo_data


def test_seeded_stock_matches_the_ledger():
    summary = seed_demo_data("password123", days=15)
    assert summary["products"] == 40
    assert summary["sales orders"] > 0

    rows = db.session.execute(
        db.select(
            Product.sku,
            Product.stock_qty,
            func.coalesce(func.sum(StockMovement.quantity_change), 0),
        )
        .outerjoin(StockMovement, StockMovement.product_id == Product.id)
        .group_by(Product.id, Product.sku, Product.stock_qty)
    ).all()

    mismatches = [(sku, stock, total) for sku, stock, total in rows if stock != total]
    assert mismatches == []
