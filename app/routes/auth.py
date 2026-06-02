from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user, login_required
from ..models.user import User

auth_bp = Blueprint('auth', __name__)

# Messages affichés sur le login selon la raison de la déconnexion.
_REASON_MESSAGES = {
    'timeout': ("Session expirée après 5 minutes d'inactivité. Reconnectez-vous.", 'warning'),
    'closed':  ("Session fermée. Reconnectez-vous.", 'warning'),
}


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.is_active and user.check_password(password):
            # remember=False : pas de cookie « remember-me » persistant → la session
            # tombe à la fermeture du navigateur (cookie de session non persistant).
            login_user(user, remember=False)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.dashboard'))

        flash('Identifiants incorrects ou compte désactivé.', 'danger')
    else:
        reason = request.args.get('reason')
        if reason in _REASON_MESSAGES:
            msg, category = _REASON_MESSAGES[reason]
            flash(msg, category)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    reason = request.args.get('reason')
    if reason in _REASON_MESSAGES:
        return redirect(url_for('auth.login', reason=reason))
    return redirect(url_for('auth.login'))


@auth_bp.route('/keepalive')
@login_required
def keepalive():
    """Signal d'activité réelle envoyé par le client (souris/clavier).

    Le rafraîchissement de l'horodatage d'activité est fait dans le before_request ;
    si la session a déjà expiré, before_request renvoie 401 avant d'arriver ici.
    """
    return ('', 204)
