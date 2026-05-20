from datetime import datetime, timezone
from ..extensions import db


class Asset(db.Model):
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    asset_type = db.Column(db.String(50), nullable=False)  # 'server' | 'workstation' | 'firewall'
    ip_address = db.Column(db.String(45))
    hostname = db.Column(db.String(100))
    source_system = db.Column(db.String(50))  # 'wazuh' | 'prtg' | 'manual'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    incidents = db.relationship('Incident', back_populates='asset', lazy='dynamic')
    alerts = db.relationship('Alert', back_populates='asset', lazy='dynamic')

    def __repr__(self):
        return f'<Asset {self.name} ({self.ip_address})>'
