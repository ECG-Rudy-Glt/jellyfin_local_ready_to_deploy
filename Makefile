.PHONY: init up up-full down restart pull logs ps check clean

# Copie .env.example → .env (si absent), rend DATA_DIR « shared » (sudo) et crée
# la config Decypharr. Voir README §1.
init:
	@[ -f .env ] || { cp .env.example .env; echo "→ .env créé : renseigne au moins DATA_DIR, CACHE_DIR et DEBRID_API_KEY, puis relance 'make init'."; exit 1; }
	@bash scripts/prepare-data-mount.sh
	@bash scripts/init-decypharr-config.sh

up: check
	docker compose up -d
	@set -a; . ./.env; set +a; \
	echo ""; \
	echo "Jellyfin  → http://localhost:$${JELLYFIN_PORT:-8096}"; \
	echo "Seerr     → http://localhost:$${SEERR_PORT:-5055}"; \
	echo "Radarr    → http://localhost:$${RADARR_PORT:-7878}"; \
	echo "Sonarr    → http://localhost:$${SONARR_PORT:-8989}"; \
	echo "Prowlarr  → http://localhost:$${PROWLARR_PORT:-9696}"; \
	echo "Bazarr    → http://localhost:$${BAZARR_PORT:-6767}"; \
	echo "Decypharr → http://localhost:$${DECYPHARR_PORT:-8282}";
	@echo "Suite : README.md §2 « Mise en route »"

up-full: check
	COMPOSE_PROFILES=flaresolverr docker compose up -d

# Refuse de démarrer si DATA_DIR n'est pas shared : sinon Jellyfin et les *arr
# verraient un dossier remote/ vide sans aucune erreur.
check:
	@set -a; . ./.env; set +a; \
	findmnt -no PROPAGATION "$$DATA_DIR" 2>/dev/null | grep -q shared \
	  || { echo "DATA_DIR ($$DATA_DIR) n'est pas en propagation shared : lance 'make init'." >&2; exit 1; }
	@[ -f config/decypharr/config.json ] || { echo "config/decypharr/config.json absent : lance 'make init'." >&2; exit 1; }

down:
	docker compose down

restart:
	docker compose restart

pull:
	docker compose pull

logs:
	docker compose logs -f

ps:
	docker compose ps

# Supprime conteneurs et volumes de configuration. DATA_DIR et CACHE_DIR ne sont
# pas touchés (la bibliothèque n'est faite que de liens, mais autant la garder).
clean:
	docker compose down -v
