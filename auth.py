import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app

from flask import redirect, url_for

def token_required(f):
    """ Extracts and verifies the JWT token from the request header. """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return redirect(url_for('login'))  # Redirect to login page

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user = data
        except jwt.ExpiredSignatureError:
            return redirect(url_for('login'))  # Redirect if token expired
        except jwt.InvalidTokenError:
            return redirect(url_for('login'))  # Redirect if token is invalid

        return f(*args, **kwargs)
    return decorated


def role_required(required_role):
    """ Restricts access based on user role extracted from the JWT token. """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'user') or 'role' not in request.user:
                return jsonify({"error": "Unauthorized access!"}), 403
            
            user_role = request.user['role']
            if user_role != required_role:
                return jsonify({"error": "Insufficient permissions!"}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
