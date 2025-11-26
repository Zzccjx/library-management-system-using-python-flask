from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Book, IssuedBook, Notification, Category
from datetime import datetime, timedelta, timezone
import os
import xlsxwriter
from io import BytesIO

main = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@main.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('main.admin_dashboard'))
        else:
            return redirect(url_for('main.student_dashboard'))
    return render_template('index.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.is_admin():
                return redirect(url_for('main.admin_dashboard'))
            else:
                return redirect(url_for('main.student_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form.get('mobile', '')
        password = request.form['password']
        role = request.form.get('role', 'student')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        user = User(name=name, email=email, mobile=mobile, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('register.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    # Get statistics
    total_books = Book.query.count()
    total_visitors = User.query.filter_by(role='student').count()
    issued_books = IssuedBook.query.filter(IssuedBook.return_date.is_(None)).count()
    available_books = db.session.query(db.func.sum(Book.available_copies)).scalar() or 0
    
    # Recent activities
    recent_issues = IssuedBook.query.order_by(IssuedBook.issue_date.desc()).limit(5).all()
    overdue_books = IssuedBook.query.filter(
        IssuedBook.return_date.is_(None),
        IssuedBook.due_date < datetime.now(timezone.utc)
    ).all()
    
    return render_template('admin_dashboard.html', 
                         total_books=total_books,
                         total_visitors=total_visitors,
                         issued_books=issued_books,
                         available_books=available_books,
                         recent_issues=recent_issues,
                         overdue_books=overdue_books)

@main.route('/student/dashboard')
@login_required
def student_dashboard():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = Book.query
    
    if search:
        query = query.filter(
            (Book.title.contains(search)) |
            (Book.author.contains(search))
        )
    
    if category:
        query = query.filter_by(category=category)
    
    books = query.all()
    categories = db.session.query(Book.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template('student_dashboard.html', books=books, categories=categories, search=search, selected_category=category)

@main.route('/books')
@login_required
def books():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    books = Book.query.all()
    return render_template('books.html', books=books)

@main.route('/books/add', methods=['GET', 'POST'])
@login_required
def add_book():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        category = request.form['category']
        total_copies = int(request.form['total_copies'])
        
        # Handle file upload
        cover_photo = None
        if 'cover_photo' in request.files:
            file = request.files['cover_photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                cover_photo = filename
        
        book = Book(
            title=title,
            author=author,
            category=category,
            total_copies=total_copies,
            available_copies=total_copies,
            cover_photo=cover_photo
        )
        
        db.session.add(book)
        db.session.commit()
        
        flash('Book added successfully!', 'success')
        return redirect(url_for('main.books'))
    
    categories = Category.query.order_by(Category.name).all()
    return render_template('add_book.html', categories=categories)

@main.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        book.title = request.form['title']
        book.author = request.form['author']
        book.category = request.form['category']
        old_total = book.total_copies
        new_total = int(request.form['total_copies'])
        
        # Update available copies proportionally
        if new_total != old_total:
            issued_count = old_total - book.available_copies
            book.total_copies = new_total
            book.available_copies = max(0, new_total - issued_count)
        
        # Handle file upload
        if 'cover_photo' in request.files:
            file = request.files['cover_photo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Delete old file if exists
                if book.cover_photo:
                    old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], book.cover_photo)
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                
                filename = secure_filename(file.filename)
                filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                book.cover_photo = filename
        
        db.session.commit()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('main.books'))
    
    return render_template('edit_book.html', book=book)

@main.route('/books/delete/<int:book_id>')
@login_required
def delete_book(book_id):
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    book = Book.query.get_or_404(book_id)
    
    # Check if book is currently issued
    if book.available_copies < book.total_copies:
        flash('Cannot delete book. It is currently issued to students.', 'danger')
        return redirect(url_for('main.books'))
    
    # Delete cover photo if exists
    if book.cover_photo:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], book.cover_photo)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(book)
    db.session.commit()
    
    flash('Book deleted successfully!', 'success')
    return redirect(url_for('main.books'))

@main.route('/issue-book', methods=['GET', 'POST'])
@login_required
def issue_book():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    if request.method == 'POST':
        student_id = request.form['student_id']
        book_id = request.form['book_id']
        
        student = User.query.get(student_id)
        book = Book.query.get(book_id)
        
        if not student or not book:
            flash('Invalid student or book selected.', 'danger')
            return redirect(url_for('main.issue_book'))
        
        if not book.is_available():
            flash('Book is not available for issue.', 'danger')
            return redirect(url_for('main.issue_book'))
        
        # Check if student already has this book
        existing_issue = IssuedBook.query.filter_by(
            user_id=student_id,
            book_id=book_id,
            return_date=None
        ).first()
        
        if existing_issue:
            flash('Student already has this book issued.', 'danger')
            return redirect(url_for('main.issue_book'))
        
        # Issue the book
        issued_book = IssuedBook(user_id=student_id, book_id=book_id)
        book.available_copies -= 1
        
        db.session.add(issued_book)
        db.session.commit()
        
        # Create notification for student
        Notification.create_notification(
            student_id,
            f"Book '{book.title}' has been issued to you. Due date: {issued_book.due_date.strftime('%Y-%m-%d')}",
            'info'
        )
        
        flash('Book issued successfully!', 'success')
        return redirect(url_for('main.issue_book'))
    
    visitors = User.query.filter_by(role='student').all()
    books = Book.query.filter(Book.available_copies > 0).all()
    
    return render_template('issue_book.html', students=visitors, books=books)

@main.route('/return-book', methods=['GET', 'POST'])
@login_required
def return_book():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    if request.method == 'POST':
        issued_book_id = request.form['issued_book_id']
        issued_book = IssuedBook.query.get(issued_book_id)
        
        if not issued_book or issued_book.return_date:
            flash('Invalid book return request.', 'danger')
            return redirect(url_for('main.return_book'))
        
        # Calculate fine if overdue
        if issued_book.is_overdue():
            issued_book.calculate_fine(current_app.config['FINE_PER_DAY'])
        
        # Return the book
        issued_book.return_date = datetime.now(timezone.utc)
        issued_book.book.available_copies += 1
        
        db.session.commit()
        
        # Create notification for student
        message = f"Book '{issued_book.book.title}' has been returned."
        if issued_book.fine > 0:
            message += f" Fine: ₹{issued_book.fine}"
        
        Notification.create_notification(
            issued_book.user_id,
            message,
            'info'
        )
        
        flash('Book returned successfully!', 'success')
        return redirect(url_for('main.return_book'))
    
    issued_books = IssuedBook.query.filter(IssuedBook.return_date.is_(None)).all()
    return render_template('return_book.html', issued_books=issued_books)

@main.route('/my-books')
@login_required
def my_books():
    if current_user.is_admin():
        flash('This page is for students only.', 'info')
        return redirect(url_for('main.admin_dashboard'))
    
    issued_books = IssuedBook.query.filter_by(user_id=current_user.id).order_by(IssuedBook.issue_date.desc()).all()
    return render_template('my_books.html', issued_books=issued_books)

@main.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    
    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    
    return render_template('notifications.html', notifications=notifications)

@main.route('/api/notifications/count')
@login_required
def notification_count():
    count = current_user.get_unread_notifications_count()
    return jsonify({'count': count})

# Category Management Routes
@main.route('/categories')
@login_required
def categories():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    categories = Category.query.order_by(Category.name).all()
    
    def books_in_category(category_name):
        return Book.query.filter_by(category=category_name).count()
    
    return render_template('categories.html', categories=categories, books_in_category=books_in_category)

@main.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    category_name = request.form['name'].strip()
    
    if not category_name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('main.categories'))
    
    # Check if category already exists
    existing_category = Category.query.filter_by(name=category_name).first()
    if existing_category:
        flash('Category already exists.', 'danger')
        return redirect(url_for('main.categories'))
    
    category = Category(name=category_name)
    db.session.add(category)
    db.session.commit()
    
    flash('Category added successfully!', 'success')
    return redirect(url_for('main.categories'))

@main.route('/categories/delete/<int:category_id>')
@login_required
def delete_category(category_id):
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    category = Category.query.get_or_404(category_id)
    
    # Check if any books use this category
    books_with_category = Book.query.filter_by(category=category.name).count()
    if books_with_category > 0:
        flash(f'Cannot delete category. {books_with_category} books are using this category.', 'danger')
        return redirect(url_for('main.categories'))
    
    db.session.delete(category)
    db.session.commit()
    
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('main.categories'))

# Membership Management Routes
@main.route('/memberships')
@login_required
def memberships():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    visitors = User.query.filter_by(role='student').order_by(User.name).all()
    return render_template('memberships.html', visitors=visitors)

@main.route('/memberships/update/<int:user_id>', methods=['POST'])
@login_required
def update_membership(user_id):
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    user = User.query.get_or_404(user_id)
    membership_type = request.form['membership_type']
    
    # Calculate expiry date based on membership type
    if membership_type == '3month':
        user.membership_expiry = datetime.now(timezone.utc) + timedelta(days=90)
    elif membership_type == '6month':
        user.membership_expiry = datetime.now(timezone.utc) + timedelta(days=180)
    elif membership_type == 'lifetime':
        user.membership_expiry = None
    else:  # basic
        user.membership_expiry = None
    
    user.membership_type = membership_type
    db.session.commit()
    
    # Create notification for user
    membership_names = {
        'basic': 'Basic (Free)',
        '3month': '3 Month (₹100)',
        '6month': '6 Month (₹300)',
        'lifetime': 'Lifetime (₹600)'
    }
    
    Notification.create_notification(
        user.id,
        f"Your membership has been updated to {membership_names[membership_type]}.",
        'info'
    )
    
    flash(f'Membership updated successfully for {user.name}!', 'success')
    return redirect(url_for('main.memberships'))

# Recent Issues Page
@main.route('/recent-issues')
@login_required
def recent_issues():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    recent_issues = IssuedBook.query.order_by(IssuedBook.issue_date.desc()).limit(50).all()
    return render_template('recent_issues.html', recent_issues=recent_issues)

# Database Admin Page
@main.route('/admin/database')
@login_required
def database_admin():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    # Get database information
    db_info = {
        'database_name': 'SQLite Library Management System',
        'database_path': current_app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///library.db'),
        'total_tables': 5
    }
    
    # Get table information and records
    tables_info = []
    
    # Users table
    users = User.query.all()
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'mobile': user.mobile,
            'role': user.role,
            'membership_type': user.membership_type,
            'membership_expiry': user.membership_expiry.strftime('%Y-%m-%d %H:%M:%S') if user.membership_expiry else 'N/A',
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    tables_info.append({
        'name': 'users',
        'description': 'User accounts (visitors and admins)',
        'record_count': len(users),
        'columns': ['id', 'name', 'email', 'mobile', 'role', 'membership_type', 'membership_expiry', 'created_at'],
        'records': users_data
    })
    
    # Books table
    books = Book.query.all()
    books_data = []
    for book in books:
        books_data.append({
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'category': book.category,
            'total_copies': book.total_copies,
            'available_copies': book.available_copies,
            'cover_photo': book.cover_photo or 'N/A',
            'created_at': book.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    tables_info.append({
        'name': 'books',
        'description': 'Book inventory and details',
        'record_count': len(books),
        'columns': ['id', 'title', 'author', 'category', 'total_copies', 'available_copies', 'cover_photo', 'created_at'],
        'records': books_data
    })
    
    # Issued Books table
    issued_books = IssuedBook.query.all()
    issued_books_data = []
    for issued_book in issued_books:
        issued_books_data.append({
            'id': issued_book.id,
            'user_id': issued_book.user_id,
            'user_name': issued_book.user.name,
            'book_id': issued_book.book_id,
            'book_title': issued_book.book.title,
            'issue_date': issued_book.issue_date.strftime('%Y-%m-%d %H:%M:%S'),
            'due_date': issued_book.due_date.strftime('%Y-%m-%d %H:%M:%S'),
            'return_date': issued_book.return_date.strftime('%Y-%m-%d %H:%M:%S') if issued_book.return_date else 'Not Returned',
            'fine': f'₹{issued_book.fine}' if issued_book.fine > 0 else '₹0'
        })
    
    tables_info.append({
        'name': 'issued_books',
        'description': 'Book issue and return records',
        'record_count': len(issued_books),
        'columns': ['id', 'user_id', 'user_name', 'book_id', 'book_title', 'issue_date', 'due_date', 'return_date', 'fine'],
        'records': issued_books_data
    })
    
    # Notifications table
    notifications = Notification.query.all()
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'user_id': notification.user_id,
            'user_name': notification.user.name,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'is_read': 'Yes' if notification.is_read else 'No',
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    tables_info.append({
        'name': 'notifications',
        'description': 'User notifications and alerts',
        'record_count': len(notifications),
        'columns': ['id', 'user_id', 'user_name', 'message', 'notification_type', 'is_read', 'created_at'],
        'records': notifications_data
    })
    
    # Categories table
    categories = Category.query.all()
    categories_data = []
    for category in categories:
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'books_count': Book.query.filter_by(category=category.name).count()
        })
    
    tables_info.append({
        'name': 'categories',
        'description': 'Book categories and classifications',
        'record_count': len(categories),
        'columns': ['id', 'name', 'created_at', 'books_count'],
        'records': categories_data
    })
    
    # Database statistics
    db_stats = {
        'total_records': sum(table['record_count'] for table in tables_info),
        'active_visitors': User.query.filter_by(role='student').count(),
        'admin_users': User.query.filter_by(role='admin').count(),
        'total_books': Book.query.count(),
        'books_issued': IssuedBook.query.filter(IssuedBook.return_date.is_(None)).count(),
        'books_returned': IssuedBook.query.filter(IssuedBook.return_date.isnot(None)).count(),
        'unread_notifications': Notification.query.filter_by(is_read=False).count(),
        'overdue_books': IssuedBook.query.filter(
            IssuedBook.return_date.is_(None),
            IssuedBook.due_date < datetime.now(timezone.utc)
        ).count()
    }
    
    return render_template('database_admin.html', 
                         db_info=db_info,
                         tables_info=tables_info,
                         db_stats=db_stats)

# Excel Export Route
@main.route('/admin/database/export')
@login_required
def export_database():
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.student_dashboard'))
    
    # Create Excel file in memory
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Export Users
    worksheet = workbook.add_worksheet('Users')
    users = User.query.all()
    headers = ['ID', 'Name', 'Email', 'Mobile', 'Role', 'Membership Type', 'Membership Expiry', 'Created At']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    for row, user in enumerate(users, 1):
        worksheet.write(row, 0, user.id)
        worksheet.write(row, 1, user.name)
        worksheet.write(row, 2, user.email)
        worksheet.write(row, 3, user.mobile or 'N/A')
        worksheet.write(row, 4, user.role)
        worksheet.write(row, 5, user.membership_type)
        worksheet.write(row, 6, user.membership_expiry.strftime('%Y-%m-%d %H:%M:%S') if user.membership_expiry else 'N/A')
        worksheet.write(row, 7, user.created_at.strftime('%Y-%m-%d %H:%M:%S'))
    
    # Export Books
    worksheet = workbook.add_worksheet('Books')
    books = Book.query.all()
    headers = ['ID', 'Title', 'Author', 'Category', 'Total Copies', 'Available Copies', 'Cover Photo', 'Created At']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    for row, book in enumerate(books, 1):
        worksheet.write(row, 0, book.id)
        worksheet.write(row, 1, book.title)
        worksheet.write(row, 2, book.author)
        worksheet.write(row, 3, book.category)
        worksheet.write(row, 4, book.total_copies)
        worksheet.write(row, 5, book.available_copies)
        worksheet.write(row, 6, book.cover_photo or 'N/A')
        worksheet.write(row, 7, book.created_at.strftime('%Y-%m-%d %H:%M:%S'))
    
    # Export Issued Books
    worksheet = workbook.add_worksheet('Issued Books')
    issued_books = IssuedBook.query.all()
    headers = ['ID', 'User ID', 'User Name', 'Book ID', 'Book Title', 'Issue Date', 'Due Date', 'Return Date', 'Fine']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    for row, issued_book in enumerate(issued_books, 1):
        worksheet.write(row, 0, issued_book.id)
        worksheet.write(row, 1, issued_book.user_id)
        worksheet.write(row, 2, issued_book.user.name)
        worksheet.write(row, 3, issued_book.book_id)
        worksheet.write(row, 4, issued_book.book.title)
        worksheet.write(row, 5, issued_book.issue_date.strftime('%Y-%m-%d %H:%M:%S'))
        worksheet.write(row, 6, issued_book.due_date.strftime('%Y-%m-%d %H:%M:%S'))
        worksheet.write(row, 7, issued_book.return_date.strftime('%Y-%m-%d %H:%M:%S') if issued_book.return_date else 'Not Returned')
        worksheet.write(row, 8, issued_book.fine)
    
    # Export Notifications
    worksheet = workbook.add_worksheet('Notifications')
    notifications = Notification.query.all()
    headers = ['ID', 'User ID', 'User Name', 'Message', 'Type', 'Is Read', 'Created At']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    for row, notification in enumerate(notifications, 1):
        worksheet.write(row, 0, notification.id)
        worksheet.write(row, 1, notification.user_id)
        worksheet.write(row, 2, notification.user.name)
        worksheet.write(row, 3, notification.message)
        worksheet.write(row, 4, notification.notification_type)
        worksheet.write(row, 5, 'Yes' if notification.is_read else 'No')
        worksheet.write(row, 6, notification.created_at.strftime('%Y-%m-%d %H:%M:%S'))
    
    # Export Categories
    worksheet = workbook.add_worksheet('Categories')
    categories = Category.query.all()
    headers = ['ID', 'Name', 'Created At', 'Books Count']
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    for row, category in enumerate(categories, 1):
        worksheet.write(row, 0, category.id)
        worksheet.write(row, 1, category.name)
        worksheet.write(row, 2, category.created_at.strftime('%Y-%m-%d %H:%M:%S'))
        worksheet.write(row, 3, Book.query.filter_by(category=category.name).count())
    
    workbook.close()
    
    output.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'library_database_export_{timestamp}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
