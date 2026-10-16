# IMS - Inventory Management System

Flask + MySQL app for a small shop: products, suppliers, sales and purchase
orders, with stock that always adds up.

**Prototype features**
- Login with **admin** and **staff** roles (staff get a 403 on admin pages)
- Products, categories and suppliers, with a preferred supplier per product
- Sales orders: take stock out in one locked transaction (all-or-nothing)
- Purchase orders: stock goes up when marked received (can't be received twice)
- Stock ledger: every stock change has a `stock_movements` row
- Low-stock dashboard with today's sales
- `flask seed`: a demo hardware store with 60 days of history


## Getting started

You need Python 3.12+ and a local MySQL 8.0 server.

```bash
# 1. Virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Packages
pip install -r requirements.txt

# 3. Local config
cp .env.example .env              # then fill in your DB password and a SECRET_KEY
```

A quick way to make a `SECRET_KEY`:
`python -c "import secrets; print(secrets.token_hex(32))"`

### 4. MySQL: create the databases and user

Run once in the MySQL shell (`mysql -u root -p`). Use the same password in `.env`.

```sql
CREATE DATABASE ims_dev  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE ims_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'ims_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON ims_dev.*  TO 'ims_user'@'localhost';
GRANT ALL PRIVILEGES ON ims_test.* TO 'ims_user'@'localhost';
FLUSH PRIVILEGES;
```

### 5. Create the tables

If you already created the tables before Sprint 2, skip to
"Upgrading an existing database" below.

```bash
flask db init                          # first time only: creates migrations/ (commit it)
flask db migrate -m "initial schema"   # writes the migration from app/models.py
flask db upgrade                       # creates the tables in ims_dev
```

Have a quick look at the file in `migrations/versions/` before `upgrade`.
Later, whenever `models.py` changes: `flask db migrate -m "..."` then `flask db upgrade`.

### 6. Load data, then run

Either the demo store (recommended):

```bash
flask seed          # asks for a password for the demo 'admin' and 'staff' users
```

or just an empty system with one admin:

```bash
flask create-admin
```

Then:

```bash
flask run
```

Open http://localhost:5000 and log in.

To reset the demo before recording a walkthrough: `flask seed --reset`
(this deletes **all** data in `ims_dev`).

## Upgrading an existing database (Sprint 2)

Only needed if you ran `flask db upgrade` before the Sprint 2 code.

```bash
flask db migrate -m "sprint 2: customers, low stock alerts, draft POs"
```

Open the new file in `migrations/versions/`. Alembic picks up the new
columns, but it does **not** notice the new `draft` value in the purchase
order status. Add this inside `upgrade()` yourself:

```python
op.alter_column(
    "purchase_orders",
    "status",
    existing_type=sa.Enum("ordered", "received", "cancelled", name="po_status"),
    type_=sa.Enum("draft", "ordered", "received", "cancelled", name="po_status"),
    existing_nullable=False,
)
```

Then `flask db upgrade`.

## Low-stock alerts and draft purchase orders

1. A sale (or a negative stock adjustment) takes a product to its reorder
   level or below.
2. In the same transaction, the product gets `low_stock_alerted_at` set and
   is added to a **draft** purchase order for its preferred supplier
   (one draft per supplier collects all its low products). The suggested
   quantity is `reorder_level * 3 - stock_qty`.
3. After the sale is saved, an alert goes to `LOW_STOCK_ALERT_EMAILS`.
   For now that just prints in the `flask run` terminal.
4. Further sales don't alert again while the product stays low.
5. Someone reviews the draft (quantities can be changed), then clicks
   **Place order**. It's received as normal.
6. Receiving resets the flag. If the product is still low after the
   delivery, a new cycle starts right away.

Products without a preferred supplier still get flagged and alerted,
but no draft is created. The dashboard shows which low products are
already on a draft or open order.


What they cover:
- a sale reduces stock and writes one movement per line
- a sale that's larger than stock raises an error and saves nothing
- receiving a purchase order adds stock, and receiving it twice fails
- staff get a 403 on admin-only pages
- after seeding, every product's `stock_qty` equals the sum of its movements
- dropping to the reorder level flags the product once, drafts a PO, sends one alert
- drafts must be placed before they can be received
- staff can add customers but not deactivate them; inactive customers can't buy

## How stock works (the important bit)

`products.stock_qty` is **only** changed by `app/services/inventory.py`:

| Function | What it does | Ledger reason |
|---|---|---|
| `create_sale` | locks products, checks every line, saves order, subtracts stock | `sale` (negative) |
| `receive_purchase_order` | locks the PO, checks it's still `ordered`, adds stock | `receipt` (positive) |
| `adjust_stock` | opening stock and manual corrections | `adjustment` |
| `create_purchase_order`, `place_purchase_order`, `update_draft_quantities`, `cancel_purchase_order` | no stock change | - |

Each one is a single transaction. Product rows are locked with
`SELECT ... FOR UPDATE` (SQLAlchemy `with_for_update()`), so two people
selling the last item at the same time can't both succeed. If any check
fails, everything is rolled back.

Because of that, for any product, `SUM(stock_movements.quantity_change) = stock_qty`.

## Who can do what

| | Admin | Staff |
|---|---|---|
| Dashboard, view products / suppliers / orders | yes | yes |
| Record sales, create / place / receive / cancel purchase orders | yes | yes |
| Add and edit customers | yes | yes |
| Deactivate customers | yes | 403 |
| Create, edit, deactivate products, categories, suppliers | yes | 403 |
| Link products to suppliers, adjust stock | yes | 403 |
| Manage users | yes | 403 |

## Project layout

```
application.py            entry point (flask run / Elastic Beanstalk later)
config.py                 settings from environment variables (+ TestConfig)
app/
  __init__.py             create_app(): extensions, blueprints, error pages
  extensions.py           db, migrate, login_manager, csrf
  models.py               all database tables
  decorators.py           @admin_required
  services/inventory.py   ALL stock-changing logic, low-stock flags, auto drafts
  services/notifications.py  alert "emails" (logged for now)
  seed.py                 demo hardware store
  cli.py                  flask create-admin / flask seed
  auth/                   login, logout, user management
  dashboard/              low-stock dashboard
  products/               products, categories, stock adjustments
  suppliers/              suppliers and product links
  customers/              customer screens
  orders/                 sales and purchase orders
  templates/              base.html, _macros.html, one folder per blueprint
tests/                    pytest suite (uses ims_test)
```

