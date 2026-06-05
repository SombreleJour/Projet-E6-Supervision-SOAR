from datetime import datetime, timezone
from ..extensions import db


# Table des actifs : machines surveillees (serveurs, postes, parefeu...)
class Asset(db.Model):
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)            # identifiant unique
    name = db.Column(db.String(100), nullable=False)        # nom de la machine
    asset_type = db.Column(db.String(50), nullable=False)   # type : 'server' | 'workstation' | 'firewall'
    ip_address = db.Column(db.String(45))                   # adresse IP (45 = compatible IPv6)
    hostname = db.Column(db.String(100))                    # nom d'hote (doit matcher l'agent Wazuh)
    source_system = db.Column(db.String(50))               # d'ou vient l'actif : 'wazuh' | 'prtg' | 'manual'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Un actif peut avoir plusieurs incidents et plusieurs alertes (lazy=dynamic = requete a la demande)
    incidents = db.relationship('Incident', back_populates='asset', lazy='dynamic')
    alerts = db.relationship('Alert', back_populates='asset', lazy='dynamic')

    def __repr__(self):
        return f'<Asset {self.name} ({self.ip_address})>'
