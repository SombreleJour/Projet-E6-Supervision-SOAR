"""
Initialisation de la base de données supervision_db.
Lance depuis le dossier racine du projet :
    python scripts/seed.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.sensor_reading import Sensor
from app.models.asset import Asset
from werkzeug.security import generate_password_hash


def seed():
    app = create_app()
    with app.app_context():
        print("Création des tables…")
        db.create_all()

        # ── Rôles ──────────────────────────────────────────────────
        roles_created = 0
        for role_name in ('admin', 'analyst', 'operator'):
            if not Role.query.filter_by(name=role_name).first():
                db.session.add(Role(name=role_name))
                roles_created += 1
        db.session.commit()
        print(f"Rôles créés : {roles_created}")

        # ── Utilisateur admin par défaut ────────────────────────────
        admin_role = Role.query.filter_by(name='admin').first()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                email='admin@siem.local',
                password_hash=generate_password_hash('Admin1234!'),
                role_id=admin_role.id,
                is_active=True,
            ))
            db.session.commit()
            print("Utilisateur admin créé (mot de passe : Admin1234!)")
        else:
            print("Utilisateur admin déjà existant — ignoré")

        # ── Capteur DHT22 par défaut ────────────────────────────────
        if not Sensor.query.filter_by(raspberry_id='rpi5-iot').first():
            db.session.add(Sensor(
                name='DHT22-RPi5',
                sensor_type='DHT22',
                location='Salle serveur',
                raspberry_id='rpi5-iot',
                is_active=True,
            ))
            db.session.commit()
            print("Capteur DHT22-RPi5 créé")
        else:
            print("Capteur DHT22-RPi5 déjà existant — ignoré")

        # ── Assets des VMs du lab ───────────────────────────────────
        lab_assets = [
            ('SRV-AD-PRTG',  '172.16.1.5',  'server',      'wazuh'),
            ('SRV-WAZUH',    '172.16.1.10', 'server',      'wazuh'),
            ('PC-TEST-WIN',  '172.16.5.5',  'workstation', 'manual'),
            ('PC-TEST-LIN',  '172.16.5.10', 'workstation', 'manual'),
        ]
        assets_created = 0
        for name, ip, asset_type, source in lab_assets:
            if not Asset.query.filter_by(name=name).first():
                db.session.add(Asset(
                    name=name,
                    asset_type=asset_type,
                    ip_address=ip,
                    hostname=name.lower(),
                    source_system=source,
                ))
                assets_created += 1
        db.session.commit()
        print(f"Assets créés : {assets_created}")

        # ── Résumé ──────────────────────────────────────────────────
        print("\n=== Base de données initialisée ===")
        print(f"  Rôles   : {Role.query.count()}")
        print(f"  Users   : {User.query.count()}")
        print(f"  Capteurs: {Sensor.query.count()}")
        print(f"  Assets  : {Asset.query.count()}")


if __name__ == '__main__':
    seed()
