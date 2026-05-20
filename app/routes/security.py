from flask import Blueprint, render_template, request
from ..utils.decorators import role_required
from ..models.incident import Alert
from ..services import wazuh_service

security_bp = Blueprint('security', __name__)


@security_bp.route('/security')
@role_required('admin', 'analyst')
def security():
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 100)
    severity = request.args.get('severity')
    source = request.args.get('source')

    query = Alert.query.order_by(Alert.created_at.desc())

    if severity:
        query = query.filter_by(severity=severity)
    if source:
        query = query.filter_by(source=source)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    live_alerts = []
    try:
        live_alerts = wazuh_service.get_recent_alerts(n=10)
    except Exception:
        pass

    return render_template(
        'security.html',
        pagination=pagination,
        alerts=pagination.items,
        live_alerts=live_alerts,
        filters={'severity': severity, 'source': source},
    )
