import os
import json
from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template
from flask_login import login_required

from ..models.sensor_reading import Sensor, SensorReading

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

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        readings_24h = (SensorReading.query
                        .filter(SensorReading.sensor_id == sensor.id,
                                SensorReading.recorded_at >= since)
                        .order_by(SensorReading.recorded_at.asc())
                        .all())

        history_json = json.dumps([{
            'recorded_at': r.recorded_at.isoformat(),
            'temperature': float(r.temperature) if r.temperature is not None else None,
            'humidity':    float(r.humidity)    if r.humidity    is not None else None,
        } for r in readings_24h])

    thresholds = {
        'temp_max': float(os.getenv('TEMP_MAX', 35.0)),
        'temp_min': float(os.getenv('TEMP_MIN', 10.0)),
        'hum_max':  float(os.getenv('HUM_MAX',  80.0)),
        'hum_min':  float(os.getenv('HUM_MIN',  20.0)),
    }

    return render_template(
        'iot.html',
        sensor=sensor,
        latest_reading=latest_reading,
        history_json=history_json,
        thresholds=thresholds,
    )
