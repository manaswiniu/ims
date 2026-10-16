from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from app.extensions import db
from app.models import User


def strip(value):
    return value.strip() if isinstance(value, str) else value


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()], filters=[strip])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log in")


class UserForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(max=64)], filters=[strip]
    )
    full_name = StringField(
        "Full name", validators=[Optional(), Length(max=120)], filters=[strip]
    )
    role = SelectField("Role", choices=[("staff", "Staff"), ("admin", "Admin")], default="staff")
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create user")

    def validate_username(self, field):
        if db.session.scalar(db.select(User).filter_by(username=field.data)):
            raise ValidationError("That username is already taken.")
