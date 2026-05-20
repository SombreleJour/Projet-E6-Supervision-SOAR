from flask import Blueprint, render_template
from flask_login import login_required

from ..models.incident import Incident, Alert
from ..models.sensor_reading import SensorReading
from ..services import prtg_service

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    nb_incidents_open = Incident.query.filter_by(status='open').count()
    nb_incidents_critical = Incident.query.filter_by(criticality='critical').count()

    latest_alerts = (Alert.query
                     .order_by(Alert.created_at.desc())
                     .limit(5)
                     .all())

    latest_readings = SensorReading.query.order_by(SensorReading.recorded_at.desc()).first()

    prtg_status = prtg_service.get_sensor_summary()

    return render_template(
        'dashboard.html',
        nb_incidents_open=nb_incidents_open,
        nb_incidents_critical=nb_incidents_critical,
        latest_alerts=latest_alerts,
        latest_readings=latest_readings,
        prtg_status=prtg_status,
    )
