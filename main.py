from flask import Flask, request, abort, render_template, redirect, url_for, flash, session
from flask_bootstrap import Bootstrap5
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, current_user, get_jwt, set_access_cookies, unset_jwt_cookies, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from db_models import db, User, ExpenseCategory, ExpenseEntry
from forms import ExpenseForm, RegisterForm, LoginForm
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dashboard_functions import filter_category_month_year, month_and_category_graph
from functools import wraps

#------------------------Config App and Tokens------------------------
app = Flask(__name__)
load_dotenv(".env")
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
csrf = CSRFProtect(app)
bootstrap = Bootstrap5(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_api.db'
db.init_app(app)

with app.app_context():
    db.create_all()

#Implement JWT Token Generator
jwt = JWTManager()
app.config['JWT_SECRET_KEY'] = os.environ.get("JWT_SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)  # Access token expiry
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=3)  # Refresh token expiry

# Configure Flask-JWT-Extended to use cookies:
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SECURE"] = True  # HTTPS only
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config["JWT_CSRF_CHECK_FORM"] = True       # Look for CSRF in forms
app.config["JWT_ACCESS_COOKIE_NAME"] = "access_token_cookie"

jwt.init_app(app)

# Register a callback function that takes whatever object is passed in as the
# identity when creating JWTs and converts it to a JSON serializable format.
@jwt.user_identity_loader
def user_identity_lookup(user):
    return user

# Register a callback function that loads a user from your database whenever
# a protected route is accessed. This should return any python object on a
# successful lookup, or None if the lookup failed for any reason (for example
# if the user has been deleted from the database).
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.filter_by(id=identity).one_or_none()


#------------------------Handling Errors------------------------


# handling logout and redirect to login page when access/refresh token expires
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    if session.get('redirect_count', 0) >= 3:  # handling case when refresh token expires
        # Clear the redirect count
        session.pop('redirect_count', None)

        flash('Your credentials have expired, please login again.')
        response = redirect(url_for('login'))
        unset_jwt_cookies(response)
        return response

    # Increment the redirect count upon redirect
    session['redirect_count'] = session.get('redirect_count', 0) + 1

    return redirect(url_for('refresh')) # handling case when access token expires

@jwt.invalid_token_loader
def invalid_token_callback(jwr_header):
    abort(401)

@jwt.unauthorized_loader
def missing_token_callback(jwr_header):
    abort(401)

def entry_ownership_required(function):
    @wraps(function)
    def decorated_function(expense_id, *args, **kwargs):
        expense_entry = ExpenseEntry.query.get_or_404(expense_id)
        user_id = expense_entry.user_id  #get author_id from anime list from anime entry
        if not user_id == current_user.id :  # If both not owner and not admin
            abort(403)  # Forbidden access
        return function(expense_id, *args, **kwargs)
    return decorated_function


#------------------------Handling Routes------------------------

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=['GET','POST'])
def register():
    register_form = RegisterForm()

    if register_form.validate_on_submit():
        check_is_registered = db.session.execute(db.select(User).where(User.email == request.form.get("email"))).scalar()

        if check_is_registered:
            flash('That Email is already registered. Please Login instead!')
            return redirect(url_for('login'))

        #use sha256 encryption on password and add salt
        hash_and_salted_password = generate_password_hash(
            register_form.password.data,
            method="pbkdf2:sha256",
            salt_length=8
        )

        new_user = User(
            email=register_form.email.data,
            name=register_form.name.data,
            password=hash_and_salted_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Successfully Registered. Please Proceed with Login.')
        return redirect(url_for('login'))

    return render_template("register.html", register_form=register_form)

@app.route("/login", methods=['GET','POST'])
def login():
    login_form = LoginForm()
    user = db.session.execute(db.select(User).where(User.email == request.form.get("email"))).scalar()

    if request.args.get('message'):
        flash(request.args.get('message'))

    if login_form.validate_on_submit():
        if not user: #if the email is not registered
            flash('That Email does not exist. Please Try Again!')
            return redirect(url_for('login'))

        if check_password_hash(user.password, request.form.get("password")):
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            response = redirect(url_for('dashboard'))
            set_access_cookies(response, access_token) # Set access token in cookie
            response.set_cookie('refresh_token_cookie', refresh_token, httponly=True, secure=True)
            return response

        else:
            flash('Incorrect Credentials. Please Try Again!')
            return redirect(url_for('login'))

    return render_template("login.html", login_form=login_form)

#route to refresh tokens
@app.route('/refresh', methods=['GET','POST'])
@jwt_required(refresh=True) #only allow refresh tokens to access this route. Creates new access token from refresh tokens
def refresh():
    if request.method == 'POST':
        current_user_now = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user_now)
        response = redirect(url_for('dashboard'))
        set_access_cookies(response, new_access_token)  # Set the new access token in a cookie
        return response

    return render_template("refresh.html")

@app.route("/dashboard", methods=['GET','POST'])
@jwt_required()
def dashboard():
    selected_category = request.form.get('category') # Get the selected parameters from the dropdown form
    selected_month = request.form.get('month')
    selected_year = request.form.get('year')

    user_id = current_user.id
    query = db.select(ExpenseEntry).where(ExpenseEntry.user_id == user_id).order_by(ExpenseEntry.expense_date.desc())

    # see dashboard_functions.py for handling query of expenses based on selected optional parameters
    all_expenses = filter_category_month_year(query, selected_category, selected_month, selected_year)

    total_expense = 0
    for expense in all_expenses:
        total_expense += expense.amount

    current_year = datetime.now().year
    months = [(str(i), datetime(current_year, i, 1).strftime('%B')) for i in range(1, 13)] # set up months for dropdown menu
    years = [str(year) for year in range(current_year, current_year - 6, -1)] # set up years for dropdown menu
    categories = [category for category in ExpenseCategory]  # get the category names from enum class from db_models.py

    try:
        #see dashboard_functions.py for data manipulation and graphing
        graph_json = month_and_category_graph(all_expenses)
        show_graph = True

        return render_template("dashboard.html", all_expenses=all_expenses,
                               months=months, years=years, total_expense=total_expense, graphJSON=graph_json,
                               show_graph=show_graph, ExpenseCategory=categories)

    #handle exception when no data is shown to plot the graph
    except KeyError:
        flash("There is no Data for the filter you selected!")
        show_graph = False
        return render_template("dashboard.html", all_expenses=all_expenses,
                               months=months, years=years, total_expense=total_expense,
                               show_graph=show_graph, ExpenseCategory=categories)

@app.route("/add_expense/", methods=['GET','POST'])
@jwt_required()
def add_expense():
    user_id = current_user.id
    add_expense_form = ExpenseForm()

    if add_expense_form.validate_on_submit():
        expense_date_str = request.form.get("expense_date")
        expense_date_formatted = datetime.strptime(expense_date_str, '%Y-%m-%d')

        new_expense = ExpenseEntry(
                description=request.form.get("description"),
                amount=request.form.get("amount"),
                category= request.form.get("category"),
                expense_date=expense_date_formatted,
                user_id=user_id
            )

        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template("expense_form.html", add_expense_form=add_expense_form)

@app.route("/edit_expense/<expense_id>", methods=['GET','POST'])
@jwt_required()
@entry_ownership_required
def edit_expense(expense_id):
    expense_to_edit = db.session.execute(db.select(ExpenseEntry).where(ExpenseEntry.id == expense_id)).scalar()

    form = ExpenseForm(
        expense_id = expense_to_edit.id,
        description=expense_to_edit.description,
        amount=expense_to_edit.amount,
        category=expense_to_edit.category,
        expense_date=expense_to_edit.expense_date
    )

    if form.validate_on_submit():
        expense_to_edit.description = form.description.data
        expense_to_edit.amount = form.amount.data
        expense_to_edit.category = form.category.data
        expense_to_edit.expense_date = form.expense_date.data

        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template("expense_form.html", edit_expense_form=form, id=expense_id)

@app.route("/delete_expense/<expense_id>", methods=['GET','POST'])
@jwt_required()
@entry_ownership_required
def delete_expense(expense_id):
    expense_to_delete = db.session.execute(db.select(ExpenseEntry).where(ExpenseEntry.id == expense_id)).scalar()

    if request.method == 'POST':
        db.session.delete(expense_to_delete)
        db.session.commit()
        return redirect(url_for('dashboard'))

    return render_template("delete.html", expense=expense_to_delete)

@app.route('/logout')
def logout():
    response = redirect(url_for('home'))
    unset_jwt_cookies(response) #unset all tokens in cookies to revoke them upon log out
    return response

if __name__ == "__main__":
    app.run(debug=False, port=5002)