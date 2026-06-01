from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import current_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models.user import User, Role
from ..utils.decorators import login_required, role_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@login_required
def settings():
    # La liste/gestion des utilisateurs n'est chargée que pour les admins.
    users = roles = None
    if current_user.has_role('admin'):
        users = User.query.order_by(User.username).all()
        roles = Role.query.all()

    return render_template(
        'admin/settings.html',
        users=users,
        roles=roles,
    )


# ── Self-service (tout utilisateur connecté) ─────────────────────────────

@admin_bp.route('/account/password', methods=['POST'])
@login_required
def change_password():
    current = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if not current_user.check_password(current):
        flash('Mot de passe actuel incorrect.', 'danger')
        return redirect(url_for('admin.settings'))
    if len(new) < 8:
        flash('Le nouveau mot de passe doit contenir au moins 8 caractères.', 'danger')
        return redirect(url_for('admin.settings'))
    if new != confirm:
        flash('La confirmation ne correspond pas au nouveau mot de passe.', 'danger')
        return redirect(url_for('admin.settings'))

    current_user.password_hash = generate_password_hash(new)
    db.session.commit()
    flash('Mot de passe mis à jour.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/account/profile', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()

    if not username or not email:
        flash("L'identifiant et l'email sont obligatoires.", 'danger')
        return redirect(url_for('admin.settings'))

    clash = User.query.filter(User.username == username, User.id != current_user.id).first()
    if clash:
        flash(f"L'identifiant '{username}' est déjà utilisé.", 'warning')
        return redirect(url_for('admin.settings'))
    clash = User.query.filter(User.email == email, User.id != current_user.id).first()
    if clash:
        flash(f"L'email '{email}' est déjà utilisé.", 'warning')
        return redirect(url_for('admin.settings'))

    current_user.username = username
    current_user.email = email
    db.session.commit()
    flash('Profil mis à jour.', 'success')
    return redirect(url_for('admin.settings'))


# ── Gestion des utilisateurs (admin uniquement) ──────────────────────────

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

    db.session.add(User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role_id=role.id,
        is_active=True,
    ))
    db.session.commit()
    flash(f"Utilisateur '{username}' créé ({role_name}).", 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/users/<int:id>/edit', methods=['POST'])
@role_required('admin')
def edit_user(id):
    user = db.get_or_404(User, id)
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    role_name = request.form.get('role', user.role.name if user.role else '')

    if not username or not email:
        flash("L'identifiant et l'email sont obligatoires.", 'danger')
        return redirect(url_for('admin.settings'))

    clash = User.query.filter(User.username == username, User.id != user.id).first()
    if clash:
        flash(f"L'identifiant '{username}' est déjà utilisé.", 'warning')
        return redirect(url_for('admin.settings'))
    clash = User.query.filter(User.email == email, User.id != user.id).first()
    if clash:
        flash(f"L'email '{email}' est déjà utilisé.", 'warning')
        return redirect(url_for('admin.settings'))

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        flash(f"Rôle '{role_name}' introuvable.", 'danger')
        return redirect(url_for('admin.settings'))

    user.username = username
    user.email = email
    user.role_id = role.id
    db.session.commit()
    flash(f"Utilisateur '{username}' mis à jour.", 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/users/<int:id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(id):
    user = db.get_or_404(User, id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f"Compte '{user.username}' {'activé' if user.is_active else 'désactivé'}.", 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/users/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_user(id):
    user = db.get_or_404(User, id)
    if user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'warning')
        return redirect(url_for('admin.settings'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"Utilisateur '{username}' supprimé définitivement.", 'success')
    return redirect(url_for('admin.settings'))
