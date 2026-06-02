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
