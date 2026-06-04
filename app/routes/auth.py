from urllib.parse import urlsplit

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user, login_required

from ..models.user import User
from ..utils.logger import logger
from ..extensions import limiter

auth_bp = Blueprint('auth', __name__)

_REASON_MESSAGES = {
    'timeout': ("Session expirée après 5 minutes d'inactivité. Reconnectez-vous.", 'warning'),
    'closed':  ("Session fermée. Reconnectez-vous.", 'warning'),
}


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip = request.remote_addr

        user = User.query.filter_by(username=username).first()

        if user and user.is_active and user.check_password(password):
            login_user(user, remember=False)
            logger.info("AUTH login_success username=%s role=%s ip=%s", username, user.role.name if user.role else '?', ip)
            next_page = request.args.get('next')
            # Protection open redirect : on rejette toute URL pointant vers un hôte externe.
            if next_page and urlsplit(next_page).netloc:
                next_page = None
            return redirect(next_page or url_for('dashboard.dashboard'))

        logger.warning("AUTH login_failed username=%s ip=%s", username, ip)
        flash('Identifiants incorrects ou compte désactivé.', 'danger')
    else:
        reason = request.args.get('reason')
        if reason in _REASON_MESSAGES:
            msg, category = _REASON_MESSAGES[reason]
            flash(msg, category)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        logger.info("AUTH logout username=%s ip=%s", current_user.username, request.remote_addr)
    logout_user()
    reason = request.args.get('reason')
    if reason in _REASON_MESSAGES:
        return redirect(url_for('auth.login', reason=reason))
    return redirect(url_for('auth.login'))


@auth_bp.route('/keepalive')
@login_required
def keepalive():
    return ('', 204)
