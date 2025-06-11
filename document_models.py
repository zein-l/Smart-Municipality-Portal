import os
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads/"
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'png'}

def get_db_connection():
    conn = sqlite3.connect("municipality.db")
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file_storage):
    if file_storage and allowed_file(file_storage.filename):
        filename = secure_filename(file_storage.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_storage.save(save_path)
        return save_path
    return None

def insert_category_3_license(user_id, municipality_id, business_name, owner_name, phone_number,
                               address, business_activity, payment_method, card_number,
                               expiry_date, cvc, ownership_proof, safety_clearance, municipal_approval):
    ownership_proof_path = save_file(ownership_proof)
    safety_clearance_path = save_file(safety_clearance)
    municipal_approval_path = save_file(municipal_approval)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_3_license_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            municipality_id INTEGER NOT NULL,
            business_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            address TEXT NOT NULL,
            business_activity TEXT NOT NULL,
            ownership_proof_path TEXT,
            safety_clearance_path TEXT,
            municipal_approval_path TEXT,
            payment_method TEXT,
            card_number TEXT,
            expiry_date TEXT,
            cvc TEXT,
            status TEXT DEFAULT 'Pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_profiles(id),
            FOREIGN KEY (municipality_id) REFERENCES municipalities(id)
        )
    """)

    cursor.execute("""
        INSERT INTO category_3_license_requests (
            user_id, municipality_id, business_name, owner_name, phone_number, address,
            business_activity, ownership_proof_path, safety_clearance_path,
            municipal_approval_path, payment_method, card_number, expiry_date, cvc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, municipality_id, business_name, owner_name, phone_number, address,
        business_activity, ownership_proof_path, safety_clearance_path,
        municipal_approval_path, payment_method, card_number, expiry_date, cvc
    ))

    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return {"request_id": inserted_id}

def get_all_category_3_licenses():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, user_id, municipality_id, business_name, owner_name, phone_number,
               address, business_activity, ownership_proof_path, safety_clearance_path,
               municipal_approval_path, payment_method, status, submitted_at
        FROM category_3_license_requests
        ORDER BY submitted_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    licenses = []
    for row in rows:
        licenses.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "municipality_id": row["municipality_id"],
            "business_name": row["business_name"],
            "owner_name": row["owner_name"],
            "phone_number": row["phone_number"],
            "address": row["address"],
            "business_activity": row["business_activity"],
            "ownership_proof_path": row["ownership_proof_path"],
            "safety_clearance_path": row["safety_clearance_path"],
            "municipal_approval_path": row["municipal_approval_path"],
            "payment_method": row["payment_method"],
            "status": row["status"],
            "submitted_at": row["submitted_at"]
        })

    return licenses




