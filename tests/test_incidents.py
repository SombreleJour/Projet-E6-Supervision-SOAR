"""
Tests CRUD incidents et logique SOAR (upsert, escalade).
Lancer : pytest tests/test_incidents.py -v
"""
import pytest
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.incident import Incident
from app.models.asset import Asset
from app.services import soar_service
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    _app = create_app()
    _app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret',
        'SOAR_THRESHOLD': 'high',
    })

    with _app.app_context():
        db.create_all()

        db.session.add_all([Role(name='admin'), Role(name='analyst'), Role(name='operator')])
        db.session.commit()

        admin_role = Role.query.filter_by(name='admin').first()
        user = User(
            username='admin',
            email='admin@test.local',
            password_hash=generate_password_hash('Admin1234!'),
            role_id=admin_role.id,
            is_active=True,
        )
        db.session.add(user)

        asset = Asset(
            name='SRV-TEST',
            asset_type='server',
            ip_address='192.168.1.100',
            hostname='srv-test',
            source_system='manual',
        )
        db.session.add(asset)
        db.session.commit()

        yield _app

        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post('/login', data={'username': 'admin', 'password': 'Admin1234!'})
    return client


def test_list_incidents(auth_client):
    res = auth_client.get('/incidents/')
    assert res.status_code == 200


def test_create_incident(app, auth_client):
    res = auth_client.post('/incidents/new', data={
        'title': 'Test incident',
        'description': 'Description de test',
        'category': 'security',
        'criticality': 'high',
        'source': 'manual',
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        incident = Incident.query.filter_by(title='Test incident').first()
        assert incident is not None
        assert incident.criticality == 'high'


def test_filter_by_status(auth_client, app):
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        inc = Incident(title='Ouvert', category='security',
                       criticality='low', status='open', source='manual',
                       created_by=admin.id)
        inc2 = Incident(title='Fermé', category='security',
                        criticality='low', status='closed', source='manual',
                        created_by=admin.id)
        db.session.add_all([inc, inc2])
        db.session.commit()

    res = auth_client.get('/incidents/?status=open')
    assert res.status_code == 200
    assert b'Ouvert' in res.data
    assert b'Ferm' not in res.data


def test_add_comment(app, auth_client):
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        inc = Incident(title='Pour commentaire', category='network',
                       criticality='medium', status='open', source='manual',
                       created_by=admin.id)
        db.session.add(inc)
        db.session.commit()
        inc_id = inc.id

    res = auth_client.post(f'/incidents/{inc_id}/comment',
                           data={'comment': 'Ceci est un test'},
                           follow_redirects=True)
    assert res.status_code == 200
    assert b'Ceci est un test' in res.data


def test_soar_upsert_new(app):
    with app.app_context():
        alert = {
            'external_id': 'wazuh-alert-001',
            'title': 'Tentative brute force',
            'description': 'Détection brute force SSH',
            'source': '192.168.99.99',
            'criticality': 'medium',
            'category': 'security',
            'rule_id': '5710',
        }
        result = soar_service.process_wazuh_alert(alert)
        assert result['action'] == 'created'
        assert result['incident_id'] is not None
        assert result['triggered_soar'] is False  # medium < high threshold


def test_soar_upsert_existing(app):
    with app.app_context():
        alert = {
            'external_id': 'wazuh-alert-002',
            'title': 'Incident existant',
            'description': 'Première détection',
            'source': '192.168.99.98',
            'criticality': 'low',
            'category': 'security',
            'rule_id': '1002',
        }
        r1 = soar_service.process_wazuh_alert(alert)
        assert r1['action'] == 'created'

        # Deuxième appel avec même external_id → update
        alert['description'] = 'Détection enrichie'
        r2 = soar_service.process_wazuh_alert(alert)
        assert r2['action'] in ('updated', 'skipped')
        assert r2['incident_id'] == r1['incident_id']


def test_soar_escalation(app):
    with app.app_context():
        alert = {
            'external_id': 'wazuh-alert-003',
            'title': 'Escalade criticité',
            'description': 'Détection initiale',
            'source': '192.168.99.97',
            'criticality': 'low',
            'category': 'security',
            'rule_id': '1003',
        }
        r1 = soar_service.process_wazuh_alert(alert)
        inc_id = r1['incident_id']

        incident = db.session.get(Incident, inc_id)
        assert incident.criticality == 'low'

        # Même alert avec criticité élevée → escalade
        alert['criticality'] = 'high'
        alert['description'] = 'Escalade confirmée'
        soar_service.process_wazuh_alert(alert)

        db.session.refresh(incident)
        assert incident.criticality == 'high'
