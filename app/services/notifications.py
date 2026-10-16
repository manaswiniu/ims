from flask import current_app


def send_email(recipients, subject, body):
    current_app.logger.info(
        "EMAIL to %s\nSubject: %s\n\n%s", ", ".join(recipients) or "(nobody)", subject, body
    )


def notify_low_stock(products):
    recipients = current_app.config["LOW_STOCK_ALERT_EMAILS"]
    lines = [
        f"{p.sku}  {p.name}: {p.stock_qty} left (reorder level {p.reorder_level})"
        for p in products
    ]
    body = (
        "These products just reached their reorder level:\n\n"
        + "\n".join(lines)
        + "\n\nDraft purchase orders have been created for any with a preferred supplier."
    )
    count = len(products)
    subject = f"Low stock: {count} product{'s' if count != 1 else ''}"
    send_email(recipients, subject, body)
