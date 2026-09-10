# Patches Riven

Fichiers source montés en lecture seule dans le conteneur `riven` (voir
`docker-compose.yml`), par-dessus l'image `spoked/riven:main`. Corrigent des
bugs confirmés en usage réel, en attendant qu'ils soient fusionnés en amont.
À retirer dès que le correctif correspondant revient dans l'image upstream.

| Fichier | Chemin dans le conteneur | Corrige |
|---|---|---|
| `alldebrid.py` | `/riven/src/program/services/downloaders/alldebrid.py` | Le parsing des fichiers AllDebrid (`MagnetInfo.files` sans valeur par défaut) fait échouer la validation pydantic et blackliste à tort des torrents pourtant prêts avec fichiers réels. Correctif équivalent à [rivenmedia/riven#1407](https://github.com/rivenmedia/riven/pull/1407) (mergé puis reverté par erreur en amont). |
| `media_info.py` | `/riven/src/schemas/overseerr/models/media_info.py` | Le client Overseerr généré de Riven n'a pas de champ `status4k` sur `MediaInfo` — une demande Jellyseerr en 4K reste invisible pour Riven (aucune erreur, juste ignorée). Ajoute le champ manquant au schéma. |
| `overseerr_api.py` | `/riven/src/program/apis/overseerr_api.py` | Le filtre "approved" de Riven ne vérifiait que `status`, jamais `status4k` — combiné au patch précédent, les demandes 4K sont maintenant prises en compte. |
| `event_manager.py` | `/riven/src/program/managers/event_manager.py` | `max_workers=1` codé en dur par service (aucun réglage exposé) — le scraping/téléchargement est strictement séquentiel, un seul item à la fois. Passé à `4` : plusieurs items traités en parallèle. |

Ces patches n'ont pas de retour amont formalisé (pas de fork Git, diff local
appliqué en bind-mount) — à surveiller lors des montées de version de l'image
`spoked/riven`, un patch qui ne s'applique plus proprement (fichier renommé/
restructuré en amont) casse silencieusement rien de pire qu'un retour au
comportement par défaut (le fichier patché remplace juste le fichier upstream,
il n'y a pas de mécanisme d'application de diff qui pourrait échouer bruyamment).
