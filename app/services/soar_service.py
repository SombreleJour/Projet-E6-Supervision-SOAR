import os
import logging
from datetime import datetime, timezone

from ..extensions import db
from ..models.incident import Incident
from ..models.asset import Asset

logger = logging.getLogger(__name__)

SOAR_THRESHOLD = os.getenv('SOAR_THRESHOLD', 'high')
CRITICALITY_RANK = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}


def _rank(level):
    return CRITICALITY_RANK.get(level.lower(), 0)


def process_wazuh_alert(alert: dict) -> dict:
    external_id = alert.get('external_id')
    if not external_id:
        logger.warning('Alerte sans external_id — ignorée')
        return {'action': 'skipped', 'reason': 'missing external_id'}

    source = alert.get('source', 'unknown')
    criticality = alert.get('criticality', 'low')

    asset = Asset.query.filter_by(hostname=source).first() or Asset.query.filter_by(ip_address=source).first()
    if not asset:
        logger.warning("Aucun asset pour la source '%s'", source)

    existing = Incident.query.filter_by(external_id=external_id).first()
    result = (_update_incident(existing, criticality, alert.get('description', ''))
              if existing
              else _create_incident(external_id, alert, asset))

    triggered_soar = False
    if _rank(criticality) >= _rank(SOAR_THRESHOLD):
        triggered_soar = _trigger_isolation(result['incident_id'], asset, source)

    result['triggered_soar'] = triggered_soar
    return result


def _create_incident(external_id, alert, asset):
    incident = Incident(
        external_id=external_id,
        title=alert.get('title', 'Alerte sans titre'),
        description=f"[Wazuh rule {alert.get('rule_id', '')}] Source : {alert.get('source', '')}\n\n{alert.get('description', '')}",
        criticality=alert.get('criticality', 'low'),
        category=alert.get('category', 'security'),
        status='open',
        source='wazuh',
        asset_id=asset.id if asset else None,
    )
    db.session.add(incident)
    db.session.commit()
    logger.info('Incident créé id=%d external_id=%s', incident.id, external_id)
    return {'action': 'created', 'incident_id': incident.id}


def _update_incident(incident, criticality, description):
    updated = False
    if _rank(criticality) > _rank(incident.criticality):
        logger.info('Escalade %s → %s (id=%d)', incident.criticality, criticality, incident.id)
        incident.criticality = criticality
        updated = True
    if description and description not in (incident.description or ''):
        incident.description = (incident.description or '') + f'\n\n[{datetime.now(timezone.utc).isoformat()}]\n{description}'
        updated = True
    if updated:
        incident.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    return {'action': 'updated' if updated else 'skipped', 'incident_id': incident.id}


def _trigger_isolation(incident_id, asset, source):
    try:
        from ..playbooks.isolate_host import isolate_host
        target_ip = asset.ip_address if asset else source
        logger.warning('Déclenchement isolation SOAR incident_id=%d cible=%s', incident_id, target_ip)
        return isolate_host(target_ip, incident_id, os.getenv('WAZUH_API_URL', 'https://172.16.1.10:55000'))
    except Exception as e:
        logger.error('Erreur SOAR: %s', e)
        return False
