# Jellyfin + stack *arr + débrideur, prête à déployer

![docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)
![ansible](https://img.shields.io/badge/ansible-optional-EE0000?logo=ansible&logoColor=white)
![jellyfin](https://img.shields.io/badge/jellyfin-media%20server-00A4DC?logo=jellyfin&logoColor=white)
![self-hosted](https://img.shields.io/badge/self--hosted-yes-blue)

`jellyfin` · `seerr` · `radarr` · `sonarr` · `prowlarr` · `bazarr` · `decypharr` · `docker-compose` · `ansible` · `self-hosted` · `debrid`

Serveur média personnel sans stockage local : les demandes passent par
[Seerr](https://github.com/seerr-team/seerr), [Radarr](https://radarr.video) et
[Sonarr](https://sonarr.tv) gèrent les bibliothèques,
[Decypharr](https://github.com/sirrobot01/decypharr) confie les fichiers à un débrideur
et les monte comme un disque local, [Jellyfin](https://jellyfin.org) les lit.

Tout est configuration : aucun code applicatif maison. Le fonctionnement et ses pièges
sont expliqués dans [ARCHITECTURE.md](ARCHITECTURE.md).

> **v2 (septembre 2026)** : la v1 reposait sur Riven, abandonné par ses mainteneurs.
> Elle reste disponible sous le tag [`v1-riven`](../../tree/v1-riven).

## Prérequis

- Linux avec Docker et Docker Compose v2 (`docker compose version`)
- Module noyau FUSE (`ls /dev/fuse`, sinon `modprobe fuse`)
- `sudo` pour préparer le montage partagé
- Un compte chez un débrideur supporté par Decypharr (AllDebrid, Real-Debrid, TorBox,
  Premiumize, Debrid-Link) : **payant et obligatoire**
- Optionnel : Ansible avec les collections de `ansible/requirements.yml`

## 1. Installation

```bash
git clone https://github.com/ECG-Rudy-Glt/jellyfin_local_ready_to_deploy.git
cd jellyfin_local_ready_to_deploy
make init        # crée .env et s'arrête : renseigne-le
$EDITOR .env     # DATA_DIR et CACHE_DIR (chemins absolus), DEBRID_PROVIDER, DEBRID_API_KEY
make init        # prépare le montage partagé (sudo) et la config Decypharr
make up
```

`make init` doit être relancé après chaque redémarrage de l'hôte (voir
[ARCHITECTURE.md § Le piège du montage](ARCHITECTURE.md#le-piège-du-montage)), sauf si tu
utilises le playbook Ansible, qui installe une unité systemd pour ça.

Autres commandes : `make up-full` (avec FlareSolverr), `make logs`, `make ps`, `make pull`,
`make down`, `make clean` (supprime aussi les configurations, jamais `DATA_DIR`).

### Alternative : Ansible

```bash
cd ansible
ansible-galaxy collection install -r requirements.yml
cp ../.env.example ../.env && $EDITOR ../.env
ansible-playbook deploy-media-stack.yml            # -e target=mon-hote pour une autre machine
```

## 2. Mise en route

Les services se configurent dans leur interface. Entre conteneurs, utilise toujours le nom
du service (`http://radarr:7878`), jamais `localhost`. Chaque clé API se trouve dans
*Settings → General* du service concerné.

1. **Decypharr** ([:8282](http://localhost:8282)) : vérifie que le débrideur apparaît
   connecté. Si l'hôte est accessible par d'autres machines, active l'authentification
   (*Settings → Auth*).
2. **Radarr** ([:7878](http://localhost:7878)) et **Sonarr** ([:8989](http://localhost:8989)) :
   - *Media Management* → dossier racine `/data/media/movies` (Radarr) ou `/data/media/tv` (Sonarr)
   - *Media Management* → garde **Use Hardlinks instead of Copy** activé (valeur par défaut).
     Un lien dur vers un lien symbolique reste un lien ; une copie, elle, téléchargerait le
     fichier entier
   - *Download Clients* → **qBittorrent** : hôte `decypharr`, port `8282`,
     utilisateur `http://radarr:7878` (ou `http://sonarr:8989`), mot de passe = clé API
     de ce même Radarr/Sonarr, catégorie `radarr` (ou `sonarr`)
   - *Connect* → **Jellyfin** (`http://jellyfin:8096` + clé API Jellyfin) : Jellyfin est
     prévenu à chaque import
3. **Prowlarr** ([:9696](http://localhost:9696)) : ajoute les indexeurs de ton choix, puis
   *Settings → Apps* → Radarr et Sonarr (adresse + clé API). Les indexeurs sont alors
   synchronisés automatiquement. Avec FlareSolverr : *Settings → Indexers* → proxy
   `http://flaresolverr:8191`, avec un tag à poser sur les indexeurs concernés.
4. **Jellyfin** ([:8096](http://localhost:8096)) : assistant de départ, puis deux
   bibliothèques, `/data/media/movies` et `/data/media/tv`. Dans leurs options,
   désactive la génération de trickplay et l'extraction des images de chapitres (voir
   [les conseils d'exploitation](ARCHITECTURE.md#conseils-dexploitation)).
5. **Seerr** ([:5055](http://localhost:5055)) : connexion à Jellyfin (`http://jellyfin:8096`),
   puis ajout de Radarr et Sonarr avec leurs dossiers racine et profils de qualité.
6. **Bazarr** ([:6767](http://localhost:6767)) : connexion à Radarr et Sonarr, langues
   voulues, fournisseurs de sous-titres.

## 3. Tester

Dans Seerr, demande un film. Il doit apparaître dans la file de Radarr (*Activity*), puis
dans Decypharr, puis comme lien dans `DATA_DIR/media/movies`, et enfin dans Jellyfin. Pour
un contenu déjà présent dans le cache du débrideur, comptez moins d'une minute.

## Structure

```
docker-compose.yml               tous les services
.env.example                     variables commentées
config/decypharr/*.example       config Decypharr (sans secret : la clé reste dans .env)
scripts/prepare-data-mount.sh    montage partagé de DATA_DIR (bind + rshared)
scripts/init-decypharr-config.sh génère config/decypharr/config.json
ansible/                         playbook équivalent à make init + make up
ARCHITECTURE.md                  schéma, chemins, piège du montage, conseils d'exploitation
```

## Notes

- Usage personnel : respecte le droit d'auteur applicable là où tu vis pour le contenu que
  tu demandes via cette stack. Aucun indexeur n'est fourni ni recommandé.
- `.env` et `config/decypharr/config.json` ne doivent jamais être commités (déjà dans
  `.gitignore`).
