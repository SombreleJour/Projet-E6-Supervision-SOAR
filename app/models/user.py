from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import check_password_hash
from ..extensions import db, login_manager


# Table des roles : definit les droits (admin, analyst, viewer)
class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)          # numero unique du role
    name = db.Column(db.String(50), unique=True, nullable=False)  # nom du role

    # Un role est rattache a plusieurs utilisateurs
    users = db.relationship('User', back_populates='role')

    def __repr__(self):
        return f'<Role {self.name}>'


# Table des utilisateurs. UserMixin ajoute les methodes attendues par Flask-Login.
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)                  # identifiant unique
    username = db.Column(db.String(50), unique=True, nullable=False)   # login
    email = db.Column(db.String(120), unique=True, nullable=False)     # adresse mail
    password_hash = db.Column(db.Text, nullable=False)           # mot de passe chiffre (jamais en clair)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)  # cle etrangere vers roles
    is_active = db.Column(db.Boolean, default=True)              # compte actif ou desactive
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))  # date de creation

    # Lien vers le role de l'utilisateur
    role = db.relationship('Role', back_populates='users')

    # Compare le mot de passe saisi avec le hash enregistre
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Verifie si l'utilisateur possede un role donne
    def has_role(self, role_name):
        return self.role is not None and self.role.name == role_name

    # Flask-Login a besoin de l'identifiant sous forme de texte
    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username}>'


# Fonction appelee par Flask-Login pour recharger l'utilisateur depuis son id (cookie de session)
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
