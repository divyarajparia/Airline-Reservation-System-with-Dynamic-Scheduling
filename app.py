from flask import Flask, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy 
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
import os
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

import pymysql
pymysql.install_as_MySQLdb()

load_dotenv()

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://sql12764206:HPNY485L73@sql12.freesqldatabase.com/sql12764206'
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

@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():
    return render_template('dashboard.html')

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
