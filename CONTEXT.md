# CONTEXT.md — Projet Supervision Hybride PRTG/Wazuh/SOAR
# Étudiant : MAZZONE Milo — BTS CIEL Option IR — Session 2025
# Commanditaire : Deletec — 35 rue de Prony, 75017 Paris
# Tuteur entreprise : Etienne Guertin
# Tuteur pédagogique : Thibault AYMERIC

---

## 1. DESCRIPTION DU PROJET

### Contexte
Deletec est un prestataire informatique spécialisé dans l'infogérance de PME. 
Actuellement, la supervision réseau (NetOps) via PRTG et la sécurité (SecOps) 
via Wazuh sont gérées séparément, ce qui entraîne des délais de détection et 
une absence de corrélation entre événements performance et sécurité.

### Objectif
Développer un Proof of Concept d'une plateforme web unifiée combinant :
- Supervision des infrastructures (PRTG Network Monitor)
- Analyse de sécurité centralisée (SIEM Wazuh)
- Automatisation de la réponse aux incidents (SOAR)
- Surveillance environnementale IoT (DHT22 via Raspberry Pi 5)

### Contraintes absolues
- Budget zéro : uniquement open source ou versions gratuites
- Environnement 100% virtualisé (VMware Workstation Pro)
- Aucune donnée client réelle (conformité RGPD Deletec)
- PRTG version gratuite limitée à 100 capteurs
- 150 heures de développement total sur 5 mois

---

## 2. INFRASTRUCTURE RÉSEAU

### Topologie
- Hyperviseur : VMware Workstation Pro (machine hôte physique)
- Pare-feu/routeur : pfSense CE 2.7+

### VLANs et adressage IP
```
VLAN SRV  (172.16.1.0/24)  — Serveurs de production
VLAN IOT  (172.16.2.0/24)  — Sonde environnementale
VLAN Test (172.16.5.0/24)  — Postes de test (DHCP 172.16.5.2-254)
```

### Machines virtuelles et équipements
```
pfSense (Interface WAN)           DHCP (internet)
pfSense (Interface SRV)           172.16.1.1   — gateway VLAN SRV
pfSense (Interface IOT)           172.16.2.1   — gateway VLAN IOT
pfSense (Interface Test)          172.16.5.1   — gateway VLAN Test

VM Windows Server 2022            172.16.1.5   — SRV-AD-PRTG
  Rôles : Active Directory, DNS, DHCP, PRTG Network Monitor
  Domaine : siem.local (NetBIOS : SIEM)
  Admin : SIEM\Administrateur

VM Ubuntu Server 22.04 LTS        172.16.1.10  — SRV-WAZUH
  Rôles : Wazuh Manager, Wazuh Indexer, Wazuh Dashboard
  API Wazuh : https://172.16.1.10:55000
  Dashboard Wazuh : https://172.16.1.10:443
  Credentials API : admin / (voir .env)

VM Debian 13                      172.16.1.15  — SRV-APP
  Rôles : Application Flask, PostgreSQL, Nginx, Gunicorn
  C'est ici que tourne CETTE application
  PostgreSQL port : 5432
  Nginx port : 443 (HTTPS)
  Gunicorn socket : /run/supervision-app.sock

VM Windows 10 (poste test)        172.16.5.5   — PC-TEST-WIN
  Rôle : Machine cible pour tests d'isolement SOAR

VM Debian (poste test)            172.16.5.10  — PC-TEST-LIN
  Rôle : Machine cible pour tests d'isolement SOAR

Raspberry Pi 5 (8 Go RAM)         172.16.2.5   — RPI5-IOT
  Rôle : Sonde IoT DHT22, collecte température/humidité
  Script : /opt/dht22_collector.py
  Service systemd : dht22-collector.service
  Envoi vers : POST https://172.16.1.15/api/iot/readings toutes les 60s
```

---

## 3. STACK TECHNIQUE COMPLÈTE

### Backend
```
Python              3.11+
Flask               3.x          framework web principal
SQLAlchemy          2.x          ORM PostgreSQL
Flask-Login         0.6+         gestion sessions utilisateurs
Flask-WTF           1.x          formulaires + protection CSRF
Werkzeug            3.x          hashing mots de passe (generate_password_hash)
Gunicorn            21.x         serveur WSGI production (workers=4)
psycopg2-binary     2.9+         driver PostgreSQL
python-dotenv       1.x          chargement .env
requests            2.x          appels API PRTG et Wazuh
```

### Base de données
```
PostgreSQL          15+
Nom BDD :           supervision_db
Utilisateur :       supervision_user
Hôte :              localhost (172.16.1.15)
Port :              5432
```

### Frontend
```
Bootstrap           5.3          dark theme (data-bs-theme="dark")
Chart.js            4.x          graphiques dashboard et IoT
Jinja2              3.x          moteur de templates Flask
```

### Serveur web
```
Nginx               1.24+        reverse proxy HTTPS (port 443)
                                 → proxy_pass vers Gunicorn socket Unix
SSL/TLS             auto-signé   certificat pour l'environnement de lab
```

### Outils de développement
```
VS Code                          IDE principal
Git                              versioning (GitHub)
Postman                          tests API REST
pgAdmin / psql                   administration PostgreSQL
```

---

## 4. STRUCTURE DES FICHIERS (ARBORESCENCE COMPLÈTE)

```
/opt/supervision-app/
├── venv/                         environnement virtuel Python
├── run.py                        point d'entrée Gunicorn : from app import create_app; app = create_app()
├── requirements.txt              toutes les dépendances pip
├── .env                          variables d'environnement (NE PAS COMMITTER)
├── README.md                     guide installation et démarrage
│
├── app/
│   ├── __init__.py               create_app() + enregistrement blueprints
│   ├── config.py                 classe Config lisant les variables .env
│   ├── extensions.py             instanciation db, login_manager (imports circulaires évités)
│   │
│   ├── models/
│   │   ├── __init__.py           imports de tous les modèles
│   │   ├── user.py               modèles : Role, User (avec UserMixin Flask-Login)
│   │   ├── incident.py           modèles : Incident, IncidentComment
│   │   ├── asset.py              modèle : Asset (machines supervisées)
│   │   └── sensor_reading.py     modèles : Sensor, SensorReading
│   │
│   ├── routes/
│   │   ├── __init__.py           vide ou imports
│   │   ├── auth.py               blueprint 'auth'  — /login, /logout
│   │   ├── dashboard.py          blueprint 'dashboard' — /dashboard
│   │   ├── incidents.py          blueprint 'incidents' — /incidents, /incidents/new, /incidents/<id>
│   │   ├── security.py           blueprint 'security' — /security
│   │   ├── iot.py                blueprint 'iot' — /iot
│   │   ├── admin.py              blueprint 'admin' — /admin
│   │   ├── api.py                blueprint 'api' — /api/iot/readings, /api/metrics, /api/alerts
│   │   └── soar.py               blueprint 'soar' — /api/soar/process
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── prtg_service.py       wrapper API PRTG (lecture seule, pas de persistance)
│   │   ├── wazuh_service.py      wrapper API Wazuh + sync agents → table assets
│   │   └── soar_service.py       orchestration : process_wazuh_alert(), upsert incidents
│   │
│   ├── playbooks/
│   │   ├── isolate_host.py       isolation via Wazuh Active Response (POST /active-response)
│   │   └── block_ip.py           blocage IP via API pfSense (172.16.1.1)
│   │
│   ├── templates/
│   │   ├── base.html             layout commun : navbar, sidebar, scripts globaux
│   │   ├── auth/
│   │   │   └── login.html        page de connexion
│   │   ├── dashboard.html        dashboard principal unifié
│   │   ├── incidents/
│   │   │   ├── list.html         liste incidents + filtres
│   │   │   ├── create.html       formulaire création ticket
│   │   │   └── detail.html       détail ticket + commentaires + actions SOAR
│   │   ├── security.html         alertes Wazuh paginées
│   │   ├── iot.html              graphiques DHT22 temps réel
│   │   └── admin/
│   │       └── settings.html     gestion comptes + seuils d'alerte
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css         surcharges Bootstrap dark, variables CSS
│   │   ├── js/
│   │   │   ├── dashboard.js      polling 30s, Chart.js widgets KPI
│   │   │   ├── incidents.js      filtres dynamiques, confirmation actions
│   │   │   └── iot.js            graphique température/humidité Chart.js
│   │   └── img/
│   │       └── logo.png          logo Deletec ou placeholder
│   │
│   └── utils/
│       ├── __init__.py
│       ├── decorators.py         @login_required, @role_required('admin')
│       └── logger.py             configuration logging structuré (fichier + stdout)
│
├── tests/
│   ├── test_auth.py              tests login/logout, RBAC, accès non autorisé
│   └── test_incidents.py         tests CRUD incidents, upsert SOAR
│
└── scripts/
    ├── seed.py                   init BDD + création rôles + user admin par défaut
    └── sync_wazuh_agents.py      script cron : sync agents Wazuh → table assets
```

---

## 5. FICHIER .env (STRUCTURE ATTENDUE)

```env
# Flask
FLASK_ENV=production
SECRET_KEY=change_me_in_production_use_secrets_module

# PostgreSQL — VM Debian 172.16.1.15
DATABASE_URL=postgresql://supervision_user:MOTDEPASSE@localhost:5432/supervision_db

# PRTG — VM Windows Server 172.16.1.5
PRTG_BASE_URL=http://172.16.1.5:443
PRTG_USERNAME=prtgadmin
PRTG_PASSWORD=MOTDEPASSE_PRTG
PRTG_PASSHASH=

# Wazuh — VM Ubuntu 172.16.1.10
WAZUH_API_URL=https://172.16.1.10:55000
WAZUH_USER=wazuh-wui
WAZUH_PASSWORD=MOTDEPASSE_WAZUH

# IoT
IOT_API_TOKEN=token_secret_rpi5

# Seuils alertes IoT
TEMP_MAX=35.0
TEMP_MIN=10.0
HUM_MAX=80.0
HUM_MIN=20.0

# SOAR
SOAR_THRESHOLD=high
PFSENSE_URL=https://172.16.1.1
PFSENSE_USER=admin
PFSENSE_PASSWORD=MOTDEPASSE_PFSENSE
```

---

## 6. SCHÉMA BASE DE DONNÉES COMPLET

```sql
CREATE TABLE roles (
    id   SERIAL      PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL  -- 'admin' | 'analyst' | 'operator'
);

CREATE TABLE users (
    id            SERIAL       PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(120) UNIQUE NOT NULL,
    password_hash TEXT         NOT NULL,
    role_id       INTEGER      NOT NULL REFERENCES roles(id),
    is_active     BOOLEAN      DEFAULT TRUE,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assets (
    id            SERIAL       PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    asset_type    VARCHAR(50)  NOT NULL,  -- 'server' | 'workstation' | 'firewall'
    ip_address    INET,
    hostname      VARCHAR(100),
    source_system VARCHAR(50),            -- 'wazuh' | 'prtg' | 'manual'
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE incidents (
    id          SERIAL       PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    category    VARCHAR(50)  NOT NULL,    -- 'security' | 'performance' | 'network'
    criticality VARCHAR(20)  NOT NULL,    -- 'low' | 'medium' | 'high' | 'critical'
    status      VARCHAR(30)  NOT NULL DEFAULT 'open',  -- 'open' | 'in_progress' | 'closed'
    source      VARCHAR(30)  NOT NULL,    -- 'wazuh' | 'prtg' | 'manual'
    asset_id    INTEGER      REFERENCES assets(id),
    created_by  INTEGER      REFERENCES users(id),
    assigned_to INTEGER      REFERENCES users(id),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE incident_comments (
    id          SERIAL    PRIMARY KEY,
    incident_id INTEGER   NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    user_id     INTEGER   NOT NULL REFERENCES users(id),
    comment     TEXT      NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
    id          SERIAL       PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE,
    source      VARCHAR(30)  NOT NULL,    -- 'wazuh' | 'prtg'
    rule_name   VARCHAR(200),
    severity    VARCHAR(20),
    asset_id    INTEGER      REFERENCES assets(id),
    incident_id INTEGER      REFERENCES incidents(id),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sensors (
    id           SERIAL       PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    sensor_type  VARCHAR(50)  NOT NULL,   -- 'DHT22'
    location     VARCHAR(100),
    raspberry_id VARCHAR(100),            -- ex. 'rpi5-iot'
    is_active    BOOLEAN      DEFAULT TRUE
);

CREATE TABLE sensor_readings (
    id          SERIAL        PRIMARY KEY,
    sensor_id   INTEGER       NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    temperature NUMERIC(5,2),
    humidity    NUMERIC(5,2),
    checksum_ok BOOLEAN       DEFAULT TRUE,
    recorded_at TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. MODÈLES SQLALCHEMY ATTENDUS

### app/models/user.py
```python
# Role : id, name
# User : id, username, email, password_hash, role_id (FK), is_active, created_at
# User hérite de UserMixin (Flask-Login)
# Méthodes : check_password(password), has_role(role_name)
# Relation : user.role → Role
```

### app/models/incident.py
```python
# Incident : tous les champs SQL ci-dessus
# IncidentComment : id, incident_id (FK+CASCADE), user_id (FK), comment, created_at
# Relations :
#   incident.asset → Asset
#   incident.creator → User (created_by)
#   incident.assignee → User (assigned_to)
#   incident.comments → list[IncidentComment]
#   incident.alert → Alert (backref)
```

### app/models/asset.py
```python
# Asset : tous les champs SQL
# Relations :
#   asset.incidents → list[Incident]
#   asset.alerts → list[Alert]
```

### app/models/sensor_reading.py
```python
# Sensor : id, name, sensor_type, location, raspberry_id, is_active
# SensorReading : id, sensor_id (FK), temperature, humidity, checksum_ok, recorded_at
# Relation : sensor.readings → list[SensorReading]
```

---

## 8. ROUTES ET COMPORTEMENTS ATTENDUS

### auth.py — blueprint 'auth', prefix ''
```
GET  /login          affiche le formulaire de connexion
POST /login          vérifie credentials, crée session Flask-Login, redirect /dashboard
GET  /logout         détruit la session, redirect /login
```

### dashboard.py — blueprint 'dashboard', prefix ''
```
GET  /dashboard      page principale — @login_required
                     Injecte dans le contexte :
                     - nb_incidents_open : count incidents status='open'
                     - nb_incidents_critical : count incidents criticality='critical'
                     - latest_alerts : 5 dernières alertes (table alerts)
                     - latest_readings : dernière lecture sensor_readings
                     - prtg_status : résultat de prtg_service.get_sensor_summary()
```

### incidents.py — blueprint 'incidents', prefix '/incidents'
```
GET  /               liste tous les incidents, filtres GET params :
                     ?status=open|in_progress|closed
                     ?criticality=low|medium|high|critical
                     ?category=security|performance|network
                     ?source=wazuh|prtg|manual
GET  /new            formulaire création — @role_required('admin','analyst')
POST /new            crée un incident, redirect /incidents/<id>
GET  /<id>           détail d'un incident + ses commentaires + asset lié
POST /<id>/comment   ajoute un commentaire — @login_required
POST /<id>/assign    assigne l'incident à un utilisateur — @role_required('admin','analyst')
POST /<id>/status    change le statut — @role_required('admin','analyst')
POST /<id>/soar      déclenche une action SOAR manuelle — @role_required('admin','analyst')
```

### security.py — blueprint 'security', prefix ''
```
GET  /security       liste paginée des alertes (table alerts)
                     Paramètres : ?page=1&per_page=20&severity=high&source=wazuh
                     Données supplémentaires : appel wazuh_service.get_recent_alerts()
                     pour enrichir avec les alertes temps réel non encore en BDD
```

### iot.py — blueprint 'iot', prefix ''
```
GET  /iot            page IoT
                     Injecte : sensor actif, dernière lecture, 
                     historique 24h pour Chart.js (JSON sérialisé)
                     Seuils depuis .env : TEMP_MAX, TEMP_MIN, HUM_MAX, HUM_MIN
```

### admin.py — blueprint 'admin', prefix '/admin'
```
GET  /               page settings — @role_required('admin')
POST /users/create   crée un utilisateur
POST /users/<id>/toggle  active/désactive un compte
POST /thresholds     met à jour les seuils d'alerte IoT
```

### api.py — blueprint 'api', prefix '/api'
```
POST /iot/readings   reçoit les données du RPi5 (DHT22)
                     Body JSON : { sensor_id, temperature, humidity, timestamp, sensor_id:"dht22-rpi5" }
                     Auth : Bearer token (IOT_API_TOKEN depuis .env)
                     Valide les plages : temp [-10, 60], hum [0, 100]
                     Insère dans sensor_readings
                     Retourne : { status: "ok", id: <reading_id> }

GET  /metrics        retourne métriques PRTG en temps réel (appel prtg_service)
                     Retourne JSON : { sensors: [...], timestamp: "..." }

GET  /alerts         retourne les N dernières alertes en base
                     Paramètres : ?limit=20&severity=high

GET  /dashboard/stats retourne les KPIs pour le refresh JS du dashboard
                     Retourne JSON : {
                       incidents_open: int,
                       incidents_critical: int,
                       latest_alert: {...},
                       last_temp: float,
                       last_hum: float,
                       prtg_ok: bool
                     }
```

### soar.py — blueprint 'soar', prefix '/api/soar'
```
POST /process        point d'entrée principal SOAR
                     Body JSON : alerte Wazuh brute
                     Appelle soar_service.process_wazuh_alert(alert)
                     Retourne : { action, incident_id, triggered_soar }

GET  /status/<incident_id>  statut d'une action SOAR en cours
```

---

## 9. SERVICES

### prtg_service.py
```
get_sensor_summary()     → dict résumé état global (nb capteurs OK/warning/error)
get_sensors()            → list tous les capteurs PRTG
get_sensor(sensor_id)    → dict détail d'un capteur
get_device_status(ip)    → bool True si le device répond (utilisé par SOAR pour vérifier isolation)

Auth PRTG : Basic Auth ou passhash via query params
Base URL : http://172.16.1.5:443
Endpoint : /api/table.json?content=sensors&output=json&username=...&passhash=...
Gestion SSL : verify=False (certificat auto-signé)
Timeout : 5 secondes, fail-safe (retourne dict vide si PRTG injoignable)
```

### wazuh_service.py
```
get_token()              → str JWT token (POST /security/user/authenticate)
get_agents()             → list agents Wazuh avec IP et hostname
get_recent_alerts(n=20)  → list N dernières alertes depuis Wazuh Indexer
sync_agents_to_assets()  → sync agents Wazuh → table assets (appelé par sync_wazuh_agents.py)

Auth Wazuh : JWT Bearer token
Base URL : https://172.16.1.10:55000
Gestion SSL : verify=False (certificat auto-signé lab)
Timeout : 5 secondes, fail-safe
```

### soar_service.py
```
process_wazuh_alert(alert: dict) → dict
  1. Valide external_id (rejette si absent)
  2. Résout l'asset par hostname puis par ip_address
  3. Upsert incident (INSERT si external_id inconnu, UPDATE si existant)
  4. Escalade criticité uniquement (jamais de rétrogradation)
  5. Déclenche isolate_host() si criticality >= SOAR_THRESHOLD (défaut: 'high')
  6. Retourne { action, incident_id, triggered_soar }

SOAR_THRESHOLD : lu depuis os.getenv('SOAR_THRESHOLD', 'high')
Criticité rank : low=1, medium=2, high=3, critical=4
Fail-safe : une erreur de playbook ne fait pas planter le traitement de l'alerte
```

---

## 10. PLAYBOOKS SOAR

### isolate_host.py
```
isolate_host(target_ip, incident_id, wazuh_api_url)
  - Récupère le token JWT Wazuh
  - POST /active-response sur l'agent correspondant à target_ip
  - Action : 'firewall-drop' ou script custom d'isolation réseau
  - Retourne True si HTTP 200, False sinon
  - Loggue toutes les tentatives (succès et échecs)
```

### block_ip.py
```
block_ip(target_ip, incident_id)
  - Appelle l'API pfSense (172.16.1.1) pour ajouter une règle firewall
  - Méthode : POST /api/v1/firewall/rule (pfSense API package)
  - Retourne True si succès
  - Fail-safe : loggue l'erreur sans lever d'exception
```

---

## 11. TEMPLATES — COMPORTEMENTS DÉTAILLÉS

### base.html
```
- Bootstrap 5.3 avec data-bs-theme="dark"
- Navbar : logo Deletec, nom utilisateur connecté, rôle, bouton logout
- Sidebar avec liens de navigation selon le rôle :
    admin    : Dashboard, Incidents, Sécurité, IoT, Administration
    analyst  : Dashboard, Incidents, Sécurité, IoT
    operator : Dashboard, IoT
- Bloc flash messages (succès/erreur/warning)
- Import Bootstrap JS, Chart.js 4.x en bas de page
- Block content pour les pages enfants
- Block extra_js pour les scripts spécifiques à chaque page
```

### dashboard.html
```
- 4 widgets KPI en haut (Bootstrap cards) :
    Incidents ouverts (badge count)
    Incidents critiques (badge rouge)
    Dernière alerte Wazuh (nom règle + sévérité)
    Température/humidité IoT (valeurs temps réel)
- Tableau "Dernières alertes" : 5 lignes, colonnes source/règle/sévérité/date
- Tableau "Incidents récents" : 5 lignes, colonnes titre/criticité/statut/assigné
- Widget PRTG : liste des capteurs en erreur/warning
- Refresh automatique toutes les 30 secondes via fetch('/api/dashboard/stats')
  puis mise à jour DOM sans rechargement de page (dashboard.js)
```

### incidents/list.html
```
- Filtres en haut : dropdowns status, criticality, category, source
- Tableau paginé avec colonnes : ID, titre, criticité (badge coloré), 
  statut, source, asset, assigné, date création
- Bouton "Nouveau ticket" en haut à droite (si rôle admin ou analyst)
- Badges couleur criticité : critical=rouge, high=orange, medium=jaune, low=vert
- Badges couleur statut : open=bleu, in_progress=jaune, closed=gris
```

### incidents/detail.html
```
- Header : titre, criticité, statut, source, asset lié, dates
- Boutons d'action (si admin ou analyst) :
    Changer statut (dropdown)
    Assigner à (dropdown users)
    Déclencher isolation SOAR (bouton rouge, uniquement si asset lié)
    Déclencher blocage IP SOAR (bouton orange)
- Section commentaires : fil chronologique + formulaire ajout commentaire
- Section historique : timestamps des changements de statut
```

### security.html
```
- Filtres : severity, source, date range
- Tableau paginé alertes : external_id, rule_name, severity, asset, 
  incident lié (lien si existant), date
- Les alertes non liées à un incident ont un bouton "Créer ticket"
```

### iot.html
```
- Card état sonde : nom, type, location, raspberry_id, statut actif/inactif
- Card dernière mesure : température (°C) et humidité (%) avec icônes
- Alertes visuelles si seuils dépassés (Bootstrap alert danger/warning)
- Graphique Chart.js ligne : température et humidité sur 24h
  (deux axes Y, couleurs différentes)
- Données chargées depuis /api/iot/readings?hours=24
- Refresh automatique toutes les 60 secondes (iot.js)
```

### admin/settings.html
```
- Section "Utilisateurs" : tableau avec username, email, rôle, statut actif
  boutons activer/désactiver, formulaire création nouvel utilisateur
- Section "Seuils d'alerte IoT" : formulaire temp_max, temp_min, hum_max, hum_min
- Section "Informations système" : version Flask, version Python, connexion BDD
```

---

## 12. RBAC — CONTRÔLE D'ACCÈS

```
Rôles et permissions :
┌─────────────┬───────────┬──────────┬──────────┬──────────┬──────────┐
│ Route       │ admin     │ analyst  │ operator │ Non auth │
├─────────────┼───────────┼──────────┼──────────┼──────────┤
│ /login      │ ✓         │ ✓        │ ✓        │ ✓        │
│ /dashboard  │ ✓         │ ✓        │ ✓        │ redirect │
│ /incidents  │ ✓         │ ✓        │ ✗        │ redirect │
│ /incidents/new│ ✓       │ ✓        │ ✗        │ redirect │
│ /incidents/<id>│ ✓      │ ✓        │ ✗        │ redirect │
│ /security   │ ✓         │ ✓        │ ✗        │ redirect │
│ /iot        │ ✓         │ ✓        │ ✓        │ redirect │
│ /admin      │ ✓         │ ✗        │ ✗        │ redirect │
│ /api/soar/* │ ✓         │ ✓        │ ✗        │ 401      │
└─────────────┴───────────┴──────────┴──────────┴──────────┘

Implémentation dans utils/decorators.py :
  @login_required         → redirect /login si non authentifié
  @role_required('admin') → abort(403) si rôle insuffisant
  Accepte plusieurs rôles : @role_required('admin', 'analyst')
```

---

## 13. FICHIERS JAVASCRIPT DÉTAILLÉS

### dashboard.js
```javascript
// Polling toutes les 30 secondes
setInterval(async () => {
  const data = await fetch('/api/dashboard/stats').then(r => r.json());
  // Mise à jour des KPI cards sans rechargement
  document.getElementById('kpi-incidents-open').textContent = data.incidents_open;
  document.getElementById('kpi-incidents-critical').textContent = data.incidents_critical;
  document.getElementById('kpi-temp').textContent = data.last_temp + '°C';
  document.getElementById('kpi-hum').textContent = data.last_hum + '%';
}, 30000);
```

### iot.js
```javascript
// Graphique Chart.js double axe Y
// Fetch données depuis /api/iot/readings?hours=24
// Refresh toutes les 60 secondes
// Labels : timestamps formatés en HH:MM
// Dataset 1 : température (rouge), axe Y gauche
// Dataset 2 : humidité (bleu), axe Y droite
```

### incidents.js
```javascript
// Filtres dynamiques : submit du formulaire de filtre via GET
// Confirmation avant actions SOAR (window.confirm)
// Mise à jour statut via fetch POST sans rechargement
```

---

## 14. SCRIPTS UTILITAIRES

### scripts/seed.py
```python
# Doit faire dans l'ordre :
# 1. create_app() pour avoir le contexte Flask
# 2. db.create_all() — crée toutes les tables depuis les modèles
# 3. Insérer les 3 rôles : admin, analyst, operator
# 4. Créer l'utilisateur admin par défaut :
#    username: admin, email: admin@siem.local, password: Admin1234!
# 5. Créer un capteur DHT22 par défaut :
#    name: 'DHT22-RPi5', sensor_type: 'DHT22', 
#    location: 'Salle serveur', raspberry_id: 'rpi5-iot', is_active: True
# 6. Créer les assets des VMs du lab :
#    SRV-AD-PRTG   172.16.1.5   server    wazuh
#    SRV-WAZUH     172.16.1.10  server    wazuh
#    PC-TEST-WIN   172.16.5.5   workstation  manual
#    PC-TEST-LIN   172.16.5.10  workstation  manual
# 7. Afficher un résumé de ce qui a été créé
```

### scripts/sync_wazuh_agents.py
```python
# Appelable manuellement ou via cron (ex: */5 * * * *)
# 1. Appelle wazuh_service.get_agents()
# 2. Pour chaque agent : upsert dans la table assets par hostname
# 3. Logue le nombre d'assets créés/mis à jour
```

---

## 15. TESTS

### tests/test_auth.py
```python
# Tester avec pytest + client Flask de test
# test_login_success          : POST /login avec bons credentials → redirect dashboard
# test_login_wrong_password   : POST /login mauvais mdp → reste sur /login
# test_login_inactive_user    : user is_active=False → accès refusé
# test_logout                 : GET /logout → session détruite
# test_dashboard_requires_auth: GET /dashboard sans session → redirect /login
# test_admin_requires_role    : GET /admin avec rôle operator → 403
```

### tests/test_incidents.py
```python
# test_create_incident        : POST /incidents/new → incident créé en BDD
# test_list_incidents         : GET /incidents → 200, liste visible
# test_filter_by_status       : GET /incidents?status=open → filtre appliqué
# test_add_comment            : POST /incidents/<id>/comment → commentaire créé
# test_soar_upsert_new        : process_wazuh_alert avec nouvel external_id → action='created'
# test_soar_upsert_existing   : process_wazuh_alert avec external_id connu → action='updated'
# test_soar_escalation        : criticité low puis high → escalade confirmée
```

---

## 16. NOTES IMPORTANTES POUR LA GÉNÉRATION

1. **Imports circulaires** : toujours instancier db et login_manager dans extensions.py,
   les importer dans __init__.py APRÈS la définition de create_app(), 
   importer les modèles DANS create_app() (pas au niveau module).

2. **SSL Wazuh/PRTG** : toujours passer verify=False sur les appels requests 
   vers ces APIs (certificats auto-signés en lab). Supprimer les warnings urllib3 
   avec : urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

3. **Bootstrap dark theme** : <html data-bs-theme="dark"> dans base.html.
   Utiliser les classes Bootstrap 5 (pas Bootstrap 4).

4. **Champs criticality vs severity** : dans la table incidents, le champ 
   s'appelle 'criticality'. Dans la table alerts (données Wazuh brutes), 
   le champ s'appelle 'severity'. Ne pas confondre.

5. **Timezone** : toujours utiliser datetime.now(timezone.utc) pour les 
   timestamps, jamais datetime.utcnow() (déprécié en Python 3.12).

6. **CSRF** : activer Flask-WTF pour tous les formulaires POST des templates.
   Les endpoints API (/api/*) doivent être exemptés du CSRF.

7. **Gunicorn** : run.py doit exposer 'app' comme variable globale pour que 
   Gunicorn puisse la trouver avec : gunicorn --workers 4 --bind unix:/run/supervision-app.sock run:app
