#!/usr/bin/env bash
#
# deploy.sh — Déploiement complet de l'application Supervision SOC Deletec
#             sur une VM Debian (full CLI). Idempotent : peut être relancé.
#
# Ce qu'il fait :
#   1. Installe les paquets système (Python, PostgreSQL, git, curl…)
#   2. Provisionne l'application dans /opt/supervision-app (copie/pull du dépôt)
#   3. Crée l'utilisateur système 'dashboard' qui exécute le service
#   4. Génère un .env complet (SECRET_KEY + mot de passe DB aléatoires) s'il manque
#   5. Crée le rôle + la base PostgreSQL et les synchronise avec le .env
#   6. Crée le venv, installe les dépendances, initialise la base (seed)
#   7. Installe + active le service systemd (gunicorn, démarrage auto)
#   8. Installe Claude Code (installeur natif Anthropic) pour l'utilisateur courant
#
# Usage :
#   sudo bash scripts/deploy.sh
#
set -euo pipefail

# ─────────────────────────── Paramètres ────────────────────────────
APP_DIR="/opt/supervision-app"
APP_USER="dashboard"                   # utilisateur système qui exécute le service
SERVICE_NAME="dashboard"
SERVICE_PORT="8000"
DB_NAME="supervision_db"
DB_USER="supervision_user"
REPO_URL="https://github.com/SombreleJour/Projet-E6-Supervision-SOAR.git"

# Répertoire source = racine du dépôt (parent de scripts/)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Utilisateur humain pour qui installer Claude Code (celui qui a lancé sudo)
CLAUDE_USER="${SUDO_USER:-$(id -un)}"

# ─────────────────────────── Helpers ───────────────────────────────
log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ ok ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[fail]\033[0m %s\n' "$*" >&2; }

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    err "Ce script doit être lancé avec sudo/root (apt, systemd, postgres, /opt)."
    exit 1
  fi
}

# ─────────────────────── 0. Pré-vérifications ──────────────────────
require_root
log "Source du dépôt : $SRC_DIR"
log "Cible           : $APP_DIR"
log "Service         : ${SERVICE_NAME}.service (port ${SERVICE_PORT})"
log "Claude Code pour: $CLAUDE_USER"

# ─────────────────────── 1. Paquets système ────────────────────────
log "Installation des paquets système…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    git curl ca-certificates openssl rsync
systemctl enable --now postgresql >/dev/null 2>&1 || true
ok "Paquets installés."

# ─────────────────── 2. Utilisateur système de service ─────────────
if ! id "$APP_USER" >/dev/null 2>&1; then
  log "Création de l'utilisateur système '$APP_USER'…"
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
ok "Utilisateur '$APP_USER' présent."

# ─────────────────── 3. Code dans /opt/supervision-app ─────────────
if [[ -d "$APP_DIR/.git" ]]; then
  log "Dépôt déjà présent — git pull…"
  git config --global --add safe.directory "$APP_DIR" || true
  git -C "$APP_DIR" pull --ff-only || warn "git pull a échoué (réseau ?) — on continue."
elif [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  log "Copie du dépôt vers $APP_DIR…"
  mkdir -p "$APP_DIR"
  rsync -a --exclude 'venv' --exclude '__pycache__' "$SRC_DIR/." "$APP_DIR/"
else
  log "Le script tourne déjà depuis $APP_DIR."
fi
ok "Code en place dans $APP_DIR."

cd "$APP_DIR"

# ─────────────────── 4. Fichier .env (généré si absent) ────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
  log "Création de .env à partir de .env.example…"
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

# SECRET_KEY : remplace le placeholder par une valeur aléatoire
if grep -q 'change_me_in_production' "$APP_DIR/.env"; then
  SECRET_KEY="$(openssl rand -hex 32)"
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$APP_DIR/.env"
  ok "SECRET_KEY générée."
fi

# DATABASE_URL : remplace le placeholder MOTDEPASSE par un mot de passe aléatoire
if grep -q 'MOTDEPASSE@' "$APP_DIR/.env"; then
  DB_PASS="$(openssl rand -hex 16)"   # hex => aucun caractère spécial dans l'URL
  DB_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DB_URL}|" "$APP_DIR/.env"
  ok "DATABASE_URL générée (mot de passe DB aléatoire)."
fi

# Lecture de la valeur finale du .env (source de vérité)
DATABASE_URL="$(grep -E '^DATABASE_URL=' "$APP_DIR/.env" | head -n1 | cut -d= -f2-)"
# Parsing postgresql://USER:PASS@HOST:PORT/DBNAME
_u="${DATABASE_URL#postgresql://}"
_creds="${_u%@*}"
_hostpart="${_u#*@}"
DB_USER="${_creds%%:*}"
DB_PASS="${_creds#*:}"
DB_NAME="${_hostpart##*/}"

chmod 600 "$APP_DIR/.env"

# ─────────────────── 5. PostgreSQL : rôle + base ───────────────────
log "Configuration PostgreSQL (rôle '$DB_USER', base '$DB_NAME')…"
role_exists="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" || true)"
if [[ "$role_exists" == "1" ]]; then
  sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASS}';" >/dev/null
else
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';" >/dev/null
fi
db_exists="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" || true)"
if [[ "$db_exists" != "1" ]]; then
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
fi
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" >/dev/null
ok "PostgreSQL prêt."

# ─────────────────── 6. venv + dépendances + seed ──────────────────
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

if [[ ! -d "$APP_DIR/venv" ]]; then
  log "Création du virtualenv…"
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
fi
log "Installation des dépendances Python…"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
ok "Dépendances installées."

log "Initialisation de la base (tables + admin + données de démo)…"
sudo -u "$APP_USER" bash -c "cd '$APP_DIR' && '$APP_DIR/venv/bin/python' scripts/seed.py"
ok "Base initialisée."

# ─────────────────── 7. Service systemd ────────────────────────────
log "Installation du service systemd…"
install -m 0644 "$APP_DIR/scripts/dashboard.service" "/etc/systemd/system/${SERVICE_NAME}.service"
# Aligne le port si modifié dans ce script
if [[ "$SERVICE_PORT" != "8000" ]]; then
  sed -i "s|0.0.0.0:8000|0.0.0.0:${SERVICE_PORT}|" "/etc/systemd/system/${SERVICE_NAME}.service"
fi
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
  ok "Service '${SERVICE_NAME}' actif."
else
  warn "Le service n'est pas actif — voir : journalctl -u ${SERVICE_NAME} -n 50"
fi

# Ouvre le port si ufw est actif
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow "${SERVICE_PORT}/tcp" >/dev/null 2>&1 || true
  ok "Port ${SERVICE_PORT} autorisé dans ufw."
fi

# ─────────────────── 8. Installation de Claude Code ────────────────
log "Installation de Claude Code pour l'utilisateur '$CLAUDE_USER'…"
if [[ "$CLAUDE_USER" == "root" ]]; then
  if curl -fsSL https://claude.ai/install.sh | bash; then
    ok "Claude Code installé pour root (~/.local/bin/claude)."
  else
    warn "Échec de l'installation de Claude Code (réseau Internet requis)."
  fi
else
  if sudo -u "$CLAUDE_USER" --login bash -c 'curl -fsSL https://claude.ai/install.sh | bash'; then
    ok "Claude Code installé pour '$CLAUDE_USER' (~/.local/bin/claude)."
  else
    warn "Échec de l'installation de Claude Code (réseau Internet requis)."
  fi
fi

# ─────────────────────────── Résumé ────────────────────────────────
IP_ADDR="$(hostname -I 2>/dev/null | awk '{print $1}')"
cat <<EOF

──────────────────────────────────────────────────────────────────
 DÉPLOIEMENT TERMINÉ
──────────────────────────────────────────────────────────────────
 Application : http://${IP_ADDR:-<IP_VM>}:${SERVICE_PORT}
 Login       : admin  /  Admin1234!   (à changer après la 1re connexion)

 Service     : systemctl status ${SERVICE_NAME}
 Logs        : journalctl -u ${SERVICE_NAME} -f
 Redémarrer  : sudo systemctl restart ${SERVICE_NAME}

 À FAIRE :
  • Éditer /opt/supervision-app/.env pour les accès PRTG/Wazuh/pfSense et
    le IOT_API_TOKEN (doit correspondre au TOKEN dans dht22_collector.py),
    puis : sudo systemctl restart ${SERVICE_NAME}
  • Claude Code : lancer 'claude' puis suivre le lien de connexion.
    (VM headless : ouvrez l'URL affichée sur un PC avec navigateur,
     autorisez, puis collez le code dans le terminal.)
    Si 'claude' est introuvable : rouvrez la session ou
    export PATH="\$HOME/.local/bin:\$PATH"
──────────────────────────────────────────────────────────────────
EOF
