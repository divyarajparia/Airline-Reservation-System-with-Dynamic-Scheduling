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
from datetime import datetime
from datetime import datetime, date, time, timedelta
from sqlalchemy.exc import SQLAlchemyError

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
    previous_bookings_query = text("""
        SELECT T.PNR, T.Schedule_id, T.seat_num, T.status,
        S.Flight_num, S.src_airport, S.dst_airport, S.dept_date, S.dept_time
        FROM Trip T
        JOIN Schedule S ON T.Schedule_id = S.Schedule_id
        WHERE T.booked_by = :user_id
        ORDER BY T.PNR
    """)
    previous_bookings = db.session.execute(previous_bookings_query, {'user_id': current_user.user_id}).fetchall()
    
    user_query = text("""
        SELECT first_name, last_name, email
        FROM User
        WHERE user_id = :user_id
    """)
    
    user_result = db.session.execute(user_query, {'user_id': current_user.user_id}).fetchone()

    first_name, last_name, email = user_result if user_result else ("N/A", "N/A", "N/A")

    user_info = {"first_name": first_name, "last_name": last_name, "email": email}

    # Group bookings by PNR and check cancellation eligibility
    bookings_by_pnr = {}
    current_date = datetime.now().date()
    for row in previous_bookings:
        pnr, schedule_id, seat_num, status, flight_num, src_airport, dst_airport, dept_date, dept_time = row
        dept_time = (datetime.min + dept_time).time()
        if pnr not in bookings_by_pnr:
            bookings_by_pnr[pnr] = []
        
        # Check if the flight is more than 24 hours away
        flight_datetime = datetime.combine(dept_date, dept_time)
        can_cancel = (flight_datetime - datetime.now()).total_seconds() > 86400 and status != 'canceled'
        
        bookings_by_pnr[pnr].append({
            "Schedule_id": schedule_id,
            "seat_num": seat_num,
            "Flight_num": flight_num,
            "src_airport": src_airport,
            "dst_airport": dst_airport,
            "dept_date": dept_date,
            "dept_time": dept_time,
            "can_cancel": can_cancel,
            "status": status
        })
    
    return render_template("previous_bookings.html", bookings_by_pnr=bookings_by_pnr, user_info=user_info)


@app.route('/cancel_booking/<pnr>', methods=['POST'])
@login_required
def cancel_booking(pnr):
    try:
        db.session.execute(text("CALL CancelBooking(:pnr, :user_id)"), 
                    {'pnr': pnr, 'user_id': current_user.user_id})
        db.session.commit()
        flash("Booking canceled successfully. Refund initiated.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Cancellation failed: {str(e)}", "danger")
    
    return redirect(url_for('previous_bookings'))


def dynamic_pricing(base_price, travel_date):
    current_date = datetime.now().date()
    travel_date = datetime.strptime(travel_date, "%Y-%m-%d").date()
    days_to_travel = (travel_date - current_date).days

    if days_to_travel >= 30:
        price =  base_price * 0.85
    elif days_to_travel >= 15:
        price = base_price * 0.9
    elif days_to_travel >= 7:
        price =  base_price * 1.0
    else:
        price = base_price * 1.2

    return price


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
            airport_query = text("""SELECT airport_name FROM Airports WHERE IATA_code = :IATA""")
            for route_id, schedules in flight_routes.items():
                route_info = []
                for sched_id in schedules:
                    res = db.session.execute(sched_query, {'sched_id': sched_id})
                    res = res.fetchall()[0]
                    schedule_id, flight_num, src_airport, dst_airport, dept_time, arrival_time, base_price = res
                    dept_time, arrival_time, base_price = str(dept_time), str(arrival_time), dynamic_pricing(float(base_price), travel_date)

                    res = db.session.execute(flight_query, {'f_id': flight_num})
                    aircraft_type, airline_name = res.fetchall()[0]

                    src_name = db.session.execute(airport_query, {'IATA': src_airport}).fetchall()[0][0]
                    dst_name = db.session.execute(airport_query, {'IATA': dst_airport}).fetchall()[0][0]

                    temp = [schedule_id, flight_num, aircraft_type, airline_name ,src_airport, dst_airport, dept_time, arrival_time, base_price, src_name, dst_name]
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

    return render_template('book_flight.html', selected_route = session['flight_route_info'][session["selected_route_id"]], num_passengers = session["num_passengers"])

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
            schedule_id = flight[0]  # sched_id
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
                if seat and seat not in selected_seats[schedule_id]:
                    selected_seats[schedule_id].append(seat)
                else:
                    flash(f"Error: Seat {seat} is already taken or invalid. Please choose another seat.", "error")
                    return redirect(url_for('select_seats'))
        
        session['selected_seats'] = selected_seats
        print("Selected seats:", selected_seats)
        return redirect(url_for('payments'))
    
    return render_template('select_seats.html', available_seats=available_seats, num_passengers=session["num_passengers"], passengers=session['passengers'], flight_info=flight_info)

@app.route('/payments', methods=['GET', 'POST'])
@login_required
def payments():
    selected_route_id = session['selected_route_id']
    flight_info = session['flight_route_info'][selected_route_id]
    seat_details=[]
    user_details=[]

    if request.method == 'GET':
        if 'selected_seats' not in session or 'selected_route_id' not in session:
            return redirect(url_for('dashboard'))
        
        selected_seats = session['selected_seats']
        flight_info = session['flight_route_info'][session['selected_route_id']]

        total_price = 0
        base_price = 0
        total_seat_price = 0
        total_base_price = 0

        for flight_leg in flight_info:
            base_price += float(flight_leg[8])
        total_base_price += base_price * session['num_passengers']


        print("Selected seats: ", selected_seats)

        print("flight info", flight_info)

        added_user = False
        global_counter = 0

        for schd_id, seats in selected_seats.items():
            counter = 0
            global_counter+=1
            for seat in seats:
                ssn = session['passengers'][counter]['ssn']
                name = session['passengers'][counter]['name']
                phone = session['passengers'][counter]['phone_number']
                mail = session['passengers'][counter]['email']

                seat_price = db.session.execute(
                    text("SELECT price FROM Seats WHERE seat_num = :seat AND Schedule_id = :schd_id"), 
                    {'seat': seat, 'schd_id': schd_id}
                ).fetchone()

                flight_number = db.session.execute(
                    text("SELECT Flight_num FROM Schedule WHERE Schedule_id = :schd_id"),
                    {'schd_id': schd_id}
                ).fetchone()

                counter += 1

                
                if seat_price:
                    total_seat_price += float(seat_price[0])
                    seat_details.append((schd_id,seat,seat_price[0],flight_number[0], name))
                    if global_counter == 1:
                        user_details.append((ssn,name,phone,mail))   

        platform_fee = 60
        total_price = total_base_price + total_seat_price + platform_fee

        session['seat_details'] = seat_details
        session['user_details'] = user_details

        session['base_price'] = base_price
        session['total_base_price'] = total_base_price
        session['total_seat_price'] = total_seat_price
        session['platform_fee'] = platform_fee
        session['total_price'] = total_price


        print("Seat details: ",select_seats)
        print('Number of passangers: ', session['num_passengers'])
        print("flight info: ", flight_info)
        print("base Price info: ", base_price)


        return render_template('payments.html', total_price=total_price,  base_price=base_price, total_base_price=total_base_price, total_seat_price=total_seat_price, platform_fee=platform_fee, num_passengers=session['num_passengers'], seat_details=seat_details, user_details=user_details,)
    else:
        selected_seats = session['selected_seats']
        total_price = session.get('total_price', 0)

        print(flight_info)
        print("selected seats: ",selected_seats)

        pnr = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

        for schd_id, seats in selected_seats.items():
            while True:
                pnr = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                with db.engine.connect() as conn:
                    conn.execute(
                        text("CALL CheckPNR(:schedule_id, :pnr, @is_present)"),
                        {'schedule_id': schd_id, 'pnr': pnr}
                    )
                    present = conn.execute(text("SELECT @is_present")).scalar()

                if present == 0:
                    break

        print("Passangers info : ",session['passengers'])
        
        try:
            with db.engine.begin() as conn:
                for schd_id, seats in selected_seats.items():
                    counter = 0
                    for seat in seats:
                        ssn = session['passengers'][counter]['ssn']
                        name = session['passengers'][counter]['name']
                        phone = session['passengers'][counter]['phone_number']
                        mail = session['passengers'][counter]['email']
                        # try:
                        conn.execute(text("""CALL ConfirmSeat(:user_id, :schedule_id, :seat_num, :ssn, :pnr, :name, :phone, :email, :no_of_passangers)"""), {
                            'user_id': current_user.user_id,
                            'schedule_id': schd_id,
                            'seat_num': seat,
                            'ssn': ssn,
                            'pnr': pnr,
                            'name': name,
                            'phone': phone,
                            'email': mail,
                            'no_of_passangers': 1
                        })
                        # except SQLAlchemyError as e:
                        #     print(f"Error: {str(e)}")  # Log error
                        #     conn.rollback()  # Rollback everything if any error occurs
                        #     raise Exception("Failed to confirm seats. All changes rolled back.")
                        # conn.commit()
                        counter+=1
                
                conn.execute(text("""CALL ConfirmPayment(:user_id, :total_price, :pnr)"""), {
                    'user_id': current_user.user_id,
                    'total_price': total_price,
                    'pnr': pnr
                })
                # conn.commit()
                
                flash("Payment successful. Your booking is confirmed.", "success")
                # seat_details = [(schd_id, seat, price, flight_num, name, pnr) for (schd_id, seat, price, flight_num, name) in seat_details]
                # user_details = [(ssn, name, phone, mail, pnr) for (ssn, name, phone, mail) in user_details]

                seat_details = session['seat_details']
                user_details = session['user_details']

                print("Seat Details", seat_details)
                print("User Details: " ,user_details)
                receipt_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))  # Generates a 10-character receipt number

                return render_template('receipt.html', total_price=session["total_price"],  base_price=session["base_price"], total_base_price=session["total_base_price"], total_seat_price=session["total_seat_price"], platform_fee=session["platform_fee"], seat_details=seat_details, user_details=user_details, pnr=pnr, receipt_number=receipt_number,  num_passengers=session['num_passengers'])

        except SQLAlchemyError as e:
            print(f"Database Error: {str(e)}")
            flash("Payment failed. Please try again later.", "error")
            return redirect(url_for('dashboard'))

        except Exception as e:
            # db.session.rollback()
            print("Failed:", str(e))
            flash(f"Payment failed: {str(e)}", "danger")
            return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
