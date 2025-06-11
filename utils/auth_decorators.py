import jwt
from functools import wraps
from flask import request, jsonify, current_app, redirect, url_for

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            # Expecting header in format "Bearer <token>"
            parts = request.headers['Authorization'].split()
            if len(parts) == 2:
                token = parts[1]
        
        if not token:
            return redirect(url_for('auth.login'))

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user = data
        except jwt.ExpiredSignatureError:
            return redirect(url_for('auth.login'))
        except jwt.InvalidTokenError:
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'user') or 'role' not in request.user:
                return jsonify({"error": "Unauthorized access!"}), 403
            if request.user['role'] != required_role:
                return jsonify({"error": "Insufficient permissions!"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
