from functools import wraps
from flask import abort
from flask_login import current_user, login_required as flask_login_required


login_required = flask_login_required


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @flask_login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role is None or current_user.role.name not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
