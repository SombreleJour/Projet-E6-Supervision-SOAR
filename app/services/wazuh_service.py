import os
import re
import urllib3
import requests

from ..extensions import db
from ..models.asset import Asset
from ..utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _api_url():
    return os.getenv("WAZUH_API_URL", "https://172.16.1.10:55000")


def _credentials():
    return os.getenv("WAZUH_USER", "wazuh-wui"), os.getenv("WAZUH_PASSWORD", "")


def get_token():
    try:
        user, password = _credentials()
        resp = requests.post(
            f"{_api_url()}/security/user/authenticate",
            auth=(user, password), verify=False, timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["data"]["token"]
    except Exception as e:
        logger.warning(f"Wazuh get_token: {e}")
        return None


def get_agents():
    try:
        token = get_token()
        if not token:
            return []
        resp = requests.get(
            f"{_api_url()}/agents",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 500, "status": "active"},
            verify=False, timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("affected_items", [])
    except Exception as e:
        logger.warning(f"Wazuh get_agents: {e}")
        return []


def get_recent_alerts(n=20):
    """Événements récents via l API REST port 55000 (logs warning + FIM syscheck).
    Aucune dépendance à l indexeur OpenSearch port 9200.
    """
    events = []
    token = get_token()
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Logs manager warning/error
    try:
        resp = requests.get(
            f"{_api_url()}/manager/logs",
            headers=headers,
            params={"limit": 10, "level": "warning", "sort": "-timestamp"},
            verify=False, timeout=5,
        )
        resp.raise_for_status()
        for item in resp.json().get("data", {}).get("affected_items", []):
            ts = item.get("timestamp", "") or ""
            events.append({
                "timestamp": ts,
                "rule": {"description": item.get("description", "—"), "level": 5},
                "agent": {"name": "wazuh-manager"},
            })
    except Exception as e:
        logger.warning(f"Wazuh manager logs: {e}")

    # 2. Événements FIM (syscheck) des agents actifs
    try:
        agents_resp = requests.get(
            f"{_api_url()}/agents",
            headers=headers,
            params={"limit": 50, "status": "active"},
            verify=False, timeout=5,
        )
        agents_resp.raise_for_status()
        active_agents = [
            a for a in agents_resp.json().get("data", {}).get("affected_items", [])
            if a.get("id") != "000"
        ]
        for agent in active_agents[:5]:
            try:
                sc = requests.get(
                    f"{_api_url()}/syscheck/{agent["id"]}",
                    headers=headers,
                    params={"limit": 5, "sort": "-date"},
                    verify=False, timeout=5,
                )
                sc.raise_for_status()
                for item in sc.json().get("data", {}).get("affected_items", []):
                    events.append({
                        "timestamp": item.get("date", "") or "",
                        "rule": {
                            "description": f"FIM — {item.get("file", "?")}",
                            "level": 3,
                        },
                        "agent": {"name": agent.get("name", "—")},
                    })
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Wazuh syscheck: {e}")

    events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return events[:n]


def sync_agents_to_assets():
    created = updated = 0
    for agent in get_agents():
        if agent.get("id") == "000":
            continue
        hostname = agent.get("name", "")
        ip = agent.get("ip", "")
        existing = Asset.query.filter_by(hostname=hostname).first()
        if existing:
            existing.ip_address = ip
            existing.source_system = "wazuh"
            updated += 1
        else:
            db.session.add(Asset(name=hostname, asset_type="server",
                                 ip_address=ip, hostname=hostname, source_system="wazuh"))
            created += 1
    db.session.commit()
    logger.info(f"Wazuh sync: {created} créés, {updated} mis à jour")
    return {"created": created, "updated": updated}


# ── Vue d ensemble pour le dashboard ─────────────────────────────────────
def get_wazuh_overview(cache_ttl=None):
    from .cache import cached
    return cached("wazuh_overview", cache_ttl, _compute_wazuh_overview)


def _compute_wazuh_overview():
    token = get_token()
    if not token:
        return {"available": False}

    try:
        resp = requests.get(
            f"{_api_url()}/agents",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 500}, verify=False, timeout=5,
        )
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("affected_items", [])
    except Exception as e:
        logger.warning(f"Wazuh overview agents: {e}")
        return {"available": False}

    agents = []
    active = disconnected = other = 0
    for a in items:
        status = a.get("status", "") or "—"
        if status == "active":
            active += 1
        elif status == "disconnected":
            disconnected += 1
        else:
            other += 1
        os_info = a.get("os") or {}
        agents.append({
            "name": a.get("name", "—"),
            "ip": a.get("ip", "—"),
            "os": os_info.get("name") or os_info.get("platform") or "—",
            "status": status,
        })

    total = len(items)
    alerts = []
    for al in get_recent_alerts(8):
        rule = al.get("rule", {}) or {}
        agent = al.get("agent", {}) or {}
        ts = al.get("timestamp", "") or ""
        alerts.append({
            "time": ts[11:19] if len(ts) >= 19 else ts[:8],
            "description": rule.get("description", "—"),
            "level": rule.get("level", 0),
            "agent": agent.get("name", "—"),
        })

    agents.sort(key=lambda x: 1 if x["status"] == "active" else 0)

    return {
        "available": True,
        "agents_total": total,
        "agents_active": active,
        "agents_disconnected": disconnected,
        "agents_other": other,
        "coverage_rate": round(active / total * 100, 1) if total else 0.0,
        "agents": agents[:50],
        "alerts": alerts,
    }
