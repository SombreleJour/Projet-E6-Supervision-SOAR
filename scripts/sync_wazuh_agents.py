"""
Synchronise les agents Wazuh vers la table assets.
Lance manuellement ou via cron :
    */5 * * * * /opt/supervision-app/venv/bin/python /opt/supervision-app/scripts/sync_wazuh_agents.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services import wazuh_service


def sync():
    app = create_app()
    with app.app_context():
        print("Synchronisation agents Wazuh → assets…")
        result = wazuh_service.sync_agents_to_assets()
        created = result.get('created', 0)
        updated = result.get('updated', 0)
        print(f"Terminé — créés : {created}, mis à jour : {updated}")


if __name__ == '__main__':
    sync()
