from flask import Blueprint, current_app, request, jsonify, render_template, redirect, url_for, flash
import sqlite3
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

user_auth_bp = Blueprint('user_auth', __name__)

def get_db_connection():
    conn = sqlite3.connect('municipality.db')
    conn.row_factory = sqlite3.Row
    return conn

@user_auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        print("🔍 Received Headers:", dict(request.headers))
        print("🔍 Received Data:", request.get_json() if request.is_json else request.form)
        try:
            data = request.get_json() if request.is_json else request.form
            
            username = data.get('username')
            password = data.get('password')
            full_name = data.get('full_name')
            email = data.get('email')
            phone_number = data.get('phone_number')
            address = data.get('address')
            role = data.get('role')
            municipality = data.get('municipality')

            print(f"📌 Extracted: username={username}, email={email}, phone={phone_number}")

            
            if not all([username, password, full_name, email, phone_number, address, role, municipality]):
                return jsonify({"error": "All fields are required!"}), 400
            
            municipality = int(municipality)
            conn = get_db_connection()
            cursor = conn.cursor()
            
            print("🔍 Checking if municipality exists...")
            cursor.execute("SELECT id FROM municipalities WHERE id = ?", (municipality,))
            municipality_exists = cursor.fetchone()
            print(f"🔎 Municipality Query Result: {municipality_exists}")

            if not municipality_exists:
                conn.close()
                return jsonify({"error": "Invalid Municipality!"}), 400
            
            print("🔍 Checking if user already exists...")
            cursor.execute("SELECT * FROM user_profiles WHERE phone_number = ? OR email = ?", (phone_number, email))
            existing_user = cursor.fetchone()
            print(f"🔎 Existing User Check: {existing_user}") 
            if existing_user:
                print("❌ User already exists!")  # 💡 Extra Debugging
                conn.close()
                return jsonify({"error": "Username, email, or phone number already exists!"}), 400
            
            
            hashed_password = generate_password_hash(password)
            cursor.execute(
                """
                INSERT INTO user_profiles (username, password, full_name, email, phone_number, address, role, municipality_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (username, hashed_password, full_name, email, phone_number, address, role, municipality)
            )
            conn.commit()
            conn.close()
            print("✅ Registration successful!")
            return jsonify({"message": "Registration successful!"}), 200
        
        except sqlite3.IntegrityError:
            print("❌ Integrity Error: Username or email already exists!") 
            return jsonify({"error": "Username or email already exists!"}), 400
        
        except Exception as e:
            print("❌ ERROR:", str(e))
            return jsonify({"error": str(e)}), 500
        finally:
            # ✅ Ensure connection is always closed
            conn.close()
    
    return render_template('register.html')

@user_auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json() if request.is_json else request.form
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                return jsonify({"error": "Email and password are required!"}), 400
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_profiles WHERE email = ?", (email,))
            user = cursor.fetchone()
            conn.close()
            
            if not user or not check_password_hash(user['password'], password):
                return jsonify({"error": "Invalid email or password!"}), 401
            
            expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            token = jwt.encode(
              {
                'email': user['email'],
                'role': user['role'],
                'user_id': user['id'],  # ✅ Needed for form submission
                'municipality_id': user['municipality_id'],  # ✅ Needed for form submission
                'exp': expiration_time
              },
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
            )
            
            response = jsonify({"token": token, "role": user['role']})

            response.set_cookie('token', token, httponly=True, secure=True)
            return response
        
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return render_template('login.html')

@user_auth_bp.route('/login_register')
def login_register():
    return render_template('login.html')

@user_auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("Email is required!", "error")
            return render_template('forgot_password.html')
        
        print(f"A password reset link has been sent to: {email}")
        flash(f"A password reset link has been sent to your email: {email}.", "success")
        return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')
