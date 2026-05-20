from flask import Flask
from .config import Config
from .extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

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

    return app
