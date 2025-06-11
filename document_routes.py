from flask import Blueprint, request, jsonify, current_app
import os
import jwt
from werkzeug.utils import secure_filename

from document_models import insert_category_3_license

document_bp = Blueprint('document_bp', __name__)

@document_bp.route('/submit_category_3_license', methods=['POST'])
def submit_category_3_license():
    try:
        # 🔐 Get and decode JWT token from cookie
        token = request.cookies.get('token')
        if not token:
            return jsonify({"error": "Authentication token missing"}), 403

        try:
            decoded = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = decoded.get('user_id')
            municipality_id = decoded.get('municipality_id')
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 403
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 403

        # 🧾 Get form and file data
        data = request.form
        files = request.files

        result = insert_category_3_license(
            user_id=user_id,
            municipality_id=municipality_id,
            business_name=data.get("business-name"),
            owner_name=data.get("owner-name"),
            phone_number=data.get("phone-number"),
            address=data.get("address"),
            business_activity=data.get("business-activity"),
            payment_method=data.get("payment-method"),
            card_number=data.get("card-number"),
            expiry_date=data.get("expiry-date"),
            cvc=data.get("cvc"),
            ownership_proof=files.get("ownership-proof"),
            safety_clearance=files.get("safety-clearance"),
            municipal_approval=files.get("municipal-approval")
        )

        return jsonify({"message": "تم إرسال الطلب بنجاح", "data": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

