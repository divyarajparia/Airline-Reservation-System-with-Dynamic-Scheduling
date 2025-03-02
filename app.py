from flask import Flask, render_template, url_for, redirect, request, session
from flask_sqlalchemy import SQLAlchemy 
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
import os
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from sqlalchemy import text

import pymysql
pymysql.install_as_MySQLdb()

load_dotenv()

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql://{os.getenv('db_user_name')}:{os.getenv('db_pwd')}@{os.getenv('db_host')}/{os.getenv('db_name')}"
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db = SQLAlchemy(app)

bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True) # ID column of the user
    username = db.Column(db.String(20), nullable=False, unique=True) # Cannot be null and max length of 20 characters
    password = db.Column(db.String(80), nullable=False) # 80 characters after hashing

class RegistrationFrom(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4,max=20)], render_kw={"placeholder": "Username"})
    
    password = PasswordField(validators=[InputRequired(), Length(
        min=4,max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField("Register")

    def validate_username(self,username):
        exsiting_user_username = User.query.filter_by(
            username=username.data).first()
        
        if exsiting_user_username:
            raise ValidationError(
                "This Username already exists. Please choose a different one."
            )
        
class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4,max=20)], render_kw={"placeholder": "Username"})
    
    password = PasswordField(validators=[InputRequired(), Length(
        min=4,max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField("Login ")


@app.route('/')
def home():
    return render_template('home.html')

# @app.route('/dashboard', methods=['GET', 'POST'])
# @login_required
# def dashboard():
#     flights = None
#     selected_flight = None

#     if request.method == 'POST':
#         if 'search_flights' in request.form:  # Triggered on Flight Search
#             source_city = request.form.get('source_city')
#             destination_city = request.form.get('destination_city')
#             travel_date = request.form.get('travel_date')
#             num_passengers = int(request.form.get('num_passengers'))
#             max_layovers = int(request.form.get('max_layovers'))


#             # Fetch IATA Codes
#             source_query = text("SELECT IATA_code FROM Airports WHERE city_name = :city")
#             src_airport = db.session.execute(source_query, {'city': source_city}).fetchone()
#             dst_airport = db.session.execute(source_query, {'city': destination_city}).fetchone()
#             src_IATA = src_airport[0]
#             dst_IATA = dst_airport[0]
#             print(src_IATA, dst_IATA)

#             if src_airport and dst_airport:
#                 src_IATA, dst_IATA = src_airport[0], dst_airport[0]

#                 # Store Search Parameters
#                 session.update({
#                     'src_IATA': src_IATA,
#                     'dst_IATA': dst_IATA,
#                     'travel_date': travel_date,
#                     'num_passengers': num_passengers,
#                     'max_layovers': max_layovers
#                 })

#                 # Fetch Flights
#                 flights_query = text("""
#                     SELECT flight_num, src_airport, dst_airport, dept_time, arrival_time
#                     FROM Schedule
#                     WHERE src_airport = :src AND dst_airport = :dst AND departure_date = :date
#                 """)
#                 flights = db.session.execute(flights_query, {
#                     'src': src_IATA,
#                     'dst': dst_IATA,
#                     'date': travel_date
#                 }).fetchall()
#                 print(flights)

#         elif 'select_flight' in request.form:  # Triggered on Flight Selection
#             selected_flight = request.form.get('select_flight')
#             session['selected_flight'] = selected_flight
#             print(f"Selected Flight: {selected_flight}")

#     # Get Cities for Dropdowns
#     city_query = text("SELECT DISTINCT city_name FROM Airports")
#     cities = [row[0] for row in db.session.execute(city_query).fetchall()]

#     return render_template('dashboard.html', cities=cities, flights=flights, selected_flight=selected_flight)


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
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('dashboard'))

    return render_template('login.html', form=form)

@app.route('/logout',methods=['GET','POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    form = RegistrationFrom() 

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/previous_bookings')
@login_required
def previous_bookings():
    # Logic to fetch and display previous bookings goes here
    return render_template('previous_bookings.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
