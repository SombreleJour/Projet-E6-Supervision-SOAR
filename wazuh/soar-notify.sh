#!/usr/bin/env bash
# Wazuh Active Response — notifie l'API SOAR du dashboard Flask
FLASK_URL="https://172.16.1.15/api/soar/process"
SOAR_TOKEN="token_secret_soar"
LOG="/var/ossec/logs/active-responses.log"

# Wazuh 4.x envoie le contexte en JSON sur stdin
read -r INPUT
TMPFILE=$(mktemp /tmp/wazuh-ar-XXXXXX.json)
echo "$INPUT" > "$TMPFILE"

PAYLOAD=$(python3 - "$TMPFILE" <<'EOF'
import sys, json

with open(sys.argv[1]) as f:
    data = json.load(f)

alert  = data.get('parameters', {}).get('alert', {})
rule   = alert.get('rule',  {})
agent  = alert.get('agent', {})

level = int(rule.get('level', 0))
if   level >= 15: crit = 'critical'
elif level >= 12: crit = 'high'
elif level >= 7:  crit = 'medium'
else:             crit = 'low'

payload = {
    'external_id': alert.get('id', f'wazuh-ar-{level}'),
    'title':       rule.get('description', 'Alerte Wazuh'),
    'description': rule.get('description', ''),
    'rule_id':     str(rule.get('id', '')),
    'source':      agent.get('name', agent.get('ip', 'unknown')),
    'criticality': crit,
    'category':    'security',
}
print(json.dumps(payload))
EOF
)

rm -f "$TMPFILE"

if [ -z "$PAYLOAD" ]; then
    echo "[$(date -u +%FT%TZ)] soar-notify: erreur extraction payload — $INPUT" >> "$LOG"
    exit 1
fi

RESPONSE=$(curl -sk -X POST "$FLASK_URL" \
    -H "Authorization: Bearer $SOAR_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>&1)

echo "[$(date -u +%FT%TZ)] soar-notify: $RESPONSE" >> "$LOG"
exit 0
