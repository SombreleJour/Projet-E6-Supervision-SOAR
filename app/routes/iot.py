import json

from flask import Blueprint, render_template
from flask_login import login_required

from ..models.sensor_reading import Sensor, SensorReading
from ..models.setting import get_thresholds

iot_bp = Blueprint('iot', __name__)


@iot_bp.route('/iot')
@login_required
def iot():
    sensor = Sensor.query.filter_by(is_active=True).first()
    latest_reading = None
    history_json = '[]'

    if sensor:
        latest_reading = (SensorReading.query
                          .filter_by(sensor_id=sensor.id)
                          .order_by(SensorReading.recorded_at.desc())
                          .first())

        # Historique complet (toutes les mesures du capteur), ordre chronologique.
        readings = (SensorReading.query
                    .filter(SensorReading.sensor_id == sensor.id)
                    .order_by(SensorReading.recorded_at.asc())
                    .all())

        history_json = json.dumps([{
            'recorded_at': r.recorded_at.isoformat(),
            'temperature': float(r.temperature) if r.temperature is not None else None,
            'humidity':    float(r.humidity)    if r.humidity    is not None else None,
        } for r in readings])

    return render_template(
        'iot.html',
        sensor=sensor,
        latest_reading=latest_reading,
        history_json=history_json,
        thresholds=get_thresholds(),
    )
