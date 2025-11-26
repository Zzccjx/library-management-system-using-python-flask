from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(15), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # admin or student
    membership_type = db.Column(db.String(20), default='basic')  # basic, 3month, 6month, lifetime
    membership_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    issued_books = db.relationship('IssuedBook', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def get_unread_notifications_count(self):
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()
    
    def is_membership_active(self):
        if self.membership_type == 'lifetime':
            return True
        if self.membership_expiry:
            # Ensure membership_expiry is timezone-aware
            if self.membership_expiry.tzinfo is None:
                membership_expiry_utc = self.membership_expiry.replace(tzinfo=timezone.utc)
            else:
                membership_expiry_utc = self.membership_expiry
            return datetime.now(timezone.utc) < membership_expiry_utc
        return self.membership_type == 'basic'

class Book(db.Model):
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    available_copies = db.Column(db.Integer, nullable=False, default=1)
    cover_photo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    issued_books = db.relationship('IssuedBook', backref='book', lazy=True)
    
    def is_available(self):
        return self.available_copies > 0
    
    def get_issued_count(self):
        return self.total_copies - self.available_copies

class IssuedBook(db.Model):
    __tablename__ = 'issued_books'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime, nullable=True)
    fine = db.Column(db.Float, default=0.0)
    
    def __init__(self, **kwargs):
        super(IssuedBook, self).__init__(**kwargs)
        if not self.due_date:
            self.due_date = datetime.now(timezone.utc) + timedelta(days=10)  # 10 days loan period
    
    def is_overdue(self):
        if self.return_date:
            return False
        # Ensure due_date is timezone-aware for comparison
        if self.due_date.tzinfo is None:
            due_date_utc = self.due_date.replace(tzinfo=timezone.utc)
        else:
            due_date_utc = self.due_date
        return datetime.now(timezone.utc) > due_date_utc
    
    def days_overdue(self):
        if not self.is_overdue():
            return 0
        # Ensure due_date is timezone-aware for calculation
        if self.due_date.tzinfo is None:
            due_date_utc = self.due_date.replace(tzinfo=timezone.utc)
        else:
            due_date_utc = self.due_date
        return (datetime.now(timezone.utc) - due_date_utc).days
    
    def calculate_fine(self, fine_per_day=10):
        if self.is_overdue():
            self.fine = self.days_overdue() * fine_per_day
        return self.fine
    
    def is_due_tomorrow(self):
        if self.return_date:
            return False
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        # Ensure due_date is timezone-aware for comparison
        if self.due_date.tzinfo is None:
            due_date_utc = self.due_date.replace(tzinfo=timezone.utc)
        else:
            due_date_utc = self.due_date
        return due_date_utc.date() == tomorrow.date()

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(20), default='info')  # info, warning, danger
    
    @staticmethod
    def create_notification(user_id, message, notification_type='info'):
        notification = Notification(
            user_id=user_id,
            message=message,
            notification_type=notification_type
        )
        db.session.add(notification)
        db.session.commit()
        return notification

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Category {self.name}>'
