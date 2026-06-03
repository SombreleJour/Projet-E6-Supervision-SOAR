import os

from ..extensions import db


class Setting(db.Model):
    """Paramètres applicatifs globaux (clé/valeur).

    Persistants en base et partagés entre tous les workers gunicorn — contrairement
    à un réglage navigateur (localStorage) ou à os.environ (par process). C'est ce
    qui permet au RPi5 de lire la même cadence que celle choisie dans l'app web.
    """
    __tablename__ = 'app_settings'

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get(key, default=None):
        row = db.session.get(Setting, key)
        return row.value if row else default

    @staticmethod
    def get_int(key, default=0):
        try:
            return int(Setting.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))
        db.session.commit()

    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'


# ── Seuils d'alerte IoT ──────────────────────────────────────────────────
# Stockés en base sous les clés threshold_*, avec repli sur les variables
# d'environnement / config (mêmes valeurs par défaut qu'auparavant).
THRESHOLD_DEFAULTS = {
    'temp_max': ('TEMP_MAX', 35.0),
    'temp_min': ('TEMP_MIN', 10.0),
    'hum_max':  ('HUM_MAX', 80.0),
    'hum_min':  ('HUM_MIN', 20.0),
}


def get_thresholds():
    """Seuils d'alerte courants (base > env > défaut), en float."""
    out = {}
    for key, (env_name, default) in THRESHOLD_DEFAULTS.items():
        stored = Setting.get(f'threshold_{key}')
        value = stored if stored is not None else os.getenv(env_name, default)
        try:
            out[key] = float(value)
        except (TypeError, ValueError):
            out[key] = float(default)
    return out
