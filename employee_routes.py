
from flask import Blueprint, request, jsonify, current_app, render_template, send_from_directory
import sqlite3
import jwt
from document_models import get_all_category_3_licenses

employee_bp = Blueprint('employee_bp', __name__)

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('municipality.db')
    conn.row_factory = sqlite3.Row
    return conn

def role_required(required_role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            token = request.cookies.get('token')
            if not token:
                return jsonify({"error": "Authentication token missing"}), 403

            try:
                decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                if decoded.get("role") != required_role:
                    return jsonify({"error": "Unauthorized"}), 403
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 403
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 403

            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

@employee_bp.route('/submitted_docs', methods=['GET'])
def get_category_3_licenses():
    try:
        token = request.cookies.get('token')
        if not token:
            return jsonify({"error": "Authentication token missing"}), 403

        try:
            decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            role = decoded.get('role')
            municipality_id = decoded.get('municipality_id')
            if role != 'Municipality Employee':
                return jsonify({"error": "Unauthorized"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 403
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 403

        all_documents = get_all_category_3_licenses()
        filtered_documents = [doc for doc in all_documents if doc.get('municipality_id') == municipality_id]

        return render_template('all_documents.html', documents=filtered_documents)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@employee_bp.route('/review_doc/<int:license_id>', methods=['POST'])
def review_license(license_id):
    try:
        token = request.cookies.get('token')
        if not token:
            return jsonify({"error": "Authentication token missing"}), 403

        decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        if decoded.get('role') != 'Municipality Employee':
            return jsonify({"error": "Unauthorized"}), 403

        data = request.get_json()
        new_status = data.get('status')

        if new_status not in ["Approved", "Rejected", "Pending"]:
            return jsonify({"error": "Invalid status"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE category_3_license_requests
            SET status = ?
            WHERE id = ?
        """, (new_status, license_id))
        conn.commit()
        conn.close()

        return jsonify({"message": f"Status updated to {new_status}."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@employee_bp.route('/download/<path:filename>')
def download_file(filename):
    uploads_dir = os.path.join(current_app.root_path, 'uploads')
    return send_from_directory(uploads_dir, filename, as_attachment=True)

@employee_bp.route('/submit_info_post', methods=['POST'])
@role_required("Municipality Employee")
def submit_info_post():
    title = request.form.get("title")
    description = request.form.get("description")
    category = request.form.get("category")
    image = request.files.get("image")  # May be None

    if not title or not description or not category:
        return jsonify({"error": "Missing or invalid fields"}), 400

    # Validate category
    if category not in ["tourism", "municipal_info"]:
        return jsonify({"error": "Invalid category"}), 400

    image_path = None
    if category == "tourism" and image and image.filename:
        filename = secure_filename(image.filename)
        image_path = os.path.join("static", "uploads", filename)
        image.save(image_path)

    # Get municipality from JWT
    token = request.cookies.get('token')
    decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
    municipality_id = decoded.get('municipality_id')

    # Insert into DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO info_posts (title, description, category, image_path, municipality_id)
        VALUES (?, ?, ?, ?, ?)
    """, (title, description, category, image_path, municipality_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Info post submitted successfully!"})




@employee_bp.route('/get_info_posts/<category>', methods=['GET'])
@role_required("Municipality Employee")  # or remove if it's for citizens too
def get_info_posts(category):
    if category not in ["tourism", "municipal_info"]:
        return jsonify({"error": "Invalid category"}), 400

    # 🔐 Decode token to get municipality_id
    token = request.cookies.get("token")
    if not token:
        return jsonify({"error": "Authentication required"}), 403

    try:
        decoded = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        municipality_id = decoded.get("municipality_id")
    except Exception:
        return jsonify({"error": "Invalid token"}), 403

    # ✅ Fetch filtered posts
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, description, created_at, image_path
        FROM info_posts
        WHERE category = ? AND municipality_id = ?
        ORDER BY created_at DESC
    """, (category, municipality_id))
    posts = cursor.fetchall()
    conn.close()

    return jsonify([dict(p) for p in posts])



@employee_bp.route('/municipality_dashboard')
@role_required("Municipality Employee")
def municipality_dashboard():
    return render_template("dashboard_home.html")  # ✅ must match your file name

@employee_bp.route('/post_info')
@role_required("Municipality Employee")
def post_info():
    return render_template("employee_dashboard.html")  # ✅ must match your file name

@employee_bp.route('/delete_info_post/<int:post_id>', methods=['DELETE'])
@role_required("Municipality Employee")
def delete_info_post(post_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM info_posts WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Post deleted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@employee_bp.route('/submit_purchase', methods=['POST'])
@role_required("Municipality Employee")
def submit_purchase():
    data = request.get_json()
    title = data.get("title")
    vendor = data.get("vendor")
    amount = data.get("amount")
    purchase_date = data.get("purchase_date")

    if not title or not vendor or not amount or not purchase_date:
        return jsonify({"error": "All fields are required"}), 400

    # 🔐 Decode token to get municipality_id
    token = request.cookies.get("token")
    decoded = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    municipality_id = decoded.get("municipality_id")

    if not municipality_id:
        return jsonify({"error": "Municipality ID missing in token"}), 403

    # 💾 Store with municipality_id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO municipal_purchases (title, vendor, amount, purchase_date, municipality_id)
        VALUES (?, ?, ?, ?, ?)
    """, (title, vendor, amount, purchase_date, municipality_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Purchase added successfully!"})


@employee_bp.route('/get_purchases', methods=['GET'])
@role_required("Municipality Employee")
def get_purchases():
    token = request.cookies.get("token")
    decoded = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    municipality_id = decoded.get("municipality_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM municipal_purchases
        WHERE municipality_id = ?
        ORDER BY created_at DESC
    """, (municipality_id,))
    purchases = cursor.fetchall()
    conn.close()

    return jsonify([dict(p) for p in purchases])



@employee_bp.route('/delete_purchase/<int:purchase_id>', methods=['DELETE'])
@role_required("Municipality Employee")
def delete_purchase(purchase_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM municipal_purchases WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Purchase deleted successfully"})

