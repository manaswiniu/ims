import click

from app.extensions import db
from app.models import User


def register_commands(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, password):
        username = username.strip()
        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")
        if db.session.scalar(db.select(User).filter_by(username=username)):
            raise click.ClickException(f"User '{username}' already exists.")

        user = User(username=username, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin '{username}' created.")

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Delete ALL existing data first.")
    @click.option("--days", default=60, show_default=True, help="Days of sales history.")
    @click.option(
        "--password",
        prompt="Password for the demo 'admin' and 'staff' users",
        hide_input=True,
        confirmation_prompt=True,
    )
    def seed(reset, days, password):
        from app.seed import clear_all_data, database_has_data, seed_demo_data

        if len(password) < 8:
            raise click.ClickException("Password must be at least 8 characters.")
        if database_has_data():
            if not reset:
                raise click.ClickException(
                    "The database already has data. Use `flask seed --reset` to wipe it first."
                )
            click.confirm("This deletes ALL data in the database. Continue?", abort=True)
            clear_all_data()

        click.echo(f"Seeding {days} days of history...")
        summary = seed_demo_data(password, days=days)
        for name, count in summary.items():
            click.echo(f"  {name}: {count}")
        click.echo("Done. Log in as 'admin' or 'staff' with the password you just entered.")
