# Attack Lab — Test SOAR Wazuh

**Usage pedagogique uniquement — BTS CIEL IR**

## Config VM Debian attaquante

| Parametre  | Valeur                          |
|------------|---------------------------------|
| OS         | Debian 12 Bookworm (netinstall) |
| CPU        | 1 vCPU                          |
| RAM        | 512 MB                          |
| Disque     | 8 GB                            |
| Reseau     | 1 carte — 172.16.1.x            |
| IP statique| 172.16.1.50 (suggeree)          |

A l'installation : cocher uniquement `SSH server` + `standard system utilities` (pas de desktop).

## Premiere utilisation

```bash
git clone <ce-repo>
cd supervision-app/attack-lab
chmod +x setup.sh attack.sh
sudo ./setup.sh                  # installe nmap, hydra
sudo ./attack.sh 172.16.1.20     # remplace par l IP reelle de WIN10-test
```

## Flux complet attendu

```
VM Debian (172.16.1.50)
    -> brute-force SSH/RDP -> WIN10-test (172.16.1.20)
                                    |
                        Wazuh agent detecte (regle 5763 high)
                                    |
                        Wazuh manager -> active-response -> soar-notify.sh
                                    |
                        POST /soar/process -> dashboard Flask
                                    |
                        isolate_host() -> firewall-drop via API Wazuh
                                    |
                        PRTG verifie -> incident affiche dans dashboard
```

## Regles Wazuh declenchees

| Regle | Description                    | Level | Criticite |
|-------|--------------------------------|-------|-----------|
| 5551  | SSH auth failures multiples    | 10    | high      |
| 5763  | SSH brute-force detecte        | 10    | high      |
| 60122 | Windows RDP auth failures      | 10    | high      |
