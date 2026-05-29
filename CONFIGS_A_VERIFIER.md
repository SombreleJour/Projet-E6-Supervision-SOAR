# Configs à vérifier — Déploiement supervision-app

> Audit pré-déploiement — Milo Mazzone / BTS CIEL IR — Deletec  
> Mise à jour : 2026-05-29

---

## 1. Bugs résiduels corrigés dans cette session

| # | Fichier | Problème | Correction |
|---|---------|----------|------------|
| 1 | `dht22_collector.py` | Aucun header `Authorization: Bearer` → 401 sur chaque POST du RPi5 | Ajout `headers={"Authorization": f"Bearer {TOKEN}"}` |
| 2 | `app/routes/soar.py` | `/api/soar/process` protégé par `@role_required` → Wazuh reçoit 302 redirect au lieu de traiter l'alerte | Remplacé par `_verify_bearer()` + `SOAR_API_TOKEN` |
| 3 | `app/routes/incidents.py` | `trigger_soar` ignorait le paramètre `action` → toujours `isolate_host` même pour block_ip | Dispatch sur `action = request.form.get('action', 'isolate')` |
| 4 | `app/routes/api.py` + `iot.py` | `if r.temperature` falsy pour Decimal 0.0 | Changé en `if r.temperature is not None` |
| 5 | `app/templates/dashboard.html` | Widget PRTG : condition inversée sur `prtg_status.get('error')` | `{% if prtg_status %}` / `{% else %}` |
| 6 | `app/__init__.py` | Handlers 403/404 manquants | Ajout `@app.errorhandler(403/404)` + templates |
| 7 | `app/utils/logger.py` | `logs/` non créé → crash RotatingFileHandler | Ajout `os.makedirs(...)` avant création du handler |

---

## 2. Variables d'environnement — `.env` à créer

Copier `.env.example` → `.env` et remplir **toutes** les valeurs :

```bash
cp /opt/supervision-app/.env.example /opt/supervision-app/.env
nano /opt/supervision-app/.env
```

| Variable | Valeur requise | Risque si absente |
|----------|---------------|-------------------|
| `SECRET_KEY` | Chaîne aléatoire (32+ chars) — `python -c "import secrets; print(secrets.token_hex(32))"` | Sessions Flask non sécurisées |
| `DATABASE_URL` | `postgresql://supervision_user:MOT_DE_PASSE@localhost:5432/supervision_db` | Crash au démarrage |
| `PRTG_PASSWORD` ou `PRTG_PASSHASH` | Mot de passe ou passhash PRTG | Widget PRTG vide |
| `WAZUH_PASSWORD` | Mot de passe API Wazuh (compte `wazuh-wui`) | Alertes live vides, sync agents KO |
| `IOT_API_TOKEN` | Token partagé RPi5 ↔ serveur (ex : `openssl rand -hex 24`) | Toutes les lectures IoT refusées (401) |
| `SOAR_API_TOKEN` | Token partagé Wazuh → webhook (ex : `openssl rand -hex 24`) | Webhook SOAR rejeté (401) |
| `PFSENSE_PASSWORD` | Mot de passe pfSense | Playbook `block_ip` échoue |

> **IMPORTANT** : Le `.env` ne doit jamais être commité (il est dans `.gitignore`).

---

## 3. Configuration RPi5 — dht22_collector.py

| Point | À vérifier |
|-------|-----------|
| `API_URL` (ligne 11) | Changer `172.16.1.15` par l'IP réelle de SRV-APP sur le réseau lab |
| `TOKEN` (ligne 14) | Doit correspondre exactement à `IOT_API_TOKEN` dans `.env` sur SRV-APP |
| `GPIO_PIN = board.D4` | Vérifier que le DHT22 est bien branché sur GPIO4 (BCM) du RPi5 |
| Bibliothèques | `pip3 install adafruit-circuitpython-dht requests` sur le RPi5 |
| Service systemd RPi5 | Créer `/etc/systemd/system/dht22.service` pour démarrage automatique |

**Service systemd RPi5 (exemple) :**
```ini
[Unit]
Description=DHT22 IoT collector
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/dht22_collector.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 4. Base de données PostgreSQL

Exécuter sur SRV-APP (en tant que `postgres`) :

```bash
sudo -u postgres psql << 'EOF'
CREATE USER supervision_user WITH PASSWORD 'MOT_DE_PASSE';
CREATE DATABASE supervision_db OWNER supervision_user;
GRANT ALL PRIVILEGES ON DATABASE supervision_db TO supervision_user;
EOF
```

Puis initialiser le schéma et les données de base :

```bash
cd /opt/supervision-app
source venv/bin/activate
python scripts/seed.py
```

> `seed.py` crée les tables, les 3 rôles, l'utilisateur `admin` (mot de passe : `Admin1234!`), le capteur DHT22, et 4 assets lab. **Changer le mot de passe admin après la première connexion.**

---

## 5. Gunicorn + Nginx + HTTPS

### 5.1 Service systemd Gunicorn

Créer `/etc/systemd/system/supervision.service` :

```ini
[Unit]
Description=Supervision App (Gunicorn)
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/supervision-app
EnvironmentFile=/opt/supervision-app/.env
ExecStart=/opt/supervision-app/venv/bin/gunicorn \
    --workers 4 \
    --bind unix:/run/supervision.sock \
    --access-logfile /opt/supervision-app/logs/gunicorn-access.log \
    --error-logfile /opt/supervision-app/logs/gunicorn-error.log \
    run:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /opt/supervision-app/logs
sudo chown www-data:www-data /opt/supervision-app/logs
sudo chown -R www-data:www-data /opt/supervision-app
sudo systemctl enable --now supervision
```

> **Vérifier** que `/run/supervision.sock` est accessible par Nginx (même groupe `www-data`).

### 5.2 Certificat SSL auto-signé

```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/supervision.key \
    -out /etc/ssl/certs/supervision.crt \
    -subj "/CN=supervision.local/O=Deletec/C=FR"
```

### 5.3 Configuration Nginx

Créer `/etc/nginx/sites-available/supervision` :

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /etc/ssl/certs/supervision.crt;
    ssl_certificate_key /etc/ssl/private/supervision.key;

    location / {
        proxy_pass http://unix:/run/supervision.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/supervision-app/app/static/;
        expires 1d;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/supervision /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 6. Intégration Wazuh

### 6.1 Alertes live (section "Alertes temps réel" dans /security)

- `wazuh_service.get_recent_alerts()` requête OpenSearch sur port **9200** avec les credentials `WAZUH_USER` / `WAZUH_PASSWORD`
- **Problème connu** : le compte `wazuh-wui` n'a pas accès à l'index OpenSearch — il faut le compte `admin` (ou un compte avec rôle `all_access` dans OpenSearch)
- **Fix** : dans `.env`, mettre `WAZUH_USER=admin` et `WAZUH_PASSWORD=<mot de passe admin OpenSearch>` — OU créer un compte dédié dans OpenSearch avec accès lecture sur `wazuh-alerts-*`
- Si les credentials sont faux → alertes live toujours vides (silencieux, pas de crash)

### 6.2 Badge sévérité dans les alertes live

- Les niveaux Wazuh sont **numériques** (1–15), pas textuels
- Le CSS définit `.sev-critical`, `.sev-high`, `.sev-medium`, `.sev-low` — pas `.sev-12` etc.
- Les badges des alertes live apparaîtront sans style (fond gris Bootstrap par défaut)
- Comportement non bloquant, visuel uniquement

### 6.3 Webhook SOAR (Wazuh → /api/soar/process)

- URL à configurer dans Wazuh Manager (`ossec.conf`) : `https://172.16.1.15/api/soar/process`
- Header requis : `Authorization: Bearer <SOAR_API_TOKEN>`
- Le token doit correspondre à `SOAR_API_TOKEN` dans `.env` sur SRV-APP

**Active Response `firewall-drop` requis sur les agents Wazuh :**  
Dans `/var/ossec/etc/ossec.conf` sur chaque agent :
```xml
<active-response>
  <command>firewall-drop</command>
  <location>local</location>
  <rules_id>...</rules_id>
  <timeout>600</timeout>
</active-response>
```
Sans cette config, `isolate_host` obtient un token et trouve l'agent, mais la commande active-response ne s'exécute pas.

---

## 7. Intégration pfSense

- Installer le package **FauxAPI** ou **pfSense API** sur pfSense (Système > Gestionnaire de paquets)
- Vérifier que l'API est accessible : `curl -k https://172.16.1.1/api/v1/firewall/rule`
- Credentials dans `.env` : `PFSENSE_USER` / `PFSENSE_PASSWORD`
- Sans l'API installée → `block_ip` échoue avec timeout (5s) puis retourne `False`

---

## 8. Tests

```bash
# Installer pytest (non inclus dans requirements.txt — dépendance de dev)
pip install pytest

# Lancer les tests
cd /opt/supervision-app
pytest tests/ -v
```

- `tests/test_auth.py` — 6 tests (login, logout, 403, inactif…)
- `tests/test_incidents.py` — 7 tests (CRUD, SOAR upsert, escalade)
- Tests sur SQLite en mémoire, `WTF_CSRF_ENABLED=False`
- Pas de tests pour `iot`, `api`, `security`, `admin` — couverture partielle

---

## 9. Limitations connues (non bloquantes)

| Point | Détail |
|-------|--------|
| Seuils IoT non persistants | Modifiés via `/admin/thresholds` → perdus au redémarrage Gunicorn. Modifier directement `.env` pour persistance |
| PRTG version gratuite | Limite 100 capteurs max |
| `ip_address` VARCHAR(45) | Stocké en texte, pas en type INET PostgreSQL — fonctionnel mais pas de validation réseau en base |
| Wazuh Indexer vs Manager | Port 9200 ≠ port 55000, credentials différents — voir §6.1 |
| Pas de rate limiting | `/api/iot/readings` POST et `/api/soar/process` POST sans rate limit — acceptable en lab |
| Chart.js depuis CDN | Si le réseau lab n'a pas d'accès internet, le graphique IoT n'affichera rien. Télécharger Chart.js en local si nécessaire |
| Bootstrap Icons depuis CDN | Même contrainte que Chart.js |

---

## 10. Checklist déploiement — ordre d'exécution

- [ ] Créer `.env` depuis `.env.example` avec les vrais mots de passe
- [ ] `SECRET_KEY` changé (chaîne aléatoire 32+ chars)
- [ ] PostgreSQL : créer `supervision_user` + `supervision_db`
- [ ] `pip install -r requirements.txt` dans le venv
- [ ] `python scripts/seed.py` (crée tables + admin + assets)
- [ ] Mot de passe admin changé après première connexion
- [ ] Certificat SSL généré
- [ ] Service Gunicorn activé (`systemctl enable --now supervision`)
- [ ] Nginx configuré et rechargé
- [ ] PRTG : vérifier `PRTG_USERNAME` / `PRTG_PASSWORD` ou `PRTG_PASSHASH`
- [ ] Wazuh : vérifier credentials OpenSearch (§6.1) pour alertes live
- [ ] Wazuh : configurer webhook vers `/api/soar/process` avec `SOAR_API_TOKEN`
- [ ] Wazuh : activer Active Response `firewall-drop` sur les agents
- [ ] pfSense : installer package API
- [ ] RPi5 : mettre à jour `API_URL` et `TOKEN` dans `dht22_collector.py`
- [ ] RPi5 : démarrer le service `dht22.service`
- [ ] `TOKEN` RPi5 = `IOT_API_TOKEN` .env (identiques)
- [ ] `SOAR_API_TOKEN` .env configuré dans Wazuh webhook header
- [ ] `pytest tests/ -v` → tous verts
