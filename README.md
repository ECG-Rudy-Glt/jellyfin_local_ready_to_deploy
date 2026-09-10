# Jellyfin + Riven — stack média prête à déployer

![docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)
![ansible](https://img.shields.io/badge/ansible-optional-EE0000?logo=ansible&logoColor=white)
![jellyfin](https://img.shields.io/badge/jellyfin-media%20server-00A4DC?logo=jellyfin&logoColor=white)
![self-hosted](https://img.shields.io/badge/self--hosted-yes-blue)
![license](https://img.shields.io/badge/usage-personal-lightgrey)

`jellyfin` · `riven` · `jellyseerr` · `prowlarr` · `zilean` · `docker-compose` · `ansible` · `self-hosted` · `media-server` · `debrid`

Déploiement conteneurisé complet d'un serveur média personnel : recherche +
demande de contenu ([Jellyseerr](https://github.com/fallenbagel/jellyseerr)),
acquisition automatisée via un débrideur cloud
([Riven](https://github.com/rivenmedia/riven) + [Zilean](https://github.com/iPromKnight/zilean)
+ [Prowlarr](https://github.com/Prowlarr/Prowlarr)), lecture/transcodage
([Jellyfin](https://jellyfin.org)). Zéro code custom applicatif — que de la
configuration, plus quelques correctifs source ciblés documentés dans
[patches/](patches/README.md).

**Comment ça s'articule** : voir [ARCHITECTURE.md](ARCHITECTURE.md) (diagramme,
rôle de chaque service, et surtout la section "piège du montage média" —
à lire avant de déployer si tu veux comprendre pourquoi c'est structuré ainsi).

## Prérequis

- Docker + Docker Compose v2 (`docker compose version`)
- Module noyau `fuse` chargé (`modprobe fuse` si `/dev/fuse` n'existe pas)
- Un compte débrideur payant : [AllDebrid](https://alldebrid.com) ou
  [Real-Debrid](https://real-debrid.com) (~4€/mois) — **obligatoire**, Riven
  trouve des sources mais ne peut rien télécharger sans ça
- `sudo` (pour le montage média partagé, voir `make init`)
- Optionnel : `ansible-galaxy` + collection `community.docker`, seulement si tu
  préfères le chemin Ansible à `make`

## 1. Démarrage rapide (`make`)

```bash
git clone https://github.com/ECG-Rudy-Glt/jellyfin_local_ready_to_deploy.git
cd jellyfin_local_ready_to_deploy
make init      # copie .env.example → .env, prépare le montage média (sudo)
$EDITOR .env   # au moins ALLDEBRID_API_KEY, RIVEN_BACKEND_API_KEY, RIVEN_AUTH_SECRET
make up        # lance toute la stack
```

Les deux secrets internes se génèrent avec :

```bash
openssl rand -hex 16      # → RIVEN_BACKEND_API_KEY
openssl rand -base64 32   # → RIVEN_AUTH_SECRET
```

Commandes utiles : `make logs`, `make ps`, `make down`, `make restart`,
`make clean` (supprime aussi les volumes de config — jamais les médias).

### Alternative — Ansible

Même résultat, si tu préfères un playbook idempotent (utile pour redéployer
sur une autre machine, ou intégrer à une infra existante) :

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
cp ../.env.example ../.env && $EDITOR ../.env
ansible-playbook deploy-media-stack.yml
```

Pour arrêter/supprimer : `ansible-playbook deploy-media-stack.yml -e media_stack_state=absent`.

## 2. Le montage média — une étape avant le premier démarrage

Riven et Jellyfin doivent voir le **même** répertoire média avec la bonne
propagation de montage (`rshared`), sinon Jellyfin ne verra jamais les
fichiers exposés par Riven. `make init` (ou le playbook Ansible) le fait pour
toi. Détail technique complet : [ARCHITECTURE.md § Le piège du montage
média](ARCHITECTURE.md#le-piège-du-montage-média).

## 3. Mise en route (après `make up`)

Les clés API ci-dessous n'existent qu'une fois chaque service démarré une
première fois — c'est normal que `.env` ne les ait pas dès le départ.

1. **Jellyfin** — [http://localhost:8096](http://localhost:8096) : assistant
   de première configuration (compte admin, langue). Une fois fait :
   `Dashboard → API Keys` → créer une clé → coller dans `.env`
   (`JELLYFIN_API_KEY`). Crée aussi une bibliothèque pointant sur `/media`
   (montée en lecture seule — normal qu'elle soit vide tant que Riven n'a rien
   téléchargé).
2. **Riven frontend** — [http://localhost:3000](http://localhost:3000) :
   onboarding (confirme l'URL du backend, déjà pré-rempli). C'est l'UI admin
   pour suivre l'état des téléchargements — les utilisateurs finaux passent
   par Jellyseerr (étape 5), pas par ici.
3. **Prowlarr** — [http://localhost:9696](http://localhost:9696) : ajoute
   quelques indexeurs publics (`Indexers → Add Indexer`, filtre "Public").
   Puis `Settings → General → API Key` → coller dans `.env`
   (`PROWLARR_API_KEY`).
4. Redémarrer pour propager les clés qui viennent d'être renseignées :
   ```bash
   docker compose up -d   # ou : ansible-playbook ansible/deploy-media-stack.yml
   ```
5. **Jellyseerr** — [http://localhost:5055](http://localhost:5055) :
   assistant de configuration → connecte-le à Jellyfin (`http://jellyfin:8096`,
   nom du service Docker, pas `localhost`) → puis `Settings → General → API
   Key` (format base64, **pas** celle de l'onglet Jellyfin) → coller dans
   `.env` (`JELLYSEERR_API_KEY`) → `docker compose up -d` une dernière fois.

6. **(Optionnel mais recommandé) Garde-fous** — une fois `JELLYFIN_API_KEY` et
   `RIVEN_BACKEND_API_KEY` dans `.env` :
   ```bash
   make guards   # ou : ansible-playbook ansible/deploy-media-stack.yml --tags guards
   ```
   Voir [ARCHITECTURE.md § Garde-fous](ARCHITECTURE.md#garde-fous-scripts) pour
   ce que chacun fait.

## 4. Tester

Depuis Jellyseerr, cherche un titre et demande-le. Suis la progression côté
Riven frontend (`http://localhost:3000`) : `Requested → Indexed → Scraped →
Downloaded`. Une fois `Downloaded`/`Completed`, le fichier doit apparaître
dans Jellyfin après son prochain scan (déclenché automatiquement par Riven via
l'updater, ou manuellement `Dashboard → Bibliothèques → Analyser tout`).

## Structure

```
docker-compose.yml         jellyfin + riven (backend/frontend/db) + zilean + prowlarr + jellyseerr
.env.example                toutes les variables commentées
Makefile                    make init / up / down / guards / logs / clean
ARCHITECTURE.md              diagramme, rôle de chaque service, montage média, garde-fous
patches/                     4 correctifs source Riven (bugs upstream confirmés), voir patches/README.md
scripts/                     garde-fous Python (timers systemd) + scripts shell d'installation
ansible/                     playbook équivalent à `make`, si tu préfères Ansible
data/                        médias + caches (bind mounts) — créé au premier lancement, ignoré par git
```

## Notes

- Usage personnel : respecte le droit d'auteur applicable dans ta juridiction
  pour le contenu que tu acquiers via cette stack.
- Ne commite jamais `.env` (déjà dans `.gitignore`) — il contient des clés une
  fois l'onboarding fait.
- `MEDIA_DIR`/`*_CACHE_DIR` sont des bind mounts (pas des volumes Docker
  nommés) — volontaire, voir [ARCHITECTURE.md](ARCHITECTURE.md) : les
  garde-fous ont besoin d'un chemin hôte direct.
