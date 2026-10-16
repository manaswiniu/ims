from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.auth.forms import LoginForm, UserForm
from app.decorators import admin_required
from app.extensions import db
from app.models import User


def _safe_next_url():
    next_url = request.args.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("dashboard.index")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).filter_by(username=form.username.data))
        if user is None or not user.is_active or not user.check_password(form.password.data):
            flash("Invalid username or password.", "danger")
        else:
            login_user(user, remember=form.remember_me.data)
            return redirect(_safe_next_url())
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/users")
@admin_required
def users():
    all_users = db.session.scalars(db.select(User).order_by(User.username)).all()
    return render_template("auth/users.html", users=all_users)


@bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def new_user():
    form = UserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            full_name=form.full_name.data or None,
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f"User {user.username} created.", "success")
        return redirect(url_for("auth.users"))
    return render_template("auth/user_form.html", form=form)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "warning")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        flash(f"{user.username} is now {'active' if user.is_active else 'inactive'}.", "success")
    return redirect(url_for("auth.users"))
