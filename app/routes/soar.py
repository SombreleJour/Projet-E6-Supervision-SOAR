from flask import Blueprint, request, jsonify
from ..extensions import db
from ..utils.decorators import role_required
from ..models.incident import Incident
from ..services import soar_service

soar_bp = Blueprint('soar', __name__)


@soar_bp.route('/process', methods=['POST'])
@role_required('admin', 'analyst')
def process():
    alert = request.get_json(silent=True)
    if not alert:
        return jsonify({'error': 'Invalid JSON body'}), 400

    result = soar_service.process_wazuh_alert(alert)
    return jsonify(result), 200


@soar_bp.route('/status/<int:incident_id>', methods=['GET'])
@role_required('admin', 'analyst')
def status(incident_id):
    incident = db.get_or_404(Incident, incident_id)

    return jsonify({
        'incident_id': incident.id,
        'status': incident.status,
        'criticality': incident.criticality,
        'title': incident.title,
        'source': incident.source,
        'asset_id': incident.asset_id,
        'updated_at': incident.updated_at.isoformat() if incident.updated_at else None,
    })
