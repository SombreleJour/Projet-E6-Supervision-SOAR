"""
Modifie le mot de passe d'un utilisateur de l'application.

Usage :
    python scripts/set_password.py [username]   # défaut : admin

Le mot de passe est saisi de façon masquée (invisible à l'écran et absent
de l'historique du shell).
"""
import sys
import os
from getpass import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

MIN_LEN = 8


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else 'admin'

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Utilisateur '{username}' introuvable.")
            sys.exit(1)

        pwd = getpass(f"Nouveau mot de passe pour '{username}' : ")
        if len(pwd) < MIN_LEN:
            print(f"Mot de passe trop court ({MIN_LEN} caractères minimum).")
            sys.exit(1)
        if getpass("Confirmer : ") != pwd:
            print("Les mots de passe ne correspondent pas.")
            sys.exit(1)

        user.password_hash = generate_password_hash(pwd)
        db.session.commit()
        print(f"Mot de passe de '{username}' mis à jour.")


if __name__ == '__main__':
    main()
