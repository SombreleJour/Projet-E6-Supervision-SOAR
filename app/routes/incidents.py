from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from ..extensions import db
from ..models.incident import Incident, IncidentComment
from ..models.asset import Asset
from ..models.user import User
from ..utils.decorators import role_required
from ..services import soar_service

incidents_bp = Blueprint('incidents', __name__)

VALID_STATUSES = {'open', 'in_progress', 'closed'}
VALID_CRITICALITIES = {'low', 'medium', 'high', 'critical'}
VALID_CATEGORIES = {'security', 'performance', 'network'}
VALID_SOURCES = {'wazuh', 'prtg', 'manual'}


@incidents_bp.route('/')
@role_required('admin', 'analyst')
def list_incidents():
    status = request.args.get('status')
    criticality = request.args.get('criticality')
    category = request.args.get('category')
    source = request.args.get('source')
    page = int(request.args.get('page', 1))

    query = Incident.query.order_by(Incident.created_at.desc())

    if status and status in VALID_STATUSES:
        query = query.filter_by(status=status)
    if criticality and criticality in VALID_CRITICALITIES:
        query = query.filter_by(criticality=criticality)
    if category and category in VALID_CATEGORIES:
        query = query.filter_by(category=category)
    if source and source in VALID_SOURCES:
        query = query.filter_by(source=source)

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'incidents/list.html',
        pagination=pagination,
        incidents=pagination.items,
        filters={'status': status, 'criticality': criticality,
                 'category': category, 'source': source},
    )


@incidents_bp.route('/new', methods=['GET', 'POST'])
@role_required('admin', 'analyst')
def new_incident():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Le titre est obligatoire.', 'danger')
            return redirect(url_for('incidents.new_incident'))

        asset_id = request.form.get('asset_id') or None
        incident = Incident(
            title=title,
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', 'security'),
            criticality=request.form.get('criticality', 'low'),
            status='open',
            source=request.form.get('source', 'manual'),
            asset_id=int(asset_id) if asset_id else None,
            created_by=current_user.id,
        )
        db.session.add(incident)
        db.session.commit()
        flash('Incident créé.', 'success')
        return redirect(url_for('incidents.incident_detail', id=incident.id))

    return render_template('incidents/create.html', assets=Asset.query.order_by(Asset.name).all())


@incidents_bp.route('/<int:id>')
@role_required('admin', 'analyst')
def incident_detail(id):
    incident = db.get_or_404(Incident, id)
    users = User.query.filter_by(is_active=True).all()
    return render_template('incidents/detail.html', incident=incident, users=users)


@incidents_bp.route('/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    incident = db.get_or_404(Incident, id)
    comment_text = request.form.get('comment', '').strip()

    if not comment_text:
        flash('Le commentaire ne peut pas être vide.', 'danger')
        return redirect(url_for('incidents.incident_detail', id=id))

    db.session.add(IncidentComment(
        incident_id=incident.id,
        user_id=current_user.id,
        comment=comment_text,
    ))
    db.session.commit()
    flash('Commentaire ajouté.', 'success')
    return redirect(url_for('incidents.incident_detail', id=id))


@incidents_bp.route('/<int:id>/assign', methods=['POST'])
@role_required('admin', 'analyst')
def assign_incident(id):
    incident = db.get_or_404(Incident, id)
    user_id = request.form.get('user_id')

    if user_id:
        user = db.session.get(User, int(user_id))
        if user:
            incident.assigned_to = user.id
            incident.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash(f'Incident assigné à {user.username}.', 'success')
        else:
            flash('Utilisateur introuvable.', 'danger')
    else:
        incident.assigned_to = None
        incident.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Assignation retirée.', 'info')

    return redirect(url_for('incidents.incident_detail', id=id))


@incidents_bp.route('/<int:id>/status', methods=['POST'])
@role_required('admin', 'analyst')
def change_status(id):
    incident = db.get_or_404(Incident, id)
    new_status = request.form.get('status')

    if new_status not in VALID_STATUSES:
        flash('Statut invalide.', 'danger')
        return redirect(url_for('incidents.incident_detail', id=id))

    incident.status = new_status
    incident.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Statut mis à jour : {new_status}.', 'success')
    return redirect(url_for('incidents.incident_detail', id=id))


@incidents_bp.route('/<int:id>/soar', methods=['POST'])
@role_required('admin', 'analyst')
def trigger_soar(id):
    incident = db.get_or_404(Incident, id)

    if not incident.asset_id:
        flash('Aucun asset lié — isolation impossible.', 'warning')
        return redirect(url_for('incidents.incident_detail', id=id))

    result = soar_service.process_wazuh_alert({
        'external_id': incident.external_id or f'manual-{incident.id}',
        'title': incident.title,
        'description': incident.description or '',
        'source': str(incident.asset.ip_address) if incident.asset else '',
        'criticality': incident.criticality,
        'category': incident.category,
        'rule_id': 'manual',
    })

    if result.get('triggered_soar'):
        flash('Action SOAR déclenchée.', 'success')
    else:
        flash('Action SOAR non déclenchée (seuil non atteint ou erreur).', 'warning')

    return redirect(url_for('incidents.incident_detail', id=id))
