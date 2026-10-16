from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.auth.forms import strip


class CustomerForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=150)], filters=[strip])
    email = StringField("Email", validators=[Optional(), Length(max=120)], filters=[strip])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)], filters=[strip])
    address = StringField("Address", validators=[Optional(), Length(max=255)], filters=[strip])
    submit = SubmitField("Save")
