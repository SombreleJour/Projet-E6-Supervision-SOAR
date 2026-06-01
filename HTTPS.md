# Accès HTTPS — SOC Deletec

Mise en place d'un accès HTTPS au dashboard via **nginx** (reverse proxy, terminaison TLS)
et un **certificat auto-signé** local, avec résolution par nom de domaine
`dashboard-supervision-deletec`.

## Architecture

```
Client (navigateur)
   │  https://dashboard-supervision-deletec        (TLS — cert auto-signé)
   ▼
nginx  :443   ── termine le TLS, sert /static/ directement
   │  http://127.0.0.1:8000   (+ en-têtes X-Forwarded-*)
   ▼
gunicorn (dashboard.service) ── Flask
   :80 → 301 vers :443        (sauf /api/, laissé en HTTP pour le capteur DHT22)
```

- **nginx** est la seule porte d'entrée réseau ; gunicorn n'écoute plus que sur `127.0.0.1:8000`.
- **Apache** (qui occupait le port 80 avec la page Debian par défaut) est arrêté et désactivé.
- Flask est configuré avec **ProxyFix** pour interpréter correctement les en-têtes
  `X-Forwarded-Proto/Host/For` (schéma HTTPS, IP client réelle, CSRF, cookies).

## 1. Installation (sur la VM `webserver`, en root)

```bash
sudo bash /opt/supervision-app/scripts/setup_https.sh
```

Le script (idempotent) :
1. installe `nginx` et `openssl` ;
2. génère le certificat auto-signé avec SAN dans `/etc/ssl/dashboard-supervision-deletec/`
   (`server.crt`, `server.key`, et `server.cer` au format DER pour Windows) ;
3. installe le vhost nginx (proxy TLS + redirection 80→443 + `/api/` en HTTP) ;
4. repasse gunicorn en `127.0.0.1:8000` (sauvegarde de l'unité systemd au préalable) ;
5. arrête/désactive Apache ;
6. active et recharge nginx ;
7. ajoute `172.16.1.15 dashboard-supervision-deletec` dans `/etc/hosts` de la VM.

## 2. Test depuis la VM elle-même

```bash
# Connexion TLS + vérif du certificat et de ses SAN
openssl s_client -connect 127.0.0.1:443 -servername dashboard-supervision-deletec </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName

# Page de connexion (–k = ignore la confiance, normal pour un cert auto-signé non encore importé)
curl -k -I https://dashboard-supervision-deletec/
curl -k    https://dashboard-supervision-deletec/ | head

# La redirection HTTP→HTTPS
curl -I http://dashboard-supervision-deletec/      # -> 301 vers https
```

Attendu : `HTTP/2 200` sur la page de login en HTTPS, `301` en HTTP.

## 3. Résolution DNS sur le Windows Server 2022

Le nom `dashboard-supervision-deletec` doit pointer vers **172.16.1.15**. On crée une
zone dédiée pour que ce **nom à label unique** résolve tel quel.

### Créer la zone + l'enregistrement A

1. Sur le Windows Server : **Gestionnaire de serveur → Outils → DNS** (ou `dnsmgmt.msc`).
2. Déplier le serveur → clic droit sur **Zones de recherche directe** → **Nouvelle zone…**
   - Type : **Zone principale** (cocher « Stocker dans AD » si contrôleur de domaine).
   - Nom de la zone : `dashboard-supervision-deletec`
   - Terminer.
3. Clic droit sur la zone créée → **Nouvel hôte (A ou AAAA)…**
   - **Nom** : *laisser vide* (= sommet de la zone, donc le nom lui-même).
   - **Adresse IP** : `172.16.1.15`
   - **Ajouter l'hôte**.

### Côté clients

- Les machines clientes doivent utiliser **ce serveur DNS** (Windows Server) comme résolveur
  (Paramètres carte réseau → DNS = IP du Windows Server).
- Vérifier la résolution :
  ```cmd
  nslookup dashboard-supervision-deletec
  ping dashboard-supervision-deletec
  ```
  doit renvoyer `172.16.1.15`.
- Dans le navigateur, taper l'URL **avec le schéma** pour forcer la navigation (sinon le
  navigateur peut interpréter un mot seul comme une recherche) :
  `https://dashboard-supervision-deletec`

### Alternative (nom pleinement qualifié — recommandé si domaine AD)

Si tu as déjà une zone AD (ex. `deletec.local`), tu peux à la place créer l'enregistrement A
`dashboard-supervision-deletec` **dans cette zone** → FQDN
`dashboard-supervision-deletec.deletec.local`. Les clients membres du domaine résolvent alors
le nom court automatiquement (suffixe DNS). Dans ce cas, **préviens-moi du domaine** : il faut
ajouter le FQDN aux SAN du certificat (sinon le navigateur refusera le nom complet) et le
régénérer.

## 4. Faire confiance au certificat sur les machines hôtes

Tant que le certificat auto-signé n'est pas importé, le navigateur affiche un avertissement.
Récupérer `server.cer` depuis la VM (`/etc/ssl/dashboard-supervision-deletec/server.cer`),
puis :

### Windows (par machine)

1. Double-clic sur `server.cer` → **Installer le certificat**.
2. Emplacement : **Ordinateur local** (pas « Utilisateur actuel »).
3. **Placer tous les certificats dans le magasin suivant** →
   **Autorités de certification racines de confiance**.
4. Terminer, puis redémarrer le navigateur. (Chrome/Edge utilisent le magasin Windows ;
   **Firefox a son propre magasin** → l'importer aussi via Paramètres → Vie privée → Certificats.)

### Windows (toutes les machines via GPO — recommandé pour la maquette)

`Configuration ordinateur → Stratégies → Paramètres Windows → Paramètres de sécurité →
Stratégies de clé publique → Autorités de certification racines de confiance` →
clic droit → **Importer** → `server.cer`. Les clients du domaine l'appliquent automatiquement.

### Linux (client)

```bash
sudo cp server.crt /usr/local/share/ca-certificates/dashboard-supervision-deletec.crt
sudo update-ca-certificates
```

## 5. Note — capteur IoT (DHT22)

Le collecteur poste sur `http://172.16.1.15/api/iot/readings`. Le vhost laisse `/api/`
joignable en **HTTP sur le port 80** (auth par token Bearer), donc l'ingestion continue de
fonctionner sans toucher au Raspberry Pi. Pour passer aussi le capteur en HTTPS plus tard :
importer `server.crt` sur le Pi (ou `verify=False` côté script), pointer `API_URL` sur
`https://dashboard-supervision-deletec/api/iot/readings`, puis retirer le bloc `/api/` du
`server { listen 80; }` dans le vhost nginx.

## Dépannage

| Symptôme | Piste |
|---|---|
| `curl` renvoie 502 Bad Gateway | gunicorn (`dashboard.service`) arrêté → `systemctl status dashboard` |
| Avertissement de certificat | cert non importé sur le client (voir §4) ; vérifier que l'URL = un SAN |
| Le nom ne résout pas | DNS client mal réglé / zone absente (voir §3) ; tester `nslookup` |
| CSS/JS cassés | droits de lecture nginx sur `/opt/supervision-app/app/static` (755/644) |
| 301 en boucle | accès via un nom absent des SAN ; utiliser `dashboard-supervision-deletec` |
