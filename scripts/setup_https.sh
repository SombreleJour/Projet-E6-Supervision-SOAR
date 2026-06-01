#!/usr/bin/env bash
#
# setup_https.sh — Met l'app SOC Deletec derrière nginx en HTTPS (cert auto-signé).
#
#   Architecture :  client --HTTPS--> nginx:443 --HTTP--> gunicorn 127.0.0.1:8000
#                   nginx:80 redirige vers :443 (sauf /api/ pour le capteur DHT22)
#
#   À lancer EN ROOT, une seule fois :   sudo bash scripts/setup_https.sh
#   Idempotent : peut être relancé sans danger.
#
set -euo pipefail

# ─────────────────────────── Paramètres ────────────────────────────
DOMAIN="dashboard-supervision-deletec"      # nom de domaine (insensible à la casse)
APP_DIR="/opt/supervision-app"
CERT_DIR="/etc/ssl/${DOMAIN}"
BACKEND="127.0.0.1:8000"
IP_PRIMARY="172.16.1.15"                     # IP réseau maquette
IP_SECONDARY="192.168.63.131"
CERT_DAYS="3650"
SERVICE_FILE="/etc/systemd/system/dashboard.service"

c_ok()   { printf '\033[32m✔\033[0m %s\n' "$*"; }
c_info() { printf '\033[36m▸\033[0m %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "Ce script doit être lancé en root : sudo bash $0"; exit 1; }

# ───────────────────── 1. Paquets nécessaires ──────────────────────
c_info "Installation de nginx + openssl…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx openssl >/dev/null
c_ok "nginx installé."

# ───────────── 2. Certificat auto-signé avec SAN (SubjectAltName) ───
c_info "Génération du certificat auto-signé pour ${DOMAIN}…"
mkdir -p "$CERT_DIR"
SAN_CNF="$(mktemp)"
cat > "$SAN_CNF" <<EOF
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_ext

[dn]
C  = FR
O  = DELETEC
CN = ${DOMAIN}

[v3_ext]
subjectAltName         = @alt_names
basicConstraints       = critical, CA:TRUE
keyUsage               = critical, digitalSignature, keyEncipherment, keyCertSign
extendedKeyUsage       = serverAuth
subjectKeyIdentifier   = hash

[alt_names]
DNS.1 = ${DOMAIN}
DNS.2 = webserver
DNS.3 = localhost
IP.1  = ${IP_PRIMARY}
IP.2  = ${IP_SECONDARY}
IP.3  = 127.0.0.1
EOF

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "${CERT_DIR}/server.key" \
    -out    "${CERT_DIR}/server.crt" \
    -days   "${CERT_DAYS}" \
    -config "$SAN_CNF"
# Export DER (.cer) pour import facile dans le magasin Windows
openssl x509 -in "${CERT_DIR}/server.crt" -outform DER -out "${CERT_DIR}/server.cer"
rm -f "$SAN_CNF"

chmod 600 "${CERT_DIR}/server.key"
chmod 644 "${CERT_DIR}/server.crt" "${CERT_DIR}/server.cer"
c_ok "Certificat : ${CERT_DIR}/server.crt  (clé : server.key, export Windows : server.cer)"

# ───────────────────── 3. Vhost nginx (proxy TLS) ──────────────────
c_info "Configuration de nginx…"
cat > "/etc/nginx/sites-available/${DOMAIN}.conf" <<EOF
# SOC Deletec — reverse proxy TLS -> gunicorn (généré par setup_https.sh)
upstream soc_backend { server ${BACKEND}; }

# ── HTTP :80 ───────────────────────────────────────────────────────
server {
    listen      80 default_server;
    listen      [::]:80 default_server;
    server_name ${DOMAIN} ${IP_PRIMARY} ${IP_SECONDARY} webserver _;

    # Ingestion IoT (capteur DHT22) : reste joignable en HTTP sur :80
    # (auth par token Bearer, réseau interne). À retirer si le capteur passe en HTTPS.
    location /api/ {
        proxy_pass http://soc_backend;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host  \$host;
    }

    # Tout le reste -> HTTPS
    location / { return 301 https://${DOMAIN}\$request_uri; }
}

# ── HTTPS :443 ─────────────────────────────────────────────────────
server {
    listen      443 ssl default_server;
    listen      [::]:443 ssl default_server;
    http2       on;
    server_name ${DOMAIN} ${IP_PRIMARY} ${IP_SECONDARY} webserver _;

    ssl_certificate     ${CERT_DIR}/server.crt;
    ssl_certificate_key ${CERT_DIR}/server.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 4m;

    # Fichiers statiques servis directement par nginx
    location /static/ {
        alias      ${APP_DIR}/app/static/;
        access_log off;
        expires    7d;
    }

    location / {
        proxy_pass http://soc_backend;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host  \$host;
        proxy_redirect   off;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${DOMAIN}.conf" "/etc/nginx/sites-enabled/${DOMAIN}.conf"
rm -f /etc/nginx/sites-enabled/default
c_ok "Vhost nginx en place."

# ──────────── 4. gunicorn : bind local uniquement (127.0.0.1) ───────
if grep -q -- '--bind 0.0.0.0:8000' "$SERVICE_FILE"; then
    c_info "Passage de gunicorn en 127.0.0.1:8000 (plus exposé directement)…"
    cp -a "$SERVICE_FILE" "${SERVICE_FILE}.bak.$(date +%s)"
    sed -i 's|--bind 0.0.0.0:8000|--bind 127.0.0.1:8000|' "$SERVICE_FILE"
    systemctl daemon-reload
    systemctl restart dashboard
    c_ok "Service dashboard relancé sur 127.0.0.1:8000."
else
    c_info "gunicorn déjà en local (ou bind personnalisé) — pas de changement."
fi

# ───────────────── 5. Désactivation d'Apache (libère :80) ──────────
if systemctl is-enabled --quiet apache2 2>/dev/null || systemctl is-active --quiet apache2 2>/dev/null; then
    c_info "Désactivation d'Apache…"
    systemctl disable --now apache2
    c_ok "Apache arrêté et désactivé."
fi

# ───────────────── 6. Activation de nginx ──────────────────────────
c_info "Test de configuration nginx…"
nginx -t
systemctl enable --now nginx
systemctl reload nginx
c_ok "nginx actif."

# ──────── 7. Résolution locale sur la VM (test depuis la VM) ────────
if ! grep -q "[[:space:]]${DOMAIN}\b" /etc/hosts; then
    echo "${IP_PRIMARY} ${DOMAIN}" >> /etc/hosts
    c_ok "Entrée /etc/hosts ajoutée (${IP_PRIMARY} ${DOMAIN})."
fi

echo
c_ok "Terminé."
echo "    → Test local :  curl -k https://${DOMAIN}/   (doit renvoyer la page de connexion)"
echo "    → Cert client :  ${CERT_DIR}/server.cer  (à importer sur les machines hôtes)"
