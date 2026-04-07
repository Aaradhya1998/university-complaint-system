from flask import Flask, render_template, request, redirect, url_for, flash, session

from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import os
import random
import string
import matplotlib
matplotlib.use('Agg')
import sys
print(sys.executable)
from database import (
    get_categories,
    get_category_counts,
    get_complaint_by_ticket,   
    get_complaints,
    get_status_counts,
    init_app as init_database,
    insert_complaint,
    mark_complaint_resolved,
)
from database import get_complaint_by_id
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '0496f049d0dfcb00f336d4e264964254e714d56374d7369586415738bc496cfb')
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = (
    os.environ.get('MAIL_DEFAULT_SENDER') or app.config['MAIL_USERNAME']
)
if not app.config['MAIL_DEFAULT_SENDER']:
    raise RuntimeError("MAIL_USERNAME or MAIL_DEFAULT_SENDER must be configured in .env")

mail = Mail(app)
init_database(app)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    otp = ''.join(random.choices(string.digits, k=6))
    session['otp'] = otp
    session['email'] = email
    msg = Message(
        'Your OTP Code',
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[email],
    )
    
    msg.body = f'Your OTP code is {otp}'
    print("Sending OTP to:", email)
    print("Using:", app.config['MAIL_USERNAME'])
    mail.send(msg)
    return render_template('otp_verify.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    entered_otp = request.form['otp']
    if entered_otp == session.get('otp'):
        return redirect(url_for('user_dashboard'))
    else:
        flash('Invalid OTP. Please try again.')
        return redirect(url_for('home'))
        
@app.route('/dashboard')
def user_dashboard():
    if 'email' not in session:
        return redirect(url_for('home'))
    return render_template('dashboard.html')
@app.route('/complaint_form')
def complaint_form():
    categories = [
        'Waste', 'Sanitation', 'Washroom', 'Library', 'Classrooms',
        'Electrical', 'Teaching Faculty', 'Course', 'Non-Teaching Faculty',
        'Security', 'Lost & Found'
    ]
    return render_template('complaint_form.html', categories=categories)

@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    email = session.get('email')

    prn_or_faculty_id = request.form['prn_or_faculty_id']
    category = request.form['category']
    description = request.form['description']

    image_path = None
    if 'image' in request.files:
        image = request.files['image']
        if image and image.filename:
            filename = secure_filename(image.filename)
            upload_dir = os.path.join(app.static_folder, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            image.save(os.path.join(upload_dir, filename))
            image_path = filename

    ticket_id = insert_complaint(
        email=email,
        prn_or_faculty_id=prn_or_faculty_id,
        category=category,
        description=description,
        image_path=image_path,
    )
    print("Inserted ticket:", ticket_id)

    flash(f"Complaint submitted! Ticket ID: {ticket_id}")
    return redirect(url_for('complaint_form'))


class Complaint:
    id: int
    email: str
    prn_or_faculty_id: str
    category: str
    description: str
    image_path: str | None
    status: str
    created_at: str



    
    
  
@app.route('/track', methods=['GET', 'POST'])
def track_complaint():
    complaint = None

    if request.method == 'POST':
        ticket_id = request.form.get('complaint_id')

        if ticket_id:
            complaint = get_complaint_by_ticket(ticket_id.strip())

        if not complaint:
            flash("Complaint not found")

    return render_template('track.html', complaint=complaint)

@app.route('/admin_dashboard')
def admin_dashboard():
    generate_graphs()
    selected_category = request.args.get('category', '').strip()
    selected_status = request.args.get('status', '').strip()

    complaints = get_complaints(
        category=selected_category or None,
        status=selected_status or None,
    )
    print("complaints fetched :", complaints)
    categories = get_categories()

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        categories=categories,
        selected_category=selected_category,
        selected_status=selected_status,
    )


@app.route('/mark_resolved/<int:complaint_id>', methods=['POST'])
def mark_resolved(complaint_id):
    complaint = get_complaint_by_id(complaint_id)
    if complaint is None:
        flash('Complaint not found.')
    elif mark_complaint_resolved(complaint_id):
        flash('Complaint marked as resolved!')
    else:
        flash('Unable to update complaint status.')
    return redirect(url_for('admin_dashboard'))


def generate_graphs():
    import matplotlib.pyplot as plt
    
    graph_dir = os.path.join(app.static_folder, 'graphs')
    os.makedirs(graph_dir, exist_ok=True)

    # ------------------ CATEGORY BAR GRAPH ------------------
    category_counts = get_category_counts()
    categories = [item[0] for item in category_counts]
    counts = [item[1] for item in category_counts]

    plt.figure(figsize=(10, 6))

    if categories:
        colors = [
            "#4f46e5", "#0ea5e9", "#9333ea", "#f59e0b",
            "#14b8a6", "#6366f1", "#06b6d4", "#8b5cf6"
        ]

        bar_colors = [colors[i % len(colors)] for i in range(len(categories))]

        bars = plt.bar(categories, counts, color=bar_colors)

        # Add values on top
        for i, v in enumerate(counts):
            plt.text(i, v + 0.2, str(v), ha='center', fontsize=10)

        plt.xticks(rotation=30, ha='right')
        plt.grid(axis='y', linestyle='--', alpha=0.3)

    else:
        plt.text(0.5, 0.5, 'No complaints yet', ha='center')
        plt.axis('off')

    plt.title('Category-wise Complaint Distribution')
    plt.xlabel('Categories')
    plt.ylabel('Number of Complaints')
    plt.tight_layout()
    plt.savefig(os.path.join(graph_dir, 'category_distribution.png'))
    plt.close()

    # ------------------ STATUS PIE GRAPH ------------------
    resolved_count, not_resolved_count = get_status_counts()

    plt.figure(figsize=(7, 7))

    if resolved_count + not_resolved_count > 0:
        plt.pie(
            [resolved_count, not_resolved_count],
            labels=['Resolved', 'Not Resolved'],
            autopct='%1.1f%%',
            colors=["#16a34a", "#dc2626"],  # green, red
            startangle=140
        )
        plt.axis('equal')  # perfect circle

    else:
        plt.text(0.5, 0.5, 'No complaints yet', ha='center')
        plt.axis('off')

    plt.title('Resolved vs Not Resolved Complaints')
    plt.tight_layout()
    plt.savefig(os.path.join(graph_dir, 'resolved_vs_not_resolved.png'))
    plt.close()

@app.route("/send_otp", methods=["GET", "POST"])
def send_otp():
    if request.method == "POST":
        return login()
    return redirect(url_for("home"))

if __name__ == '__main__':
    app.run(debug=True)
