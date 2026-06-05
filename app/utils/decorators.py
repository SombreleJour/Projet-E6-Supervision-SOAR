from functools import wraps
from flask import abort
from flask_login import current_user, login_required as flask_login_required


# Raccourci : exige juste qu'un utilisateur soit connecte
login_required = flask_login_required


# Decorateur maison : autorise l'acces seulement a certains roles
# Exemple d'utilisation : @role_required('admin', 'analyst')
def role_required(*roles):
    def decorator(f):
        @wraps(f)                  # garde le nom/docstring de la fonction d'origine
        @flask_login_required      # d'abord verifier que l'utilisateur est connecte
        def decorated_function(*args, **kwargs):
            # Pas connecte -> erreur 401 (non authentifie)
            if not current_user.is_authenticated:
                abort(401)
            # Connecte mais role non autorise -> erreur 403 (interdit)
            if current_user.role is None or current_user.role.name not in roles:
                abort(403)
            # Tout est bon : on execute la vraie fonction (la route)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
