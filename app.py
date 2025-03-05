from flask import Flask, render_template, url_for, redirect, request, session
from flask_sqlalchemy import SQLAlchemy 
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
import os
from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError, Email, DataRequired
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from sqlalchemy import text
from flask import flash

import pymysql
pymysql.install_as_MySQLdb()


load_dotenv()

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"{os.getenv('connection_uri')}"
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db = SQLAlchemy(app)

bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Ensure to logout all users before closing the session
@app.before_request
def before_request():
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'User'
    user_id = db.Column(db.Integer, primary_key=True)  # Matches `user_id` in your DB
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    password = db.Column(db.String(1024), nullable=False)  # Bcrypt hashes can be long

    def get_id(self):
        return str(self.user_id)

class RegistrationForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name")
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone_number = StringField("Phone Number")
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])

    submit = SubmitField("Register")

    def validate_email(self,field):
        existing_user = User.query.filter_by(
            email=field.data).first()
        
        if existing_user:
            raise ValidationError(
                "This Username already exists. Please choose a different one."
            )
        
class LoginForm(FlaskForm):
    email = StringField(validators=[InputRequired(),Email()], render_kw={"placeholder": "Email"})
    
    password = PasswordField(validators=[InputRequired(), Length(
        min=4,max=20)], render_kw={"placeholder": "Password"})
    
    remember = BooleanField("Remember me")

    submit = SubmitField("Login")


@app.route('/', methods=['GET', 'POST'])
def home():
    # Whenever a user enters, always redirect to login page
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():
    flights = None
    if request.method == 'POST':
        source_city = request.form.get('source_city')
        destination_city = request.form.get('destination_city')
        travel_date = request.form.get('travel_date')
        num_passengers = int(request.form.get('num_passengers'))
        max_layovers = int(request.form.get('max_layovers'))

        source_query = text("SELECT IATA_code, airport_name FROM Airports WHERE city_name = :city")
        src_airport = db.session.execute(source_query, {'city': source_city}).fetchone()
        dst_airport = db.session.execute(source_query, {'city': destination_city}).fetchone()
        src_IATA = src_airport[0]
        dst_IATA = dst_airport[0]
        print(src_IATA, dst_IATA)

        session.update({
            'src_IATA': src_IATA,
            'dst_IATA': dst_IATA,
            'travel_date': travel_date,
            'num_passengers': num_passengers,
            'max_layovers': max_layovers
        })

        print(session['src_IATA'], session['dst_IATA'], session['travel_date'], session['num_passengers'], session['max_layovers'])

        flight_query = text("""
            SELECT flight_num, src_airport, dst_airport, dept_time, arrival_time, base_price
            FROM Schedule
            WHERE src_airport = :src_IATA
            AND dst_airport = :dst_IATA
            AND dept_date = :travel_date
        """)
        flights = db.session.execute(flight_query, {'src_IATA': src_IATA, 'dst_IATA': dst_IATA, 'travel_date': travel_date}).fetchall()
        print(flights)



    city_query = text("SELECT DISTINCT city_name FROM Airports")
    results = db.session.execute(city_query).fetchall()
    cities = [row[0] for row in results]

    return render_template('dashboard.html', cities=cities, flights = flights)



@app.route('/login', methods=['GET','POST'])
def login():
    print("Request method:", request.method) 
    if request.method == "POST":
        print("POST request received")

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if user and bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                flash('Login unsuccessful. Please check email and password', 'error')

    return render_template('login.html', form=form)

@app.route('/logout',methods=['GET','POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    form = RegistrationForm() 

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(email=form.email.data, password=hashed_password, first_name=form.first_name.data,last_name=form.last_name.data,phone_number=form.phone_number.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    else:
        print(form.errors)

    return render_template('register.html', form=form)

@app.route('/previous_bookings')
@login_required
def previous_bookings():
    return render_template('previous_bookings.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
