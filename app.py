from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import os
import re

app = Flask(__name__)
app.secret_key = 'securecloud_secret_key'
auth = HTTPBasicAuth()

# Kriptoqrafiya üçün açar (AES / Fernet)
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Admin şifrəsi
users_auth = {
    "admin": generate_password_hash("12345")
}

@auth.verify_password
def verify_password(username, password):
    if username in users_auth and check_password_hash(users_auth.get(username), password):
        return username

# AWS RDS PostgreSQL bağlantısı
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:hU5B9pFLN7hLrth@securecloud-db.cj8o2igwsxku.eu-north-1.rds.amazonaws.com:5432/securecloud_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class TicketBooking(db.Model):
    __tablename__ = 'flight_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    passenger_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    encrypted_passport = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
@auth.login_required
def admin():
    all_tickets = TicketBooking.query.all()
    decrypted_tickets = []
    
    for ticket in all_tickets:
        try:
            decrypted_pass = cipher_suite.decrypt(ticket.encrypted_passport.encode()).decode()
        except Exception:
            decrypted_pass = "[Deşifrə etmək mümkün olmadı]"
            
        decrypted_tickets.append({
            'id': ticket.id,
            'passenger_name': ticket.passenger_name,
            'email': ticket.email,
            'destination': ticket.destination,
            'encrypted_raw': ticket.encrypted_passport[:25] + '...',
            'passport': decrypted_pass
        })

    response = make_response(render_template('admin.html', tickets=decrypted_tickets))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Bilet Bron Etmə və Pasport Validasiyası (2 hərf + 7 rəqəm)
@app.route('/book', methods=['POST'])
def book_ticket():
    name = request.form.get('passenger_name')
    email = request.form.get('email')
    destination = request.form.get('destination')
    passport = request.form.get('passport', '').strip()
    
    # Pasport formatının yoxlanılması (Dəqiq 2 hərf və 7 rəqəm: məsələn C1234567)
    passport_pattern = r'^[A-Za-z]{2}\d{7}$'
    
    if not re.match(passport_pattern, passport):
        flash("❌ XƏTA: Pasport nömrəsi dəqiq 2 hərf və 7 rəqəmdən ibarət olmalıdır (Məsələn: C1234567)!")
        return redirect(url_for('home'))

    if name and email and destination and passport:
        try:
            # Məlumatı şifrələyirik (Encrypt)
            encrypted_data = cipher_suite.encrypt(passport.upper().encode()).decode()
            
            new_ticket = TicketBooking(
                passenger_name=name, 
                email=email, 
                destination=destination, 
                encrypted_passport=encrypted_data
            )
            db.session.add(new_ticket)
            db.session.commit()
            flash("🎉 Təbriklər! Biletiniz bron edildi və pasport məlumatınız şifrələndi.")
        except Exception as e:
            db.session.rollback()
            flash("Xəta baş verdi. Zəhmət olmasa yenidən yoxlayın.")
        
    return redirect(url_for('home'))

@app.route('/delete/<int:id>')
@auth.login_required
def delete_ticket(id):
    ticket_to_delete = TicketBooking.query.get_or_404(id)
    db.session.delete(ticket_to_delete)
    db.session.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)