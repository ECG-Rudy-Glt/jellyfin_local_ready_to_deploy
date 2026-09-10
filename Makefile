.PHONY: init up down restart logs ps guards clean

# Copie .env.example → .env (si absent) et prépare le montage média partagé
# entre Riven et Jellyfin (bind + rshared, demande sudo). Voir README §2.
init:
	@[ -f .env ] || cp .env.example .env
	@echo "→ .env prêt. Édite-le (au moins ALLDEBRID_API_KEY, RIVEN_BACKEND_API_KEY, RIVEN_AUTH_SECRET) avant 'make up'."
	@bash scripts/prepare-media-mount.sh

up:
	docker compose up -d
	@bash scripts/init-zilean-db.sh
	@echo ""
	@echo "Jellyfin   → http://localhost:8096"
	@echo "Riven      → http://localhost:8080  (front : http://localhost:3000)"
	@echo "Prowlarr   → http://localhost:9696"
	@echo "Jellyseerr → http://localhost:5055"
	@echo "Prochaine étape : README.md §3 « Mise en route »"

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

# À lancer une fois l'onboarding terminé (README §3) et .env complété
# (JELLYFIN_API_KEY, RIVEN_BACKEND_API_KEY) — installe les garde-fous en
# timers systemd. Alternative : ansible/deploy-media-stack.yml --tags guards.
guards:
	@bash scripts/install-guards.sh

# Supprime conteneurs + volumes nommés (config Jellyfin/Riven/Prowlarr/Jellyseerr,
# DB). Les données média (MEDIA_DIR) et caches (bind mounts) ne sont PAS touchés.
clean:
	docker compose down -v
