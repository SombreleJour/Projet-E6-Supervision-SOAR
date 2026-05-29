
import os
import logging
from datetime import datetime, timezone

from ..extensions import db
from ..models.incident import Incident
from ..models.asset import Asset

logger = logging.getLogger(__name__)

# Seuil de criticité à partir duquel un playbook d'isolation est déclenché
# Valeurs possibles : "low" | "medium" | "high" | "critical"
SOAR_THRESHOLD = os.getenv('SOAR_THRESHOLD', 'high')

CRITICALITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _rank(level: str) -> int:
    return CRITICALITY_RANK.get(level.lower(), 0)



# Point d'entrée principal

def process_wazuh_alert(alert: dict) -> dict:
    """
    Traite une alerte Wazuh brute reçue depuis l'API REST.

    Paramètres attendus dans `alert` :
        external_id  (str)  — ID unique Wazuh de l'alerte
        title        (str)  — Description courte de l'alerte
        description  (str)  — Détail complet de l'alerte
        source       (str)  — Hostname ou IP de l'agent Wazuh source
        criticality  (str)  — Niveau : low / medium / high / critical
        category     (str)  — Ex. : "brute_force", "malware", "lateral_movement"
        rule_id      (str)  — ID de la règle Wazuh déclenchée
        timestamp    (str)  — ISO 8601, ex. "2025-01-15T14:32:00Z"

    Retourne :
        dict avec les clés : action ("created"|"updated"|"skipped"), incident_id, triggered_soar
    """
    external_id  = alert.get("external_id")
    title        = alert.get("title", "Alerte sans titre")
    description  = alert.get("description", "")
    source       = alert.get("source", "unknown")
    criticality  = alert.get("criticality", "low")
    category     = alert.get("category", "security")
    rule_id      = alert.get("rule_id", "")

    # ── 1. Validation de l'identifiant externe ────────────────────
    if not external_id:
        logger.warning("Alerte reçue sans external_id — ignorée")
        return {"action": "skipped", "reason": "missing external_id"}

    # ── 2. Résolution de l'asset source (machine visée) ──────────
    asset = Asset.query.filter_by(hostname=source).first()
    if not asset:
        # Tentative par IP si hostname non résolu
        asset = Asset.query.filter_by(ip_address=source).first()
    asset_id = asset.id if asset else None

    if not asset_id:
        logger.warning("Aucun asset trouvé pour la source '%s'", source)

    # ── 3. Comparaison avec les incidents déjà en base ───────────
    existing = Incident.query.filter_by(external_id=external_id).first()

    if existing:
        result = _update_incident(existing, criticality, description)
    else:
        result = _create_incident(
            external_id=external_id,
            title=title,
            description=description,
            source=source,
            asset_id=asset_id,
            criticality=criticality,
            category=category,
            rule_id=rule_id,
        )

    # ── 4. Déclenchement playbook si criticité suffisante ────────
    triggered_soar = False
    if _rank(criticality) >= _rank(SOAR_THRESHOLD):
        triggered_soar = _trigger_isolation(
            incident_id=result["incident_id"],
            asset=asset,
            source=source,
        )

    result["triggered_soar"] = triggered_soar
    return result



# Création d'un nouvel incident

def _create_incident(
    external_id, title, description, source,
    asset_id, criticality, category, rule_id
) -> dict:
    incident = Incident(
        external_id  = external_id,
        title        = title,
        description  = (
            f"[Wazuh rule {rule_id}] Source : {source}\n\n{description}"
        ),
        criticality  = criticality,
        category     = category,
        status       = "open",
        source       = "wazuh",
        asset_id     = asset_id,
        created_at   = datetime.now(timezone.utc),
        updated_at   = datetime.now(timezone.utc),
    )
    db.session.add(incident)
    db.session.commit()

    logger.info(
        "Incident créé — id=%d  external_id=%s  criticité=%s",
        incident.id, external_id, criticality,
    )
    return {"action": "created", "incident_id": incident.id}



# Mise à jour d'un incident existant

def _update_incident(incident: Incident, criticality: str, description: str) -> dict:
    updated = False

    # Escalade de criticité uniquement (jamais de rétrogradation)
    if _rank(criticality) > _rank(incident.criticality):
        logger.info(
            "Escalade criticité incident id=%d : %s → %s",
            incident.id, incident.criticality, criticality,
        )
        incident.criticality = criticality
        updated = True

    # Mise à jour description si enrichie
    if description and description not in (incident.description or ''):
        incident.description += f"\n\n[Mise à jour {datetime.now(timezone.utc).isoformat()}]\n{description}"
        updated = True

    if updated:
        incident.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info("Incident mis à jour — id=%d", incident.id)

    return {"action": "updated" if updated else "skipped", "incident_id": incident.id}



# Déclenchement du playbook d'isolation réseau

def _trigger_isolation(incident_id: int, asset, source: str) -> bool:
    """
    Appelle le playbook isolate_host si un asset résolvable est disponible.
    En cas d'échec, journalise sans lever d'exception (fail-safe).
    """
    try:
        from ..playbooks.isolate_host import isolate_host

        target_ip = asset.ip_address if asset else source

        logger.warning(
            "Déclenchement isolation SOAR — incident_id=%d  cible=%s",
            incident_id, target_ip,
        )

        success = isolate_host(
            target_ip=target_ip,
            incident_id=incident_id,
            wazuh_api_url=os.getenv('WAZUH_API_URL', 'https://172.16.1.10:55000'),
        )

        if success:
            logger.info("Isolation réussie — cible=%s", target_ip)
        else:
            logger.error("Isolation échouée — cible=%s", target_ip)

        return success

    except Exception as e:
        logger.error("Erreur lors du déclenchement SOAR : %s", e)
        return False