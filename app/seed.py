import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models import (
    Category,
    Customer,
    Product,
    ProductSupplier,
    PurchaseOrder,
    SalesOrder,
    StockMovement,
    Supplier,
    User,
)
from app.services import inventory

CATALOGUE = {
    "Hand Tools": [
        ("HT-001", "Claw Hammer 16oz", "18.99", "9.50", 5),
        ("HT-002", "Screwdriver Set 6pc", "14.99", "6.80", 5),
        ("HT-003", "Adjustable Wrench 10in", "16.49", "7.90", 4),
        ("HT-004", "Tape Measure 25ft", "12.99", "5.60", 6),
        ("HT-005", "Utility Knife", "8.99", "3.40", 6),
        ("HT-006", "Needle-Nose Pliers", "11.49", "4.90", 4),
        ("HT-007", "Hacksaw", "13.99", "6.20", 3),
    ],
    "Power Tools": [
        ("PT-001", "Cordless Drill 18V", "89.00", "52.00", 2),
        ("PT-002", "Circular Saw 7-1/4in", "119.00", "71.00", 2),
        ("PT-003", "Random Orbit Sander", "64.99", "36.00", 2),
        ("PT-004", "Jigsaw", "74.99", "41.00", 2),
        ("PT-005", "Drill Bit Set 21pc", "24.99", "11.50", 4),
        ("PT-006", "Angle Grinder 4-1/2in", "59.99", "33.00", 2),
    ],
    "Fasteners": [
        ("FS-001", "Wood Screws #8 x 1-1/4in (100)", "7.49", "2.90", 10),
        ("FS-002", "Drywall Screws 1-5/8in (1lb)", "8.99", "3.60", 10),
        ("FS-003", "Common Nails 3in (1lb)", "5.49", "2.10", 10),
        ("FS-004", "Hex Bolts 3/8 x 2in (25)", "9.99", "4.20", 8),
        ("FS-005", "Wall Anchor Kit (50)", "6.99", "2.50", 8),
        ("FS-006", "Washers 3/8in (50)", "4.99", "1.80", 8),
        ("FS-007", "Cable Ties 8in (100)", "5.99", "2.20", 8),
    ],
    "Plumbing": [
        ("PL-001", "PTFE Thread Tape", "2.49", "0.80", 12),
        ("PL-002", "PVC Pipe 1/2in x 10ft", "6.99", "3.10", 6),
        ("PL-003", "Pipe Wrench 14in", "27.99", "13.50", 2),
        ("PL-004", "Faucet Cartridge", "18.49", "8.70", 3),
        ("PL-005", "Sink Plunger", "9.99", "4.10", 4),
        ("PL-006", "Compression Fittings 1/2in (2)", "7.99", "3.30", 6),
        ("PL-007", "Silicone Sealant Clear", "7.49", "3.00", 8),
    ],
    "Electrical": [
        ("EL-001", "LED Bulb 60W Equivalent (4pk)", "12.99", "6.00", 8),
        ("EL-002", "Extension Cord 25ft", "19.99", "9.40", 4),
        ("EL-003", "Electrical Tape (3pk)", "5.99", "2.10", 10),
        ("EL-004", "Wire Stripper", "15.99", "7.20", 3),
        ("EL-005", "Duplex Outlet 15A", "2.99", "1.10", 12),
        ("EL-006", "Light Switch Single Pole", "3.49", "1.30", 12),
        ("EL-007", "Voltage Tester", "21.99", "10.50", 3),
    ],
    "Paint & Supplies": [
        ("PS-001", "Interior Paint White 1gal", "34.99", "18.00", 4),
        ("PS-002", "Paint Roller Kit 9in", "14.99", "6.40", 5),
        ("PS-003", "Brush Set 3pc", "11.99", "4.80", 5),
        ("PS-004", "Painter's Tape 1.88in", "7.99", "3.20", 10),
        ("PS-005", "Drop Cloth 9x12ft", "9.99", "4.10", 5),
        ("PS-006", "Sandpaper Assortment (25)", "8.49", "3.30", 6),
    ],
}

SUPPLIERS = [
    ("Northline Tool Supply", "Dana Reyes", "orders@northline.example.com", "555-0101",
     ["Hand Tools", "Power Tools"]),
    ("Fastenright Distributors", "Sam Ortiz", "sales@fastenright.example.com", "555-0102",
     ["Fasteners"]),
    ("ClearFlow Plumbing Wholesale", "Priya Nair", "trade@clearflow.example.com", "555-0103",
     ["Plumbing"]),
    ("Brightwire Electrical", "Tom Becker", "orders@brightwire.example.com", "555-0104",
     ["Electrical"]),
    ("ColorCoat Paint Co.", "Ana Silva", "hello@colorcoat.example.com", "555-0105",
     ["Paint & Supplies"]),
]

CUSTOMERS = [
    ("Walk-in Customer", None, None),
    ("Maple Street Builders", "office@maplestreet.example.com", "555-0201"),
    ("J. Alvarez Renovations", "jalvarez@example.com", "555-0202"),
    ("Greenleaf Property Management", "maintenance@greenleaf.example.com", "555-0203"),
    ("Patel Home Repairs", "patelrepairs@example.com", "555-0204"),
    ("Riverside Community Center", "facilities@riverside.example.com", "555-0205"),
    ("K. Johnson", None, "555-0206"),
    ("Summit Roofing", "jobs@summitroofing.example.com", "555-0207"),
    ("Lin Okafor", "lin.okafor@example.com", None),
    ("Harbor View Apartments", "super@harborview.example.com", "555-0209"),
    ("Oak & Iron Carpentry", "shop@oakandiron.example.com", "555-0210"),
    ("Mia Thompson", None, "555-0211"),
    ("Sunrise Daycare", "admin@sunrisedaycare.example.com", "555-0212"),
    ("D. Novak", None, None),
    ("Westside Auto Body", "parts@westsideauto.example.com", "555-0214"),
]


def database_has_data():
    return bool(
        db.session.scalar(db.select(func.count(User.id)))
        or db.session.scalar(db.select(func.count(Product.id)))
    )


def clear_all_data():
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()


def _create_master_data(password):
    admin = User(username="admin", full_name="Demo Admin", role="admin")
    staff = User(username="staff", full_name="Demo Staff", role="staff")
    admin.set_password(password)
    staff.set_password(password)
    db.session.add_all([admin, staff])

    categories = {}
    products = []
    for category_name, items in CATALOGUE.items():
        category = Category(name=category_name)
        categories[category_name] = category
        db.session.add(category)
        for sku, name, price, cost, reorder in items:
            product = Product(
                sku=sku,
                name=name,
                category=category,
                unit_price=Decimal(price),
                cost_price=Decimal(cost),
                reorder_level=reorder,
                stock_qty=0,
            )
            products.append(product)
            db.session.add(product)

    for name, contact, email, phone, preferred_for in SUPPLIERS:
        supplier = Supplier(name=name, contact_name=contact, email=email, phone=phone)
        db.session.add(supplier)
        for product in products:
            if product.category.name in preferred_for:
                db.session.add(
                    ProductSupplier(product=product, supplier=supplier, is_preferred=True)
                )
        if name == "Northline Tool Supply":
            for product in products:
                if product.category.name == "Fasteners":
                    db.session.add(ProductSupplier(product=product, supplier=supplier))

    customers = [
        Customer(name=name, email=email, phone=phone) for name, email, phone in CUSTOMERS
    ]
    db.session.add_all(customers)

    db.session.commit()
    return admin, staff, products, customers


def seed_demo_data(password, days=60, rng_seed=42):
    rng = random.Random(rng_seed)
    admin, staff, products, customers = _create_master_data(password)

    admin_id, staff_id = admin.id, staff.id
    walk_in_id = customers[0].id
    customer_ids = [c.id for c in customers]
    product_ids = [p.id for p in products]
    weights = [3 if p.unit_price < 10 else 2 if p.unit_price < 30 else 1 for p in products]

    first_day = date.today() - timedelta(days=days)
    now = datetime.now()

    opening_time = datetime.combine(first_day, time(8, 0))
    for product in products:
        quantity = product.reorder_level * 3 + rng.randint(5, 15)
        inventory.adjust_stock(
            product.id, quantity, admin_id, "Opening stock", when=opening_time, send_alerts=False
        )

    pending_receipts = []

    for day in range(days + 1):
        today = first_day + timedelta(days=day)
        is_last_day = day == days

        for due_day, po_id in list(pending_receipts):
            if due_day == day:
                inventory.receive_purchase_order(
                    po_id, staff_id, when=datetime.combine(today, time(8, 30)), send_alerts=False
                )
                pending_receipts.remove((due_day, po_id))

        order_count = rng.randint(2, 4) if is_last_day else rng.randint(3, 8)
        for _ in range(order_count):
            when = datetime.combine(today, time(rng.randint(9, 16), rng.randint(0, 59)))
            if when > now:
                continue
            chosen = set(rng.choices(product_ids, weights=weights, k=rng.randint(1, 3)))
            lines = []
            for product_id in chosen:
                product = db.session.get(Product, product_id)
                wanted = rng.randint(1, 5) if product.unit_price < 10 else rng.randint(1, 2)
                quantity = min(wanted, product.stock_qty)
                if quantity > 0:
                    lines.append((product_id, quantity))
            if not lines:
                continue
            customer_id = walk_in_id if rng.random() < 0.4 else rng.choice(customer_ids)
            seller_id = staff_id if rng.random() < 0.8 else admin_id
            inventory.create_sale(customer_id, lines, seller_id, when=when, send_alerts=False)

        if is_last_day:
            continue
        draft_ids = db.session.scalars(
            db.select(PurchaseOrder.id).filter_by(status="draft").order_by(PurchaseOrder.id)
        ).all()
        for po_id in draft_ids:
            inventory.place_purchase_order(po_id, when=datetime.combine(today, time(17, 30)))
            pending_receipts.append((day + rng.randint(2, 4), po_id))

    return {
        "users": db.session.scalar(db.select(func.count(User.id))),
        "categories": db.session.scalar(db.select(func.count(Category.id))),
        "products": db.session.scalar(db.select(func.count(Product.id))),
        "suppliers": db.session.scalar(db.select(func.count(Supplier.id))),
        "customers": db.session.scalar(db.select(func.count(Customer.id))),
        "sales orders": db.session.scalar(db.select(func.count(SalesOrder.id))),
        "purchase orders": db.session.scalar(db.select(func.count(PurchaseOrder.id))),
        "draft purchase orders": db.session.scalar(
            db.select(func.count(PurchaseOrder.id)).filter_by(status="draft")
        ),
        "stock movements": db.session.scalar(db.select(func.count(StockMovement.id))),
    }
