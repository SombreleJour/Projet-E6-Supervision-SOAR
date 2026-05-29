"""
Tests d'authentification et de contrôle d'accès.
Lancer : pytest tests/test_auth.py -v
"""
import pytest
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    _app = create_app()
    _app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret',
    })

    with _app.app_context():
        db.create_all()

        admin_role    = Role(name='admin')
        analyst_role  = Role(name='analyst')
        operator_role = Role(name='operator')
        db.session.add_all([admin_role, analyst_role, operator_role])
        db.session.commit()

        admin_user = User(
            username='admin',
            email='admin@test.local',
            password_hash=generate_password_hash('Admin1234!'),
            role_id=admin_role.id,
            is_active=True,
        )
        inactive_user = User(
            username='inactive',
            email='inactive@test.local',
            password_hash=generate_password_hash('Admin1234!'),
            role_id=operator_role.id,
            is_active=False,
        )
        operator_user = User(
            username='operator',
            email='operator@test.local',
            password_hash=generate_password_hash('Admin1234!'),
            role_id=operator_role.id,
            is_active=True,
        )
        db.session.add_all([admin_user, inactive_user, operator_user])
        db.session.commit()

        yield _app

        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password},
                       follow_redirects=True)


def test_login_success(client):
    res = login(client, 'admin', 'Admin1234!')
    assert res.status_code == 200
    assert b'Dashboard' in res.data


def test_login_wrong_password(client):
    res = login(client, 'admin', 'mauvais_mdp')
    assert res.status_code == 200
    assert b'Identifiants incorrects' in res.data


def test_login_inactive_user(client):
    res = login(client, 'inactive', 'Admin1234!')
    assert res.status_code == 200
    assert b'Identifiants incorrects' in res.data


def test_logout(client):
    login(client, 'admin', 'Admin1234!')
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b'login' in res.request.url.lower() or b'connexion' in res.data.lower()


def test_dashboard_requires_auth(client):
    res = client.get('/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/login' in res.headers['Location']


def test_admin_requires_role(client):
    login(client, 'operator', 'Admin1234!')
    res = client.get('/admin/', follow_redirects=False)
    assert res.status_code == 403
