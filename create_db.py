from app import app, db
import os
from sqlalchemy import inspect

with app.app_context():
    db.create_all()  # Create tables in the MySQL database
    print("Database tables created successfully.")
    print(f"Database location: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Current working directory: {os.getcwd()}")

    # Get table names using inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables in the database: {tables}")

    # Try to create a user
    from app import User
    new_user = User(username="test_user", password="test_password")
    db.session.add(new_user)
    db.session.commit()

    print(f"Users in the database: {User.query.all()}")