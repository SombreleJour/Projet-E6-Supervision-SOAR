import os
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from ..extensions import db
from ..models.sensor_reading import Sensor, SensorReading
from ..models.incident import Alert, Incident
from ..services import prtg_service

api_bp = Blueprint('api', __name__)


def _verify_bearer():
    """Vérifie le Bearer token IoT depuis l'en-tête Authorization."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    token = auth[7:]
    return token == os.getenv('IOT_API_TOKEN', '')


@api_bp.route('/iot/readings', methods=['POST'])
def iot_readings():
    if not _verify_bearer():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    temperature = data.get('temperature')
    humidity = data.get('humidity')
    sensor_ref = data.get('sensor_id', 'dht22-rpi5')

    if temperature is None or humidity is None:
        return jsonify({'error': 'Missing temperature or humidity'}), 422

    try:
        temperature = float(temperature)
        humidity = float(humidity)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid numeric values'}), 422

    if not (-10 <= temperature <= 60):
        return jsonify({'error': 'Temperature out of range [-10, 60]'}), 422
    if not (0 <= humidity <= 100):
        return jsonify({'error': 'Humidity out of range [0, 100]'}), 422

    sensor = Sensor.query.filter_by(raspberry_id=sensor_ref, is_active=True).first()
    if not sensor:
        sensor = Sensor.query.filter_by(is_active=True).first()
    if not sensor:
        return jsonify({'error': 'No active sensor found'}), 404

    reading = SensorReading(
        sensor_id=sensor.id,
        temperature=temperature,
        humidity=humidity,
        checksum_ok=True,
        recorded_at=datetime.now(timezone.utc),
    )
    db.session.add(reading)
    db.session.commit()

    return jsonify({'status': 'ok', 'id': reading.id}), 201


@api_bp.route('/metrics', methods=['GET'])
@login_required
def metrics():
    sensors = prtg_service.get_sensors()
    return jsonify({
        'sensors': sensors,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


@api_bp.route('/alerts', methods=['GET'])
@login_required
def alerts():
    limit = min(int(request.args.get('limit', 20)), 200)
    severity = request.args.get('severity')

    query = Alert.query.order_by(Alert.created_at.desc())
    if severity:
        query = query.filter_by(severity=severity)
    results = query.limit(limit).all()

    return jsonify([{
        'id': a.id,
        'external_id': a.external_id,
        'source': a.source,
        'rule_name': a.rule_name,
        'severity': a.severity,
        'asset_id': a.asset_id,
        'incident_id': a.incident_id,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    } for a in results])


@api_bp.route('/dashboard/stats', methods=['GET'])
@login_required
def dashboard_stats():
    incidents_open = Incident.query.filter_by(status='open').count()
    incidents_critical = Incident.query.filter_by(criticality='critical').count()

    latest_alert = Alert.query.order_by(Alert.created_at.desc()).first()
    latest_alert_data = None
    if latest_alert:
        latest_alert_data = {
            'rule_name': latest_alert.rule_name,
            'severity': latest_alert.severity,
            'source': latest_alert.source,
            'created_at': latest_alert.created_at.isoformat() if latest_alert.created_at else None,
        }

    last_reading = SensorReading.query.order_by(SensorReading.recorded_at.desc()).first()
    last_temp = float(last_reading.temperature) if last_reading and last_reading.temperature else None
    last_hum = float(last_reading.humidity) if last_reading and last_reading.humidity else None

    prtg_summary = prtg_service.get_sensor_summary()
    prtg_ok = prtg_summary.get('error', 0) == 0 and bool(prtg_summary)

    return jsonify({
        'incidents_open': incidents_open,
        'incidents_critical': incidents_critical,
        'latest_alert': latest_alert_data,
        'last_temp': last_temp,
        'last_hum': last_hum,
        'prtg_ok': prtg_ok,
    })


@api_bp.route('/iot/readings', methods=['GET'])
@login_required
def iot_readings_history():
    hours = int(request.args.get('hours', 24))
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    readings = (SensorReading.query
                .filter(SensorReading.recorded_at >= since)
                .order_by(SensorReading.recorded_at.asc())
                .all())

    return jsonify([{
        'id': r.id,
        'temperature': float(r.temperature) if r.temperature else None,
        'humidity': float(r.humidity) if r.humidity else None,
        'recorded_at': r.recorded_at.isoformat() if r.recorded_at else None,
    } for r in readings])
