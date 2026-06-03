from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

from ..models.incident import Incident, Alert
from ..models.sensor_reading import SensorReading
from ..models.setting import Setting
from ..services import prtg_service, wazuh_service

dashboard_bp = Blueprint('dashboard', __name__)


def _integration_ttl():
    """TTL du cache des intégrations = fréquence d'actualisation choisie (en s),
    avec un plancher pour ne jamais marteler PRTG/Wazuh."""
    return max(5, Setting.get_int('refresh_interval_ms', 30000) // 1000)


@dashboard_bp.route('/')
def index():
    # Racine du site : renvoie vers le dashboard (lui-même protégé -> login si non connecté).
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    nb_incidents_open = Incident.query.filter_by(status='open').count()
    nb_incidents_critical = Incident.query.filter_by(criticality='critical').count()

    latest_alerts = Alert.query.order_by(Alert.created_at.desc()).limit(5).all()
    recent_incidents = Incident.query.order_by(Incident.created_at.desc()).limit(5).all()
    latest_readings = SensorReading.query.order_by(SensorReading.recorded_at.desc()).first()
    ttl = _integration_ttl()

    return render_template(
        'dashboard.html',
        nb_incidents_open=nb_incidents_open,
        nb_incidents_critical=nb_incidents_critical,
        latest_alerts=latest_alerts,
        recent_incidents=recent_incidents,
        latest_readings=latest_readings,
        prtg=prtg_service.get_prtg_overview(cache_ttl=ttl),
        wazuh=wazuh_service.get_wazuh_overview(cache_ttl=ttl),
    )


@dashboard_bp.route('/dashboard/prtg-section')
@login_required
def prtg_section():
    """Fragment HTML de la section PRTG (polling côté client)."""
    return render_template('partials/_prtg_section.html',
                           prtg=prtg_service.get_prtg_overview(cache_ttl=_integration_ttl()))


@dashboard_bp.route('/dashboard/wazuh-section')
@login_required
def wazuh_section():
    """Fragment HTML de la section Wazuh (polling côté client)."""
    return render_template('partials/_wazuh_section.html',
                           wazuh=wazuh_service.get_wazuh_overview(cache_ttl=_integration_ttl()))
