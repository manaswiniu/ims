from flask_wtf import FlaskForm
from wtforms import (
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from app.auth.forms import strip
from app.extensions import db
from app.models import Category, Product


def upper(value):
    return value.upper() if isinstance(value, str) else value


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)], filters=[strip])
    description = StringField(
        "Description", validators=[Optional(), Length(max=255)], filters=[strip]
    )
    submit = SubmitField("Save")

    def __init__(self, *args, editing_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing_id = editing_id

    def validate_name(self, field):
        existing = db.session.scalar(db.select(Category).filter_by(name=field.data))
        if existing and existing.id != self.editing_id:
            raise ValidationError("A category with that name already exists.")


class ProductForm(FlaskForm):
    sku = StringField("SKU", validators=[DataRequired(), Length(max=50)], filters=[strip, upper])
    name = StringField("Name", validators=[DataRequired(), Length(max=150)], filters=[strip])
    description = TextAreaField("Description", validators=[Optional()])
    category_id = SelectField("Category", coerce=int)
    unit_price = DecimalField(
        "Selling price", places=2, validators=[InputRequired(), NumberRange(min=0)]
    )
    cost_price = DecimalField(
        "Cost price", places=2, validators=[InputRequired(), NumberRange(min=0)]
    )
    reorder_level = IntegerField(
        "Reorder level", default=0, validators=[InputRequired(), NumberRange(min=0)]
    )
    submit = SubmitField("Save")

    def __init__(self, *args, editing_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing_id = editing_id

    def validate_sku(self, field):
        existing = db.session.scalar(db.select(Product).filter_by(sku=field.data))
        if existing and existing.id != self.editing_id:
            raise ValidationError("That SKU is already used by another product.")


class NewProductForm(ProductForm):
    opening_stock = IntegerField(
        "Opening stock", default=0, validators=[InputRequired(), NumberRange(min=0)]
    )


class StockAdjustmentForm(FlaskForm):
    quantity_change = IntegerField(
        "Change (+ to add, - to remove)", validators=[InputRequired()]
    )
    note = StringField(
        "Reason", validators=[DataRequired(), Length(max=255)], filters=[strip]
    )
    submit = SubmitField("Save adjustment")

    def validate_quantity_change(self, field):
        if field.data == 0:
            raise ValidationError("The change can't be zero.")
