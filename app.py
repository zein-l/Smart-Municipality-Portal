import hashlib
import html
import re
from bs4 import BeautifulSoup
from flask import Flask, current_app, flash, render_template, render_template_string, request, jsonify, redirect, session, url_for,  send_from_directory
import sqlite3
import jwt
import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from flask_cors import CORS
import json
from rapidfuzz import process
import google.generativeai as genai
from user_auth import user_auth_bp
from google.cloud import translate_v2 as translate
#from translation_helper import translate_text
from flask import render_template 

app = Flask(__name__ , static_folder="static")
CORS(app)
app.config['SECRET_KEY'] = 'your_secret_key'
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'png'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
translate_client = translate.Client()

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

TRANSLATION_CACHE_FILE = "translation_cache.json"
try:
    with open(TRANSLATION_CACHE_FILE, "r", encoding="utf-8") as f:
        TRANSLATION_CACHE = json.load(f)
except FileNotFoundError:
    TRANSLATION_CACHE = {}

# Google Translate API client
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-translate-key.json"
translate_client = translate.Client()

def translate_text(text, target_language):
    """Caches translations to avoid unnecessary API calls."""
    if not text.strip():
        return text  # Skip empty text
    
    # Create a unique cache key
    cache_key = hashlib.md5(f"{text}-{target_language}".encode()).hexdigest()

    # Return cached translation if available
    if cache_key in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[cache_key]

    # Call Google Translate API
    result = translate_client.translate(text, target_language=target_language)
    translated_text = result["translatedText"]

    # Store in cache
    TRANSLATION_CACHE[cache_key] = translated_text

    # Save cache to file
    with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(TRANSLATION_CACHE, f, ensure_ascii=False, indent=2)

    return translated_text

def get_db_connection():
    conn = sqlite3.connect('municipality.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lease_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            parcel_number INTEGER NOT NULL,
            unit_number INTEGER NOT NULL,
            cadastral_zone TEXT NOT NULL,
            lease_contract_path TEXT NOT NULL,
            lease_contract_copy_path TEXT NOT NULL,
            historical_statement_path TEXT,
            id_card_copy_path TEXT,
            payment_method TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone_number TEXT NOT NULL,
            address TEXT NOT NULL,
            role TEXT DEFAULT 'Citizen'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            complaint_text TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            feedback TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS info_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT CHECK(category IN ('tourism', 'municipal_info')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
    # cursor.execute("ALTER TABLE info_posts ADD COLUMN image_path TEXT")
    cursor.execute("""
CREATE TABLE IF NOT EXISTS municipal_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    vendor TEXT NOT NULL,
    amount TEXT NOT NULL,
    purchase_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    conn.commit()
    conn.close()

create_tables()

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get('Authorization') or request.cookies.get('token')
            if not token:
                return jsonify({"error": "Token is missing!"}), 401
            try:
                decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                user_role = decoded.get('role', 'Citizen')
                if user_role != required_role:
                    return jsonify({"error": "Unauthorized Access!"}), 403
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token has expired!"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token!"}), 401
        return decorated_function
    return decorator

# Register the authentication blueprint.
app.register_blueprint(user_auth_bp)

@app.route('/')
def root():
    return redirect(url_for('user_auth.login'))

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-translate-key.json"


def translate_template(template_content, target_language):
    """Translates all visible text in an HTML template while preserving Jinja2 syntax."""
    
    # Preserve Jinja2 template expressions by replacing them with placeholders
    jinja_expressions = re.findall(r"(\{\{.*?\}\}|\{%.*?%\})", template_content)
    placeholders = {f"__JINJA_{i}__": expr for i, expr in enumerate(jinja_expressions)}
    
    for placeholder, expr in placeholders.items():
        template_content = template_content.replace(expr, placeholder)

    # Use BeautifulSoup to parse the HTML while keeping structure intact
    soup = BeautifulSoup(template_content, "html.parser")

    # Translate only visible text (excluding scripts, styles, and Jinja2 placeholders)
    for element in soup.find_all(string=True):
        if element.parent.name not in ["script", "style"]:
            translated_text = translate_text(element, target_language)
            element.replace_with(translated_text)

    # Restore Jinja2 expressions in the translated content
    translated_content = str(soup)
    for placeholder, expr in placeholders.items():
        translated_content = translated_content.replace(placeholder, expr)

    return translated_content

@app.route('/home')
def home():
    token = request.cookies.get('token')
    if not token:
        return redirect(url_for('user_auth.login'))

    lang = request.args.get("lang", "en")

    # Read the template file content
    with open("templates/index.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)

    return render_template_string(translated_content)

@app.route('/logout')
def logout():
    session.clear()
    response = redirect(url_for('user_auth.login'))
    response.delete_cookie('token')
    return response

# --- Other Routes in Your Application ---

@app.route('/document_request')
def document_request():
    lang = request.args.get("lang", "en")

    # Read the template file content
    with open("templates/document.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)
    translated_content = html.unescape(translated_content)

    return render_template_string(translated_content)


from flask import render_template, request, redirect, url_for, abort
from jinja2 import TemplateNotFound
@app.route('/document/<doc_name>')
def document_page(doc_name):
    lang = request.args.get("lang", "en")

    # Read the template file content
    with open(f"templates/{doc_name}.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)
    translated_content = html.unescape(translated_content)

    return render_template_string(translated_content)
    



@app.route('/lease_contract')
def lease_contract():
    return render_template('lease_contract.html')

@app.route('/submit_lease_contract', methods=['POST'])
def submit_lease_contract():
    print("Form received:", request.form)
    print("Files received:", request.files)
    full_name       = request.form['full-name']
    address         = request.form['address']
    phone_number    = request.form['phone-number']
    parcel_number   = request.form['parcel-number']
    unit_number     = request.form['unit-number']
    cadastral_zone  = request.form['cadastral-zone']
    payment_method  = request.form['payment-method']
    
    files = {}
    required_files = ['lease-contract', 'lease-contract-copy']
    optional_files = ['historical-statement', 'id-card-copy']

    for file_key in required_files + optional_files:
        if file_key in request.files:
            file = request.files[file_key]
            if file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(os.getcwd(), app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    files[file_key] = file_path
                else:
                    print(f"File {file.filename} has an invalid format.")
            else:
                print(f"No file selected for {file_key}.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO lease_contracts (
            full_name, address, phone_number, parcel_number, unit_number, cadastral_zone, 
            lease_contract_path, lease_contract_copy_path, historical_statement_path, id_card_copy_path, 
            payment_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (full_name, address, phone_number, parcel_number, unit_number, cadastral_zone,
          files.get('lease-contract', ''), files.get('lease-contract-copy', ''),
          files.get('historical-statement', ''), files.get('id-card-copy', ''), payment_method))
    conn.commit()
    conn.close()
    
    return redirect(url_for('document_request'))



@app.route('/get_lease_contracts', methods=['GET'])
def get_lease_contracts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, submitted_at, status FROM lease_contracts")
        contracts = cursor.fetchall()
        conn.close()
        contracts_list = [dict(contract) for contract in contracts]
        return jsonify(contracts_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/fees_installments', methods=['GET', 'POST'])
def fees_installments():
    return render_template('fees_installments.html')

@app.route('/statement_request', methods=['GET', 'POST'])
def statement_request():
    return render_template('statement_request.html')

@app.route('/disabled_person_request', methods=['GET', 'POST'])
def disabled_person_request():
    return render_template('disabled_person.html')

@app.route('/shakwa_moraja3a', methods=['GET', 'POST'])
def shakwa_moraja3a():
    return render_template('shakwa_aw_moraja3a.html')

@app.route('/submit_document_request', methods=['POST'])
def submit_document_request():
    return "Document request submitted successfully!"

@app.route('/talab_bara2it_zeme', methods=['GET', 'POST'])
def talab_bara2it_zeme():
    return render_template('talab_bara2it_zeme.html')

@app.route('/submit_clearance_request', methods=['POST'])
def submit_clearance_request():
    return "Document request submitted successfully!"


@app.route('/review_request/<int:request_id>', methods=['GET', 'POST'])
def review_request(request_id):
    if request.method == 'POST':
        feedback = request.form.get('feedback')
        status   = request.form.get('status')
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if status == "Rejected":
                cursor.execute("DELETE FROM lease_contracts WHERE id = ?", (request_id,))
                conn.commit()
                flash("Request has been rejected and deleted.", "success")
                return redirect(url_for('municipality_dashboard'))
            else:
                cursor.execute("""
                    UPDATE lease_contracts
                    SET status = ?, reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, request_id))
                conn.commit()
                flash("Request status updated successfully!", "success")
            conn.close()
            return redirect(url_for('review_request', request_id=request_id))
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for('review_request', request_id=request_id))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, full_name, address, phone_number, parcel_number, unit_number, 
                   cadastral_zone, lease_contract_path, lease_contract_copy_path, 
                   historical_statement_path, id_card_copy_path, payment_method, submitted_at, status
            FROM lease_contracts WHERE id = ?
        """, (request_id,))
        request_details = cursor.fetchone()
        conn.close()
        if not request_details:
            flash("Request not found!", "error")
            return redirect(url_for('root'))
        request_data = dict(request_details)
        files = []
        file_fields = {
            "Lease Contract": request_data["lease_contract_path"],
            "Lease Contract Copy": request_data["lease_contract_copy_path"],
            "Historical Statement": request_data["historical_statement_path"],
            "ID Card Copy": request_data["id_card_copy_path"]
        }
        for file_name, file_path in file_fields.items():
            if file_path:
                files.append({
                    "file_name": file_name,
                    "file_url": url_for('static', filename='uploads/' + os.path.basename(file_path))
                })
        return render_template("review_request.html", request_data=request_data, files=files)
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for('root'))

@app.route('/complaint')
def complaint_page():
    lang = request.args.get("lang", "en")

    # Read the template file content
    with open("templates/complaint.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)
    translated_content = html.unescape(translated_content)

    return render_template_string(translated_content)

@app.route('/council_purchases')
def council_purchases():
    lang = request.args.get("lang", "en")

    token = request.cookies.get("token")
    if not token:
        return redirect(url_for("user_auth.login_register"))

    try:
        decoded = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        municipality_id = decoded.get("municipality_id")
    except Exception:
        return redirect(url_for("user_auth.login_register"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM info_posts
        WHERE category = 'municipal_info' AND municipality_id = ?
        ORDER BY created_at DESC
    """, (municipality_id,))
    posts = cursor.fetchall()

    cursor.execute("""
        SELECT * FROM municipal_purchases
        WHERE municipality_id = ?
        ORDER BY purchase_date DESC
    """, (municipality_id,))
    purchases = cursor.fetchall()

    conn.close()

    # ✅ Use the real Jinja template engine
    with open("templates/council-info.html", "r", encoding="utf-8") as f:
        template_content = f.read()
    translated_content = translate_template(template_content, lang)
    return render_template_string(translated_content, posts=posts, purchases=purchases)







@app.route('/careers_volunteers')
def careers_volunteers():
    lang = request.args.get("lang", "en")

    # Read the template file content
    with open("templates/careers.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)
    translated_content = html.unescape(translated_content)

    return render_template_string(translated_content)

@app.route('/contact')
def contact():
    lang = request.args.get("lang", "en")

    # Read the template file content
    with open("templates/contact.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)
    translated_content = html.unescape(translated_content)

    return render_template_string(translated_content)


@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    data = request.json
    email = data.get('email')
    complaint_text = data.get('complaint_text')
    if not email or not complaint_text:
        return jsonify({"error": "Email and complaint text are required!"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_profiles WHERE email = ?", (email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found!"}), 404
    user_id = user['id']
    cursor.execute("""
        INSERT INTO complaints (user_id, complaint_text)
        VALUES (?, ?)
    """, (user_id, complaint_text))
    conn.commit()
    conn.close()
    return jsonify({"message": "Complaint submitted successfully!"})

@app.route('/get_complaints', methods=['GET'])
def get_complaints():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, u.full_name, c.complaint_text, c.status, c.feedback, c.submitted_at
        FROM complaints c
        JOIN user_profiles u ON c.user_id = u.id
    """)
    complaints = cursor.fetchall()
    conn.close()
    return jsonify([dict(complaint) for complaint in complaints])

@app.route('/review_complaint/<int:complaint_id>', methods=['POST'])
def review_complaint(complaint_id):
    data = request.json
    feedback = data.get('feedback')
    status = data.get('status')
    if not feedback or not status:
        return jsonify({"error": "Feedback and status are required!"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE complaints
        SET feedback = ?, status = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (feedback, status, complaint_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Complaint reviewed successfully!"})

@app.route('/map')
def map_page():
    lang = request.args.get("lang", "en")

    # Read the template file content
    with open("templates/map.html", "r", encoding="utf-8") as f:
        template_content = f.read()

    # Translate and serve the template
    translated_content = translate_template(template_content, lang)
    translated_content = html.unescape(translated_content)

    return render_template_string(translated_content)

with open("static/geojson/municipalities_data_with_coords.json", "r", encoding="utf-8") as file:
    municipalities = json.load(file)

@app.route('/search', methods=['GET'])
def search_municipality():
    query = request.args.get('name', '').strip().lower()
    
    if not query:
        return jsonify({"error": "No search term provided"}), 400

    # Find the matching municipality
    result = next((mun for mun in municipalities if mun["Name_EN"].strip().lower() == query), None)

    if result:
        return jsonify(result)
    else:
        return jsonify({"error": "Municipality not found"}), 404
    
@app.route('/static/geojson/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.root_path, 'static/geojson'), filename)

# @app.route('/municipality_dashboard')
# @role_required("Municipality Employee")  # ✅ Ensures only employees can access it
# def municipality_dashboard():
#     return render_template('municipality_dashboard.html')


@app.route('/get_municipalities', methods=['GET'])
def get_municipalities():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM municipalities")  # ✅ Ensure table name is correct
        municipalities = cursor.fetchall()
        conn.close()
        
        if not municipalities:
            print("⚠️ No municipalities found in the database!")  # ✅ Debugging output
            return jsonify([])  # ✅ Return an empty array instead of None
        
        # ✅ Ensure we return a valid JSON array
        municipality_list = [{"id": row["id"], "name": row["name"]} for row in municipalities]
        
        
        return jsonify(municipality_list)
    
    except Exception as e:
        print("❌ Error fetching municipalities:", str(e))  # ✅ Debugging info
        return jsonify({"error": str(e)}), 500  # ✅ Return error in JSON format



# Set your Google AI API Key (Get it from https://aistudio.google.com/)
genai.configure(api_key="AIzaSyBKreYbp2ZIhwA29TNv6Q-sYOgxKQnByag")


# Load FAQs from JSON
def load_faqs():
    """Load FAQs from JSON file."""
    with open("static/faqs.json", "r", encoding="utf-8") as file:
        return json.load(file)["faqs"]

from rapidfuzz import process, fuzz
from textblob import TextBlob


SAFE_WORDS = {"zalka", "baalbek", "beirut", "antelias", "tripoli"}  # Add any known locations

def correct_spelling(user_input):
    words = user_input.split()
    corrected_words = []

    for word in words:
        lowercase = word.lower()
        if lowercase in SAFE_WORDS or word[0].isupper():
            corrected_words.append(word)
        else:
            corrected_words.append(str(TextBlob(word).correct()))
    
    return " ".join(corrected_words)



from rapidfuzz import process, fuzz # Ensure fuzz is imported if not already

def get_best_faq_match(user_question):
    """Find the best FAQ match using fuzzy matching, accepting moderately strong matches."""
    faqs = load_faqs()
    questions = [faq["question"] for faq in faqs]

    # Use RapidFuzz for better FAQ matching
    # Keep the score_cutoff here to filter out very dissimilar questions initially
    match = process.extractOne(user_question, questions, scorer=fuzz.WRatio, score_cutoff=85)

    if match:
        # Unpack the results: the matched question string, the score, and its index
        matched_question_text, score, index = match

        # Optional: Add a debug print to see what was matched and the score
        print(f"DEBUG: Fuzzy Match Found: '{matched_question_text}' with score {score} for input '{user_question}'")

        # Since 'match' is not None, it means the score met the score_cutoff (e.g., 85).
        # We can now directly return the answer using the index.
        return faqs[index]["answer"]
    else:
        # Optional: Add a debug print if no match was found above the cutoff
        print(f"DEBUG: No suitable FAQ match found above cutoff 85 for input '{user_question}'.")
        return None # Return None if no match meets the minimum cutoff

# AI Response Generator
def generate_ai_response(user_question, history=None):
    """Generate AI response with FAQ matching, fallback logic, and conversation memory."""

    corrected_question = correct_spelling(user_question)

    # Handle greetings
    greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if corrected_question.lower() in greetings:
        return "Hello! 😊 How can I assist you today?"

    # Try matching from FAQ
    retrieved_answer = get_best_faq_match(corrected_question)
    if retrieved_answer:
        return retrieved_answer  # ✅ Use FAQ if matched

    # Format chat history for multi-turn context (if available)
    history_prompt = ""
    if history:
        history_prompt = "Here is the previous conversation:\n"
        for turn in history[-10:]:  # include last 10 exchanges instead of 5
            user_msg = turn.get("user", "").strip()
            bot_msg = turn.get("bot", "").strip()
            history_prompt += f"User: {user_msg}\nBot: {bot_msg}\n"

    # Map of keyword triggers to site sections
    keyword_to_section = {
        # Document-related keywords mapped to Document Request
        "document": "Document Request",
        "form": "Document Request",
        "submit": "Document Request",
        "application": "Document Request",
        "building permit": "Document Request",
        "apply for a permit": "Document Request",
        "statement request": "Document Request",
        "get a statement": "Document Request",
        "payment": "Document Request",
        "pay my fees": "Document Request",

        # Complaint related
        "complaint": "Submit a Complaint",
        "report an issue": "Submit a Complaint",
        "garbage": "Submit a Complaint",
        "waste collection": "Submit a Complaint",

        # Jobs and volunteering
        "job": "Careers and Volunteers",
        "apply for a job": "Careers and Volunteers",
        "volunteer": "Careers and Volunteers",

        # Request tracking
        "check my requests": "Check My Requests",
        "track request": "Check My Requests",
        "status of my request": "Check My Requests",

        # Tourism and mapping
        "tourism": "Tourism Information",
        "tourist": "Tourism Information",
        "idp map": "Live IDP and Immigrant Map",
        "immigrant map": "Live IDP and Immigrant Map",
        "live map": "Live IDP and Immigrant Map"
    }

    for keyword, section in keyword_to_section.items():
        if keyword in corrected_question.lower():
            return f"You can use the **{section}** section on the site to complete this request."

    # Final fallback prompt with history and context
    fallback_prompt = f"""
You are a smart and helpful municipal chatbot designed to assist with city services, locations, and general municipal information.

{history_prompt}
User: {corrected_question}

### Guidelines for your reply:
1. If it's about municipal services (e.g., permits, complaints, payments), give steps or directions.
2. If it's about locations (e.g., police stations, hospitals), suggest checking a directory or Google Maps.
3. If unclear or vague, ask for clarification.
4. If unrelated to municipal topics, kindly say you specialize in city services.
5. If relevant, suggest visiting the site for forms or services.

Respond clearly and concisely.
"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(fallback_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Google AI Error: {e}")
        return "Sorry, I couldn't find an answer. Try rephrasing or contact the municipality."


# API Route for Chatbot
@app.route("/ask_faq", methods=["POST"])
def ask_faq():
    data = request.get_json()
    user_question = data.get("question", "")
    history = data.get("history", [])
    response = generate_ai_response(user_question, history)
    return jsonify({"answer": response})

#routes for the documents 

@app.route('/submit_business_license', methods=['POST'])
def submit_business_license():
    return "Form submitted: Business License"

@app.route('/submit_fuel_station_license', methods=['POST'])
def submit_fuel_station_license():
    return "Form submitted: Fuel Station License"

@app.route('/submit_venue_betting_license', methods=['POST'])
def submit_venue_betting_license():
    return "Form submitted: Investment License"

@app.route('/submit_declaration_receipt', methods=['POST'])
def submit_declaration_receipt():
    return "Form submitted: Declaration Receipt"

@app.route('/submit_violation_settlement', methods=['POST'])
def submit_violation_settlement():
    return "Form submitted: Violation Settlement"

@app.route('/submit_mobile_profession_license', methods=['POST'])
def submit_mobile_profession_license():
    return "Form submitted: Profession License"

@app.route('/submit_ad_license', methods=['POST'])
def submit_ad_license():
    return "Form submitted: Ad License"

@app.route('/submit_building_permit', methods=['POST'])
def submit_building_permit():
    return "Form submitted: Building Permit"

@app.route('/submit_public_property_license', methods=['POST'])
def submit_public_property_license():
    return "Form submitted: Public Property License"

@app.route('/submit_property_valuation', methods=['POST'])
def submit_property_valuation():
    return "Form submitted: Property Valuation"

@app.route('/submit_building_renewal', methods=['POST'])
def submit_building_renewal():
    return "Form submitted: Building Renewal"

@app.route('/submit_municipal_land_purchase', methods=['POST'])
def submit_municipal_land_purchase():
    return "Form submitted: Land Purchase"

@app.route('/submit_housing_permit', methods=['POST'])
def submit_housing_permit():
    return "Form submitted: Housing Permit"

@app.route('/submit_sewage_connection', methods=['POST'])
def submit_sewage_connection():
    return "Form submitted: Sewage Connection"

@app.route('/submit_fees_objection', methods=['POST'])
def submit_fees_objection():
    return "Form submitted: Fees Objection"

@app.route('/submit_merge_private_road', methods=['POST'])
def submit_merge_private_road():
    return "Form submitted: Road Merge"

@app.route('/submit_add_construction', methods=['POST'])
def submit_add_construction():
    return "Form submitted: Add Construction"

@app.route('/submit_complaint_review', methods=['POST'])
def submit_complaint_review():
    return "Form submitted: Complaint Review"

from document_routes import document_bp
from employee_routes import employee_bp

app.register_blueprint(document_bp)
app.register_blueprint(employee_bp)


@app.route('/get_info_posts/<category>')
def get_info_posts(category):
    if category not in ["tourism", "municipal_info"]:
        return jsonify({"error": "Invalid category"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, description, created_at
        FROM info_posts
        WHERE category = ?
        ORDER BY created_at DESC
    """, (category,))
    posts = cursor.fetchall()
    conn.close()

    return jsonify([dict(post) for post in posts])

@app.route('/tourism')
def tourism():
    token = request.cookies.get('token')
    if not token:
        return redirect(url_for('user_auth.login'))

    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        user_municipality_id = decoded.get('municipality_id')
    except Exception:
        return redirect(url_for('user_auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM info_posts
        WHERE category = 'tourism' AND municipality_id = ?
        ORDER BY created_at DESC
    """, (user_municipality_id,))
    posts = cursor.fetchall()
    conn.close()
    return render_template("tourism.html", posts=posts)

@app.route('/tracker', methods=['GET'])
def get_user_requests():
    try:
        token = request.cookies.get('token')
        if not token:
            return jsonify({"error": "Authentication token missing"}), 403

        decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        user_id = decoded.get('user_id')
        if not user_id:
            return jsonify({"error": "User not found in token"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, business_name, status, submitted_at
            FROM category_3_license_requests
            WHERE user_id = ?
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()

        requests = [dict(row) for row in rows]
        return render_template("tracker.html")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/events")
def api_events():
    import pandas as pd
    df = pd.read_csv("event_data_lbn(1).csv")
    df = df.dropna(subset=["latitude", "longitude", "figure", "locations_name"])
    df = df[df["displacement_type"] == "Conflict"]
    data = df[["latitude", "longitude", "locations_name", "figure", "description"]].to_dict(orient="records")
    return jsonify(data)

@app.route("/api/idp-governorates")
def idp_governorates():
    import pandas as pd

    df = pd.read_csv("lbn-iom-dtm-from-api-admin-0-to-2.csv", skiprows=[0])

    # Use correct column names after inspecting them
    df["#adm+level"] = pd.to_numeric(df["#adm+level"], errors="coerce")
    df = df[(df["#adm+level"] == 1) & df["#adm1+name"].notna()]

    grouped = df.groupby("#adm1+name").agg({
        "#affected+idps": "sum",
        "#date+reported": "max",
        "#operation+status": "first"
    }).reset_index()

    coords = {
        "akkar": [34.6, 36.0],
        "north": [34.4, 35.9],
        "mount lebanon": [33.8, 35.6],
        "beirut": [33.9, 35.5],
        "south": [33.3, 35.3],
        "nabatieh": [33.4, 35.5],
        "bekaa": [33.9, 36.0],
        "baalbek": [34.3, 36.3]
    }

    results = []
    for _, row in grouped.iterrows():
        name = row["#adm1+name"]
        match = next((key for key in coords if key in name.lower()), None)
        if match:
            results.append({
                "name": name,
                "lat": coords[match][0],
                "lng": coords[match][1],
                "idps": int(row["#affected+idps"]),
                "date": row["#date+reported"],
                "status": row["#operation+status"]
            })

    print("✅ IDP Governorates Returned:", results)
    return jsonify(results)

@app.route('/terms')
def terms_and_conditions():
    """Serves the Terms and Conditions page."""
    return render_template('terms.html')

# @app.route('/council_purchases')
# def  council_purchases_view():
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM info_posts WHERE category = 'municipal_info' ORDER BY created_at DESC")
#     posts = cursor.fetchall()
#     conn.close()
#     return render_template("council-info.html", posts=posts)


if __name__ == '__main__':
    app.run(debug=True)

