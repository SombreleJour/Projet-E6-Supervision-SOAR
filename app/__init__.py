from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db, login_manager, csrf, limiter


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Derrière le reverse proxy nginx (terminaison TLS) : interpréter les en-têtes
    # X-Forwarded-* (schéma HTTPS, hôte, IP client réelle) pour CSRF/cookies/redirections.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    csrf.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        from .models import user, incident, asset, sensor_reading  # noqa: F401

        from .routes.auth import auth_bp
        from .routes.dashboard import dashboard_bp
        from .routes.incidents import incidents_bp
        from .routes.security import security_bp
        from .routes.iot import iot_bp
        from .routes.admin import admin_bp
        from .routes.api import api_bp
        from .routes.soar import soar_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(incidents_bp, url_prefix='/incidents')
        app.register_blueprint(security_bp)
        app.register_blueprint(iot_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(api_bp, url_prefix='/api')
        app.register_blueprint(soar_bp, url_prefix='/api/soar')

        csrf.exempt(api_bp)
        csrf.exempt(soar_bp)

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    # ── Déconnexion automatique après inactivité (autorité serveur) ──────
    # Le polling en arrière-plan (Dashboard/IoT) NE rafraîchit PAS l'horodatage
    # d'activité : seules les vraies actions (navigation, keepalive) le font.
    @app.before_request
    def _enforce_idle_timeout():
        import time
        from flask import request, session, redirect, url_for, jsonify
        from flask_login import current_user, logout_user

        if request.endpoint == 'static' or not current_user.is_authenticated:
            return

        now = int(time.time())
        idle = app.config.get('IDLE_TIMEOUT_SECONDS', 300)
        last = session.get('last_activity')

        if last is not None and now - last > idle:
            logout_user()
            session.clear()
            wants_json = (request.path.startswith('/api/')
                          or request.headers.get('X-Requested-With') == 'XMLHttpRequest')
            if wants_json:
                return jsonify({'error': 'session_expired'}), 401
            return redirect(url_for('auth.login', reason='timeout'))

        POLLING_ENDPOINTS = {'api.dashboard_stats', 'api.iot_readings_history',
                             'dashboard.prtg_section', 'dashboard.wazuh_section'}
        if request.endpoint not in POLLING_ENDPOINTS:
            session['last_activity'] = now

    # Cache-busting des fichiers statiques : nginx les sert avec un max-age long
    # (7 jours), donc on suffixe l'URL d'un ?v=<mtime> pour forcer le navigateur à
    # retélécharger un asset (CSS/JS) dès qu'il change.
    @app.context_processor
    def inject_asset_url():
        import os
        from flask import url_for

        def asset_url(filename):
            try:
                version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
            except OSError:
                version = 0
            return url_for('static', filename=filename, v=version)

        return {'asset_url': asset_url}

    # Intervalle de rafraîchissement global exposé à tous les templates :
    # base.html (polling JS) et la page Paramètres (option pré-sélectionnée).
    @app.context_processor
    def inject_refresh_interval():
        from .models.setting import Setting
        try:
            ms = Setting.get_int('refresh_interval_ms', 30000)
        except Exception:
            db.session.rollback()
            ms = 30000
        return {'refresh_interval_ms': ms,
                'idle_timeout_seconds': app.config.get('IDLE_TIMEOUT_SECONDS', 300)}


    # ── En-têtes HTTP de sécurité ──────────────────────────────────────────
    # Appliqués à chaque réponse pour renforcer la posture sécurité côté client.
    @app.after_request
    def _set_security_headers(response):
        # Empêche l'embarquement dans une iframe (protection clickjacking)
        response.headers['X-Frame-Options'] = 'DENY'
        # Interdit au navigateur de deviner le MIME type (protection MIME sniffing)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Filtre XSS pour les anciens navigateurs
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Contrôle les infos envoyées dans l'en-tête Referer vers des domaines tiers
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Politique de sources : restreint les origines autorisées pour scripts/styles/polices
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
            "font-src 'self' cdn.jsdelivr.net fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response

    # ── Trop de requêtes (rate limiting) ───────────────────────────────────
    @app.errorhandler(429)
    def too_many_requests(e):
        from flask import render_template
        return render_template('errors/429.html'), 429

    return app
