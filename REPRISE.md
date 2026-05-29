# État du projet — Pause après Blocs 1 à 6 complets

## Fait
- [x] Bloc 1 : requirements.txt, run.py, __init__.py, config.py, extensions.py,
               4 modèles (user, incident, asset, sensor_reading),
               decorators.py, logger.py
- [x] Bloc 2 : prtg_service.py, wazuh_service.py, soar_service.py,
               isolate_host.py, block_ip.py
- [x] Bloc 3 : 8 blueprints (auth, api, dashboard, incidents,
               security, iot, admin, soar)
               Bugs corrigés : imports absolus/relatifs, db.get_or_404(),
               CSRFProtect + exemption api_bp et soar_bp
- [x] Bloc 4 : 9 templates Bootstrap 5 dark theme
               (base.html, login.html, dashboard.html, list/create/detail.html,
               security.html, iot.html, admin/settings.html)
- [x] Bloc 5 : dashboard.js (polling 30s), iot.js (Chart.js), incidents.js
- [x] Bloc 6 : seed.py, sync_wazuh_agents.py, test_auth.py, test_incidents.py

## Total fichiers créés : 22

## À faire (prochaine session)
- [ ] Déploiement sur VM Debian SRV-APP (172.16.1.15)
- [ ] Init BDD PostgreSQL + python scripts/seed.py
- [ ] Config Nginx + SSL auto-signé
- [ ] Service systemd supervision-app
- [ ] Tests pytest sur la VM
- [ ] Tests fonctionnels : curl SOAR + curl IoT

## Prochaine commande à lancer
Voir GUIDE_CLAUDE_CODE.md — Étape 4 (Initialisation Base de Données)
