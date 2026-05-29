from flask import Flask
from .config import Config
from .extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    csrf.init_app(app)

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

    return app
