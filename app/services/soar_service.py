import os
import logging
from datetime import datetime, timezone

from ..extensions import db
from ..models.incident import Incident, Alert
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

    # Persistance de l'alerte (dashboard + vue /security)
    _record_alert(alert, asset, result['incident_id'])

    triggered_soar = False
    if _rank(criticality) >= _rank(SOAR_THRESHOLD):
        triggered_soar = _trigger_isolation(result['incident_id'], asset, source)

    result['triggered_soar'] = triggered_soar
    return result


def _record_alert(alert, asset, incident_id):
    """Enregistre l'alerte Wazuh en base, dédupliquée par external_id."""
    external_id = alert.get('external_id')
    existing = Alert.query.filter_by(external_id=external_id).first()
    if existing:
        if existing.incident_id is None:
            existing.incident_id = incident_id
            db.session.commit()
        return existing

    alert_row = Alert(
        external_id=external_id,
        source='wazuh',
        rule_name=alert.get('title') or f"rule {alert.get('rule_id', '')}".strip(),
        severity=alert.get('criticality', 'low'),
        asset_id=asset.id if asset else None,
        incident_id=incident_id,
    )
    db.session.add(alert_row)
    db.session.commit()
    logger.info('Alerte enregistrée id=%d external_id=%s', alert_row.id, external_id)
    return alert_row


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
        isolated = isolate_host(target_ip, incident_id, os.getenv('WAZUH_API_URL', 'https://172.16.1.10:55000'))
        if isolated:
            _verify_isolation(target_ip, incident_id)
        return isolated
    except Exception as e:
        logger.error('Erreur SOAR: %s', e)
        return False


def _verify_isolation(target_ip, incident_id):
    """Valide l'intervention via PRTG : un hôte isolé ne doit plus répondre."""
    from ..services import prtg_service
    still_up = prtg_service.get_device_status(target_ip)
    effective = not still_up
    note = (f"Vérification PRTG : isolation "
            f"{'CONFIRMÉE' if effective else 'NON confirmée'} — "
            f"hôte {target_ip} {'injoignable' if effective else 'toujours joignable'}.")
    logger.info('[SOAR] %s', note)

    incident = db.session.get(Incident, incident_id)
    if incident:
        incident.description = (incident.description or '') + \
            f"\n\n[SOAR {datetime.now(timezone.utc).isoformat()}] {note}"
        incident.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    return effective
