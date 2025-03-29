from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, DecimalField, SelectField, DateField
from wtforms.validators import DataRequired
from db_models import ExpenseCategory

class ExpenseForm(FlaskForm):
    description = StringField("Description", validators=[DataRequired()])
    amount = DecimalField("Amount (HKD)", validators=[DataRequired()])

    category = SelectField(
        "Category",
        choices=[(cat.value, cat.value) for cat in ExpenseCategory],
        validators=[DataRequired()]
    )

    expense_date = DateField("Date of Expense", validators=[DataRequired()])
    button = SubmitField("Submit")

class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register User")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")