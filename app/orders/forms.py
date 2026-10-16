from flask_wtf import FlaskForm
from wtforms import (
    DecimalField,
    FieldList,
    Form,
    FormField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import Length, NumberRange, Optional

from app.auth.forms import strip

LINE_ROWS = 5


class SaleLineForm(Form):
    product_id = SelectField("Product", coerce=int, default=0)
    quantity = IntegerField("Quantity", validators=[Optional(), NumberRange(min=1)])


class PurchaseLineForm(Form):
    product_id = SelectField("Product", coerce=int, default=0)
    quantity = IntegerField("Quantity", validators=[Optional(), NumberRange(min=1)])
    unit_cost = DecimalField(
        "Unit cost", places=2, validators=[Optional(), NumberRange(min=0)]
    )


class OrderFormBase(FlaskForm):
    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False

        used = [line for line in self.lines if line.product_id.data or line.quantity.data]
        if not used:
            self.form_errors.append("Add at least one product.")
            return False
        if any(not line.product_id.data or not line.quantity.data for line in used):
            self.form_errors.append("Each line needs both a product and a quantity.")
            return False
        return True

    def set_product_choices(self, choices):
        for line in self.lines:
            line.product_id.choices = choices


class SaleForm(OrderFormBase):
    customer_id = SelectField("Customer", coerce=int)
    lines = FieldList(FormField(SaleLineForm), min_entries=LINE_ROWS)
    notes = StringField("Notes", validators=[Optional(), Length(max=255)], filters=[strip])
    submit = SubmitField("Record sale")

    def line_items(self):
        return [
            (line.product_id.data, line.quantity.data)
            for line in self.lines
            if line.product_id.data
        ]


class PurchaseOrderForm(OrderFormBase):
    supplier_id = SelectField("Supplier", coerce=int)
    lines = FieldList(FormField(PurchaseLineForm), min_entries=LINE_ROWS)
    notes = StringField("Notes", validators=[Optional(), Length(max=255)], filters=[strip])
    submit = SubmitField("Create purchase order")

    def line_items(self):
        return [
            (line.product_id.data, line.quantity.data, line.unit_cost.data)
            for line in self.lines
            if line.product_id.data
        ]
