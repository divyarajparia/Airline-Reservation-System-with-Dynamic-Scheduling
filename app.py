import string
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
import random

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

class TravelerInfo(db.Model):
    __tablename__ = 'Traveler_info'
    social_security_num = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)

@app.route('/', methods=['GET', 'POST'])
def home():
    # Whenever a user enters, always redirect to login page
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():

    flight_route_info = None
    if request.method == 'POST':
        if "search_flights" in request.form:
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

            flight_query = text("""CALL FindFlights(:travel_date, :src_IATA, :dst_IATA, :num_passengers, :max_layovers)""")
            print(flight_query)
            res = db.session.execute(flight_query, {'travel_date': session["travel_date"], 'src_IATA': session["src_IATA"], 'dst_IATA': session["dst_IATA"], 'num_passengers': session["num_passengers"], 'max_layovers': session["max_layovers"]})
            res = res.fetchall()
            print(res)
            flight_routes = {}
            for route_id, route in res:
                schedule_ids = [int(t) for t in route.strip().split()]
                flight_routes[route_id] = schedule_ids
            print(flight_routes)

            flight_route_info = {}
            sched_query = text("""SELECT Schedule_id, Flight_num, src_airport, dst_airport, dept_time, arrival_time, base_price FROM Schedule WHERE Schedule_id = :sched_id""")
            flight_query = text("""SELECT aircraft_type, airline_name FROM Flight_data WHERE Flight_num = :f_id""")
            for route_id, schedules in flight_routes.items():
                route_info = []
                for sched_id in schedules:
                    res = db.session.execute(sched_query, {'sched_id': sched_id})
                    res = res.fetchall()[0]
                    schedule_id, flight_num, src_airport, dst_airport, dept_time, arrival_time, base_price = res
                    dept_time, arrival_time, base_price = str(dept_time), str(arrival_time), float(base_price)
                    res = db.session.execute(flight_query, {'f_id': flight_num})
                    aircraft_type, airline_name = res.fetchall()[0]
                    temp = [schedule_id, flight_num, aircraft_type, airline_name ,src_airport, dst_airport, dept_time, arrival_time, base_price]
                    route_info.append(temp)

                route_id = int(route_id)    
                flight_route_info[route_id] = route_info

            session['flight_route_info'] = flight_route_info
            print(flight_route_info)
        

    city_query = text("SELECT DISTINCT city_name FROM Airports")
    results = db.session.execute(city_query).fetchall()
    cities = [row[0] for row in results]
    return render_template('dashboard.html', cities=cities, flights = flight_route_info )

@app.route('/book_flight', methods=['GET','POST'])
@login_required
def book_flight():

    if request.method == 'POST':

        if 'selected_flight' in request.form:
            selected_route_id = str(request.form.get('selected_flight'))
            print(session["flight_route_info"])
            print("selected_route_id:", selected_route_id)
            print(session['flight_route_info'][selected_route_id])
            session['selected_route_id'] = selected_route_id
            selected_route_id = session['selected_route_id']    

        elif 'passenger_info' in request.form:
            passengers = []
            for i in range(session.get("num_passengers", 1)):
                pax = {
                    'name': request.form.get(f'name_{i}'),
                    'phone_number': request.form.get(f'phone_number_{i}'),
                    'email': request.form.get(f'email_{i}'),
                    'ssn': request.form.get(f'ssn_{i}')
                }
                passengers.append(pax)
            session['passengers'] = passengers  
            print("Passengers stored in session:", passengers)
            flash("Passenger information saved!", "success")
            return redirect(url_for('select_seats'))



    # have to work on this
    # if request.method == 'POST':
    #     passengers = []
    #     for i in range(session["num_passengers"]):
    #         pax = {
    #             'name': request.form.get(f'name_{i}'),
    #             'phone_number': request.form.get(f'phone_number_{i}'),
    #             'email': request.form.get(f'email_{i}'),
    #             'ssn': request.form.get(f'ssn_{i}')
    #         }
    #         passengers.append(pax)
    #     # print(passengers)


    return render_template('book_flight.html', selected_route = session['flight_route_info'][session["selected_route_id"]], num_passengers = session["num_passengers"])

# @app.route('/select_seats', methods=['GET', 'POST'])
# @login_required
# def select_seats():
#     if request.method == 'GET':
#         # Ensure that selected_route_id exists
#         if 'selected_route_id' not in session:
#             return redirect(url_for('dashboard'))
        
#         selected_route_id = session['selected_route_id']
#         flight_info = session['flight_route_info'][selected_route_id]
        
#         # Fetch Schedule_id for the selected flight
#         sched_query = text("SELECT Schedule_id FROM Schedule WHERE Flight_num = :f_id")
#         sched_id = db.session.execute(sched_query, {'f_id': flight_info[0][1]}).fetchone()[0]
        
#         # Store Schedule_id in session (to avoid querying again later)
#         session['schedule_id'] = sched_id

#         # Fetch available seats for the selected flight
#         seat_query = text("SELECT seat_num, price, seat_type FROM Seats WHERE Schedule_id = :sched_id AND status = 'available'")
#         available_seats = db.session.execute(seat_query, {'sched_id': sched_id}).fetchall()
        
#         passengers = session.get("passengers", [])  # Use the correct key

#         return render_template('select_seats.html', available_seats=available_seats, num_passengers=session["num_passengers"], passengers = passengers)
    
#     # Handle POST request for seat selection (Store in session, NOT database)
#     if request.method == 'POST':
#         selected_seats = []
#         for i in range(session["num_passengers"]):
#             seat = request.form.get(f"seat_{i}")  # Fetch seat for each passenger
#             if seat:
#                 selected_seats.append(seat)

#         session['selected_seats'] = selected_seats  # Store in session

#         print("Selected seats:", selected_seats)  # Debugging output

#         return redirect(url_for('select_seats'))  # Redirect to payment (or confirmation)
    
#     return render_template('select_seats.html')

# @app.route('/select_seats', methods=['GET', 'POST'])
# @login_required
# def select_seats():
#     if request.method == 'GET':
#         if 'selected_route_id' not in session:
#             return redirect(url_for('dashboard'))
        
#         selected_route_id = session['selected_route_id']
#         flight_info = session['flight_route_info'][selected_route_id]
        
#         available_seats = {}
        
#         for flight in flight_info:
#             sched_id = db.session.execute(text("SELECT Schedule_id FROM Schedule WHERE Flight_num = :f_id"), {'f_id': flight[1]}).fetchone()[0]
#             seat_query = text("SELECT seat_num, price, seat_type FROM Seats WHERE Schedule_id = :sched_id AND status = 'available'")
#             available_seats[flight[1]] = db.session.execute(seat_query, {'sched_id': sched_id}).fetchall()
        
#         return render_template('select_seats.html', available_seats=available_seats, num_passengers=session["num_passengers"], flight_info=flight_info, passengers=session['passengers'])
    
#     if request.method == 'POST':
#         selected_seats = {}
        
#         for flight in session['flight_route_info'][session['selected_route_id']]:
#             flight_num = flight[1]
#             selected_seats[flight_num] = []
            
#             for i in range(session["num_passengers"]):
#                 seat = request.form.get(f"seat_{flight_num}_{i}")
#                 if seat:
#                     selected_seats[flight_num].append(seat)
        
#         session['selected_seats'] = selected_seats
        
#         print("Selected seats:", selected_seats)
        
#         return redirect(url_for('payments'))  # Implement payment route later
        
#     return render_template('select_seats.html', available_seats=available_seats, num_passengers=session["num_passengers"], passengers=session['passengers'], flight_info=flight_info)

@app.route('/select_seats', methods=['GET', 'POST'])
@login_required
def select_seats():
    if request.method == 'GET':
        if 'selected_route_id' not in session:
            return redirect(url_for('dashboard'))
        
        selected_route_id = session['selected_route_id']
        flight_info = session['flight_route_info'][selected_route_id]
        
        available_seats = {}
        for flight in flight_info:
            schedule_id = flight[0]  # Assuming schedule_id is the first element in flight info
            seat_query = text("SELECT seat_num, price, seat_type FROM Seats WHERE Schedule_id = :sched_id AND status = 'available'")
            available_seats[schedule_id] = db.session.execute(seat_query, {'sched_id': schedule_id}).fetchall()
        
        return render_template('select_seats.html', available_seats=available_seats, num_passengers=session["num_passengers"], flight_info=flight_info, passengers=session['passengers'])
    
    if request.method == 'POST':
        selected_seats = {}
        for flight in session['flight_route_info'][session['selected_route_id']]:
            schedule_id = flight[0]
            selected_seats[schedule_id] = []
            for i in range(session["num_passengers"]):
                seat = request.form.get(f"seat_{schedule_id}_{i}")
                if seat:
                    selected_seats[schedule_id].append(seat)
        
        session['selected_seats'] = selected_seats
        print("Selected seats:", selected_seats)
        return redirect(url_for('payments'))
    
    return render_template('select_seats.html', available_seats=available_seats, num_passengers=session["num_passengers"], passengers=session['passengers'], flight_info=flight_info)


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


    # return render_template('book_flight.html')

@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    selected_route_id = session['selected_route_id']
    flight_info = session['flight_route_info'][selected_route_id]

    if request.method == 'GET':
        if 'selected_seats' not in session or 'selected_route_id' not in session:
            return redirect(url_for('dashboard'))
        
        selected_seats = session['selected_seats']
        total_price=0
        seat_details=[]

        print("Selected seats: ", selected_seats)

        # selected_route_id = session['selected_route_id']
        # flight_info = session['flight_route_info'][selected_route_id]

        print("flight info", flight_info)

        for schd_id, seats in selected_seats.items():
            counter = 0
            for seat in seats:
                seat_price = db.session.execute(
                    text("SELECT price FROM Seats WHERE seat_num = :seat AND Schedule_id = :schd_id"), 
                    {'seat': seat, 'schd_id': schd_id}
                ).fetchone()

                counter += 1

                if seat_price:
                    total_price += seat_price[0]
                    seat_details.append((schd_id,seat,seat_price[0]))
            
        session['total_price'] = total_price

        return render_template('payments.html', total_price=total_price, seat_details=seat_details)
    else:
        # Create stored procedure

        selected_seats = session['selected_seats']
        total_price = session.get('total_price', 0)

        print(flight_info)
        print("selected seats: ",selected_seats)

        # print("HI", session['flight_route_info'[selected_route_id]])

        pnr = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        
        try:
            with db.engine.connect() as conn:
                for schd_id, seats in selected_seats.items():
                    counter = 0
                    for seat in seats:
                        ssn = session['passengers'][counter]['ssn']
                        conn.execute(text("""CALL ConfirmSeat(:user_id, :schedule_id, :seat_num, :ssn, :pnr)"""), {
                            'user_id': current_user.user_id,
                            'schedule_id': schd_id,
                            'seat_num': seat,
                            'ssn': ssn,
                            'pnr': pnr
                        })
                        conn.commit()
                    counter+=1
                
                conn.execute(text("""CALL ConfirmPayment(:user_id, :total_price, :pnr)"""), {
                    'user_id': current_user.user_id,
                    'total_price': total_price,
                    'pnr': pnr
                })
                conn.commit()
                
                flash("Payment successful. Your booking is confirmed.", "success")
                return render_template('receipt.html')

        except Exception as e:
            db.session.rollback()
            print("Failed:", str(e))
            flash(f"Payment failed: {str(e)}", "danger")
            return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
