import os

from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models.user import User, Role
from ..utils.decorators import role_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@role_required('admin')
def settings():
    users = User.query.order_by(User.username).all()
    roles = Role.query.all()

    thresholds = {
        'temp_max': os.getenv('TEMP_MAX', '35.0'),
        'temp_min': os.getenv('TEMP_MIN', '10.0'),
        'hum_max': os.getenv('HUM_MAX', '80.0'),
        'hum_min': os.getenv('HUM_MIN', '20.0'),
    }

    import sys
    import flask
    system_info = {
        'flask_version': flask.__version__,
        'python_version': sys.version.split()[0],
    }

    try:
        db.session.execute(db.text('SELECT 1'))
        system_info['db_status'] = 'Connecté'
    except Exception:
        system_info['db_status'] = 'Erreur de connexion'

    return render_template(
        'admin/settings.html',
        users=users,
        roles=roles,
        thresholds=thresholds,
        system_info=system_info,
    )


@admin_bp.route('/users/create', methods=['POST'])
@role_required('admin')
def create_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role_name = request.form.get('role', 'operator')

    if not username or not email or not password:
        flash('Tous les champs sont obligatoires.', 'danger')
        return redirect(url_for('admin.settings'))

    if User.query.filter_by(username=username).first():
        flash(f"L'utilisateur '{username}' existe déjà.", 'warning')
        return redirect(url_for('admin.settings'))

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        flash(f"Rôle '{role_name}' introuvable.", 'danger')
        return redirect(url_for('admin.settings'))

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role_id=role.id,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    flash(f"Utilisateur '{username}' créé avec le rôle {role_name}.", 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/users/<int:id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(id):
    user = db.get_or_404(User, id)
    user.is_active = not user.is_active
    db.session.commit()
    state = 'activé' if user.is_active else 'désactivé'
    flash(f"Compte '{user.username}' {state}.", 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/thresholds', methods=['POST'])
@role_required('admin')
def update_thresholds():
    fields = ['TEMP_MAX', 'TEMP_MIN', 'HUM_MAX', 'HUM_MIN']
    for field in fields:
        value = request.form.get(field.lower())
        if value is not None:
            try:
                float(value)
                os.environ[field] = value
            except ValueError:
                flash(f'Valeur invalide pour {field}.', 'danger')
                return redirect(url_for('admin.settings'))

    flash('Seuils mis à jour pour cette session.', 'success')
    return redirect(url_for('admin.settings'))
