from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.auth.forms import strip


class SupplierForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=150)], filters=[strip])
    contact_name = StringField(
        "Contact person", validators=[Optional(), Length(max=120)], filters=[strip]
    )
    email = StringField("Email", validators=[Optional(), Length(max=120)], filters=[strip])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)], filters=[strip])
    address = StringField("Address", validators=[Optional(), Length(max=255)], filters=[strip])
    submit = SubmitField("Save")


class LinkProductForm(FlaskForm):
    product_id = SelectField("Product", coerce=int)
    is_preferred = BooleanField("Preferred supplier for this product")
    submit = SubmitField("Link product")
