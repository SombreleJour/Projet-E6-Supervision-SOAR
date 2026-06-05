from datetime import datetime, timezone
from ..extensions import db


# Table des alertes : evenements bruts remontes par Wazuh ou PRTG
class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)              # identifiant unique
    external_id = db.Column(db.String(100), unique=True)      # id d'origine (cote Wazuh) pour eviter les doublons
    source = db.Column(db.String(30), nullable=False)         # outil source : 'wazuh', 'prtg'...
    rule_name = db.Column(db.String(200))                     # nom/regle qui a declenche l'alerte
    severity = db.Column(db.String(20))                      # gravite : low / medium / high / critical
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))      # machine concernee
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'))  # incident rattache (si cree)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Liens vers la machine et l'incident associes
    asset = db.relationship('Asset', back_populates='alerts')
    incident = db.relationship('Incident', back_populates='alerts')

    def __repr__(self):
        return f'<Alert {self.external_id} [{self.severity}]>'


# Table des incidents : un probleme de securite a traiter (cree a partir d'une alerte)
class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)              # identifiant unique
    external_id = db.Column(db.String(100), unique=True)      # id Wazuh d'origine (anti-doublon)
    title = db.Column(db.String(200), nullable=False)        # titre court de l'incident
    description = db.Column(db.Text)                         # details (on y ajoute les actions SOAR)
    category = db.Column(db.String(50), nullable=False)      # categorie : 'security', 'network'...
    criticality = db.Column(db.String(20), nullable=False)   # criticite : low / medium / high / critical
    status = db.Column(db.String(30), nullable=False, default='open')  # etat : open, in_progress, closed
    source = db.Column(db.String(30), nullable=False)        # origine : 'wazuh', 'manual'...
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))       # machine touchee
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))      # qui a cree l'incident
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))     # a qui il est attribue
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # updated_at se met a jour tout seul a chaque modification (onupdate)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relations vers les autres tables
    asset = db.relationship('Asset', back_populates='incidents')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_incidents')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_incidents')
    # Les commentaires sont supprimes en cascade si l'incident est supprime
    comments = db.relationship('IncidentComment', back_populates='incident',
                               cascade='all, delete-orphan',
                               order_by='IncidentComment.created_at')
    alerts = db.relationship('Alert', back_populates='incident')

    def __repr__(self):
        return f'<Incident {self.id} [{self.criticality}] {self.title[:40]}>'


# Table des commentaires laisses par les analystes sur un incident
class IncidentComment(db.Model):
    __tablename__ = 'incident_comments'

    id = db.Column(db.Integer, primary_key=True)             # identifiant unique
    # ondelete=CASCADE : si l'incident part, ses commentaires partent aussi
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # auteur du commentaire
    comment = db.Column(db.Text, nullable=False)            # texte du commentaire
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Liens vers l'incident et l'auteur
    incident = db.relationship('Incident', back_populates='comments')
    author = db.relationship('User', backref='comments')

    def __repr__(self):
        return f'<IncidentComment incident={self.incident_id} user={self.user_id}>'
