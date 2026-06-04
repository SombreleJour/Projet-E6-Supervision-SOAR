from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# Stockage en mémoire (par worker gunicorn) — suffisant pour un PoC mono-serveur.
# Remplacer storage_uri par "redis://localhost:6379" en production multi-worker.
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")
