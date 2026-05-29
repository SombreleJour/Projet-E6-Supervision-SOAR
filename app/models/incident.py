from datetime import datetime, timezone
from ..extensions import db


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True)
    source = db.Column(db.String(30), nullable=False)
    rule_name = db.Column(db.String(200))
    severity = db.Column(db.String(20))
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    asset = db.relationship('Asset', back_populates='alerts')
    incident = db.relationship('Incident', back_populates='alerts')

    def __repr__(self):
        return f'<Alert {self.external_id} [{self.severity}]>'


class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)
    criticality = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='open')
    source = db.Column(db.String(30), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    asset = db.relationship('Asset', back_populates='incidents')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_incidents')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_incidents')
    comments = db.relationship('IncidentComment', back_populates='incident',
                               cascade='all, delete-orphan',
                               order_by='IncidentComment.created_at')
    alerts = db.relationship('Alert', back_populates='incident')

    def __repr__(self):
        return f'<Incident {self.id} [{self.criticality}] {self.title[:40]}>'


class IncidentComment(db.Model):
    __tablename__ = 'incident_comments'

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    incident = db.relationship('Incident', back_populates='comments')
    author = db.relationship('User', backref='comments')

    def __repr__(self):
        return f'<IncidentComment incident={self.incident_id} user={self.user_id}>'
