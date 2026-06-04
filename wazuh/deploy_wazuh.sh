#!/bin/bash
# ============================================================
#  DEPLOY SOAR sur manager Wazuh — a executer sur ubuntu-server
#  (172.16.1.10) en tant que root
# ============================================================
set -e

OSSEC_CONF="/var/ossec/etc/ossec.conf"
AR_BIN="/var/ossec/active-response/bin"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploy SOAR Wazuh ==="

# 1. Copier soar-notify.sh sur le manager
echo "[1/4] Deploiement soar-notify.sh..."
cp "$SCRIPT_DIR/soar-notify.sh" "$AR_BIN/soar-notify.sh"
chmod 750 "$AR_BIN/soar-notify.sh"
chown root:wazuh "$AR_BIN/soar-notify.sh"
echo "      OK -> $AR_BIN/soar-notify.sh"

# 2. Corriger active-response dans ossec.conf :
#    - location local  -> server
#    - level 11        -> 10
echo "[2/4] Correction ossec.conf..."
cp "$OSSEC_CONF" "${OSSEC_CONF}.bak_$(date +%Y%m%d_%H%M%S)"

python3 - "$OSSEC_CONF" << 'EOF'
import sys, re

with open(sys.argv[1]) as f:
    content = f.read()

# Changer location local -> server pour soar-notify
# On cible le bloc active-response contenant soar-notify
def fix_soar_ar(text):
    # Remplacer <location>local</location> dans le bloc soar-notify
    pattern = r'(<active-response>(?:(?!</active-response>).)*?soar-notify(?:(?!</active-response>).)*?)<location>\s*local\s*</location>'
    replacement = r'\1<location>server</location>'
    text = re.sub(pattern, replacement, text, flags=re.DOTALL)
    # Abaisser le level de 11 a 10 dans le bloc soar-notify
    pattern2 = r'(<active-response>(?:(?!</active-response>).)*?soar-notify(?:(?!</active-response>).)*?)<level>\s*11\s*</level>'
    replacement2 = r'\1<level>10</level>'
    text = re.sub(pattern2, replacement2, text, flags=re.DOTALL)
    return text

new_content = fix_soar_ar(content)
if new_content == content:
    print("  WARN: aucune modification detectee (config deja correcte ?)")
else:
    with open(sys.argv[1], 'w') as f:
        f.write(new_content)
    print("  ossec.conf mis a jour (location=server, level=10)")
EOF

# 3. Valider la config (wazuh-analysisd -t = test de syntaxe ossec.conf)
echo "[3/4] Validation de la config..."
VALIDATE_OUT=$(/var/ossec/bin/wazuh-analysisd -t 2>&1)
VALIDATE_RC=$?
if [ $VALIDATE_RC -eq 0 ]; then
    echo "      Config valide"
else
    echo "      ERREUR config (rc=$VALIDATE_RC) :"
    echo "$VALIDATE_OUT"
    LATEST_BAK=$(ls -t "${OSSEC_CONF}.bak_"* 2>/dev/null | head -1)
    [ -n "$LATEST_BAK" ] && cp "$LATEST_BAK" "$OSSEC_CONF" && echo "      Backup restaure: $LATEST_BAK"
    exit 1
fi

# 4. Redemarrer le manager
echo "[4/4] Redemarrage wazuh-manager..."
systemctl restart wazuh-manager
sleep 3
systemctl is-active wazuh-manager && echo "      wazuh-manager ACTIF" || echo "      ERREUR demarrage"

echo ""
echo "=== Deploy termine ==="
echo "Verifier les logs : tail -f /var/ossec/logs/active-responses.log"
