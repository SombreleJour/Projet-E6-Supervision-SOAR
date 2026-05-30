"""
Initialisation de la base de données supervision_db.
Lance depuis le dossier racine du projet :
    python scripts/seed.py
"""
import sys
import os
import math
import random
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.sensor_reading import Sensor, SensorReading
from app.models.asset import Asset
from app.models.incident import Incident, IncidentComment, Alert
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
        # raspberry_id doit correspondre au sensor_id envoyé par dht22_collector.py
        if not Sensor.query.filter_by(raspberry_id='dht22-rpi5').first():
            db.session.add(Sensor(
                name='DHT22-RPi5',
                sensor_type='DHT22',
                location='Salle serveur',
                raspberry_id='dht22-rpi5',
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

        # ── Données de démonstration (dashboard / soutenance) ───────
        seed_demo_data()

        # ── Résumé ──────────────────────────────────────────────────
        print("\n=== Base de données initialisée ===")
        print(f"  Rôles   : {Role.query.count()}")
        print(f"  Users   : {User.query.count()}")
        print(f"  Capteurs: {Sensor.query.count()}")
        print(f"  Assets  : {Asset.query.count()}")
        print(f"  Incidents: {Incident.query.count()}")
        print(f"  Alertes : {Alert.query.count()}")
        print(f"  Mesures : {SensorReading.query.count()}")


def seed_demo_data():
    """Jeu de données fictif (RGPD-safe) pour peupler le dashboard.

    Idempotent : ne s'exécute que si aucune alerte n'existe encore.
    """
    if Alert.query.count() > 0:
        print("Données de démo déjà présentes — ignorées")
        return

    admin = User.query.filter_by(username='admin').first()
    now = datetime.now(timezone.utc)

    def asset_id(name):
        a = Asset.query.filter_by(name=name).first()
        return a.id if a else None

    # ── Incidents (criticités / statuts / catégories variés) ────────
    incidents_spec = [
        # (external_id, titre, catégorie, criticité, statut, source, asset, h_ago, assigné)
        ('INC-DEMO-001', 'Force brute SSH détectée', 'security', 'critical', 'open',
         'wazuh', 'PC-TEST-LIN', 2, True),
        ('INC-DEMO-002', 'Signature malware (EICAR) détectée', 'security', 'high', 'in_progress',
         'wazuh', 'PC-TEST-WIN', 6, True),
        ('INC-DEMO-003', 'Charge CPU élevée (> 90%) prolongée', 'performance', 'medium', 'open',
         'prtg', 'SRV-AD-PRTG', 20, False),
        ('INC-DEMO-004', 'Latence réseau anormale vers la passerelle', 'network', 'low', 'closed',
         'prtg', 'SRV-WAZUH', 52, False),
    ]
    incidents = {}
    for ext_id, title, cat, crit, status, source, asset_name, h_ago, assigned in incidents_spec:
        created = now - timedelta(hours=h_ago)
        inc = Incident(
            external_id=ext_id, title=title, category=cat, criticality=crit,
            status=status, source=source, asset_id=asset_id(asset_name),
            description=f"[{source.upper()}] {title} sur {asset_name}. Donnée fictive de démonstration.",
            created_by=admin.id if admin else None,
            assigned_to=admin.id if (assigned and admin) else None,
            created_at=created, updated_at=created,
        )
        db.session.add(inc)
        incidents[ext_id] = inc
    db.session.commit()

    # Un commentaire sur l'incident en cours de traitement
    if admin:
        db.session.add(IncidentComment(
            incident_id=incidents['INC-DEMO-002'].id, user_id=admin.id,
            comment="Machine mise en quarantaine, analyse de l'échantillon en cours.",
            created_at=now - timedelta(hours=5),
        ))

    # ── Alertes (réparties dans le temps pour l'évolution temporelle) ─
    alerts_spec = [
        # (external_id, source, règle, sévérité, asset, min_ago, incident_lié)
        ('WZ-5001', 'wazuh', 'sshd: brute force (multiple auth failures)', 'critical', 'PC-TEST-LIN', 118, 'INC-DEMO-001'),
        ('WZ-5002', 'wazuh', 'Malware signature match (EICAR-Test-File)',  'high',     'PC-TEST-WIN', 355, 'INC-DEMO-002'),
        ('PRTG-3001', 'prtg', 'CPU Load > 90% (5 min)',                    'medium',   'SRV-AD-PRTG', 1180, 'INC-DEMO-003'),
        ('PRTG-3002', 'prtg', 'Ping latency > 200ms',                      'low',      'SRV-WAZUH',   3110, 'INC-DEMO-004'),
        ('WZ-5003', 'wazuh', 'File integrity: /etc/passwd modifié',        'high',     'SRV-WAZUH',   45,   None),
        ('WZ-5004', 'wazuh', 'Élévation de privilèges (sudo to root)',     'medium',   'PC-TEST-LIN', 30,   None),
        ('WZ-5005', 'wazuh', 'Connexion réussie hors horaires',            'low',      'PC-TEST-WIN', 12,   None),
        ('PRTG-3003', 'prtg', 'Interface réseau WAN down',                 'high',     'SRV-AD-PRTG', 8,    None),
    ]
    for ext_id, source, rule, sev, asset_name, min_ago, inc_ref in alerts_spec:
        db.session.add(Alert(
            external_id=ext_id, source=source, rule_name=rule, severity=sev,
            asset_id=asset_id(asset_name),
            incident_id=incidents[inc_ref].id if inc_ref else None,
            created_at=now - timedelta(minutes=min_ago),
        ))
    db.session.commit()

    # ── Historique IoT : 24 h de mesures (1 point / 30 min) ─────────
    sensor = Sensor.query.filter_by(is_active=True).first()
    if sensor and sensor.readings.count() == 0:
        points = 48
        for i in range(points):
            ts = now - timedelta(minutes=30 * (points - i))
            # Cycle jour/nuit léger + bruit, autour de 23°C / 47%
            phase = 2 * math.pi * i / points
            temp = round(23.0 + 2.5 * math.sin(phase) + random.uniform(-0.4, 0.4), 1)
            hum = round(47.0 + 6.0 * math.cos(phase) + random.uniform(-1.0, 1.0), 1)
            db.session.add(SensorReading(
                sensor_id=sensor.id, temperature=temp, humidity=hum,
                checksum_ok=True, recorded_at=ts,
            ))
        db.session.commit()

    print("Données de démo créées : 4 incidents, 8 alertes, 48 mesures IoT")


if __name__ == '__main__':
    seed()
