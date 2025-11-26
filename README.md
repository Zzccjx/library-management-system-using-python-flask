# Library Management System

A comprehensive Flask-based library management system with role-based access control, book management, and automated notifications.

## Features

### For Administrators
- **Dashboard**: Overview of library statistics and recent activities
- **Book Management**: Add, edit, delete books with cover photo uploads
- **Issue/Return System**: Track book transactions with due dates
- **User Management**: View student accounts and their book history
- **Overdue Tracking**: Monitor overdue books and calculate fines

### For Students
- **Book Browsing**: Search and filter books by title, author, or category
- **My Books**: View borrowed books, due dates, and return history
- **Notifications**: Receive alerts for due dates and overdue books
- **Fine Tracking**: View accumulated fines for overdue books

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd library_system
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   copy .env.example .env
   # Edit .env with your actual values
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

## Default Accounts

### Admin Account
- **Email**: admin@library.com
- **Password**: admin123

### Student Account
- **Email**: student@library.com
- **Password**: student123

## Configuration

- **Fine Rate**: ₹10 per day for overdue books
- **Loan Period**: 14 days
- **File Upload**: Supports PNG, JPG, JPEG, GIF (max 16MB)
- **Session Timeout**: 2 hours

## Database Schema

- **Users**: Authentication and role management
- **Books**: Book catalog with availability tracking
- **IssuedBooks**: Transaction records with due dates
- **Notifications**: User alerts and messages

## API Endpoints

- `GET /api/notifications/count` - Get unread notification count

## Security Features

- Password hashing with Werkzeug
- Session management with Flask-Login
- Role-based access control
- Secure file uploads
- CSRF protection ready

## Technologies Used

- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Frontend**: Bootstrap 5, Bootstrap Icons
- **Database**: SQLite (configurable)
- **File Handling**: Werkzeug secure uploads
