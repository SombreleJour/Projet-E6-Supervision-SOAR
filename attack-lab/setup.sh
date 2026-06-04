#!/bin/bash
# A lancer une seule fois sur la VM Debian attaquante (en root)
apt-get update -qq
apt-get install -y --no-install-recommends nmap hydra python3 curl git ca-certificates

# rockyou (utile pour hydra)
if [ ! -f /usr/share/wordlists/rockyou.txt ]; then
    if [ -f /usr/share/wordlists/rockyou.txt.gz ]; then
        gunzip /usr/share/wordlists/rockyou.txt.gz
    fi
fi

echo "[OK] Outils installes"
