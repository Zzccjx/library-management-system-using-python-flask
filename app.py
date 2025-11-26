from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from config import Config
from models import db, User, Book, IssuedBook, Notification, Category
from routes import main
import os
from datetime import datetime, timedelta, timezone

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    app.register_blueprint(main)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        create_sample_data()
    
    # Background task to check for due books and create notifications
    @app.before_request
    def check_due_books():
        if current_user.is_authenticated:
            # Check for books due tomorrow
            tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
            due_tomorrow = IssuedBook.query.filter(
                IssuedBook.user_id == current_user.id,
                IssuedBook.return_date.is_(None),
                db.func.date(IssuedBook.due_date) == tomorrow.date()
            ).all()
            
            for issued_book in due_tomorrow:
                # Check if notification already exists
                existing_notification = Notification.query.filter_by(
                    user_id=current_user.id,
                    message=f"Book '{issued_book.book.title}' is due tomorrow!"
                ).first()
                
                if not existing_notification:
                    Notification.create_notification(
                        current_user.id,
                        f"Book '{issued_book.book.title}' is due tomorrow!",
                        'warning'
                    )
            
            # Check for overdue books
            overdue_books = IssuedBook.query.filter(
                IssuedBook.user_id == current_user.id,
                IssuedBook.return_date.is_(None),
                IssuedBook.due_date < datetime.now(timezone.utc)
            ).all()
            
            for issued_book in overdue_books:
                days_overdue = (datetime.now(timezone.utc) - issued_book.due_date).days
                # Check if notification already exists for today
                today = datetime.now(timezone.utc).date()
                existing_notification = Notification.query.filter(
                    Notification.user_id == current_user.id,
                    Notification.message.like(f"%{issued_book.book.title}% is overdue%"),
                    db.func.date(Notification.created_at) == today
                ).first()
                
                if not existing_notification:
                    fine = days_overdue * app.config['FINE_PER_DAY']
                    Notification.create_notification(
                        current_user.id,
                        f"Book '{issued_book.book.title}' is overdue by {days_overdue} days. Fine: ₹{fine}",
                        'danger'
                    )
    
    return app

def create_sample_data():
    """Create sample data if database is empty"""
    if User.query.count() == 0:
        # Create admin user
        admin = User(
            name='Admin User',
            email='admin@library.com',
            mobile='9876543210',
            role='admin',
            membership_type='lifetime'
        )
        admin.set_password('admin123')
        
        # Create student user
        student = User(
            name='John Doe',
            email='student@library.com',
            mobile='9123456789',
            role='student',
            membership_type='basic'
        )
        student.set_password('student123')
        
        db.session.add(admin)
        db.session.add(student)
        
        # Create sample books
        books = [
            Book(title='The Great Gatsby', author='F. Scott Fitzgerald', category='Fiction', total_copies=3, available_copies=3),
            Book(title='To Kill a Mockingbird', author='Harper Lee', category='Fiction', total_copies=2, available_copies=2),
            Book(title='1984', author='George Orwell', category='Science Fiction', total_copies=4, available_copies=4),
            Book(title='Pride and Prejudice', author='Jane Austen', category='Romance', total_copies=2, available_copies=2),
            Book(title='The Catcher in the Rye', author='J.D. Salinger', category='Fiction', total_copies=3, available_copies=3),
            Book(title='Lord of the Flies', author='William Golding', category='Fiction', total_copies=2, available_copies=2),
            Book(title='Animal Farm', author='George Orwell', category='Political Fiction', total_copies=3, available_copies=3),
            Book(title='Brave New World', author='Aldous Huxley', category='Science Fiction', total_copies=2, available_copies=2),
        ]
        
        for book in books:
            db.session.add(book)
        
        # Create default categories
        categories = [
            Category(name='Fiction'),
            Category(name='Science Fiction'),
            Category(name='Romance'),
            Category(name='Political Fiction'),
            Category(name='Mystery'),
            Category(name='Biography'),
            Category(name='History'),
            Category(name='Science'),
            Category(name='Technology'),
            Category(name='Philosophy')
        ]
        
        for category in categories:
            db.session.add(category)
        
        db.session.commit()
        print("Sample data created successfully!")

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
