#!/usr/bin/env bash
set -euo pipefail
cd /srv/sjtu-ow
printf 'PRODUCTION-PREFLIGHT UTC=%s\n' "$(date -u +%FT%TZ)"
git status --short --branch
git rev-parse HEAD
df -h .
du -x -h --max-depth=1 /srv/sjtu-ow /root/sjtu-ow-backups /var/lib/docker 2>/dev/null | sort -h
docker system df
docker ps --filter label=com.docker.compose.project=sjtu-ow --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}}'
for service in web worker proxy; do
    container=$(docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env ps -q "$service")
    if [[ -n "$container" ]]; then
        docker inspect --format '{{.Name}} image={{.Image}} {{range .Mounts}}mount={{.Destination}} source={{.Source}} rw={{.RW}} {{end}}' "$container"
    fi
done
docker image ls --filter reference='sjtu-ow*' --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}'
docker volume ls --filter label=com.docker.compose.project=sjtu-ow --format '{{.Name}}'
docker volume ls --filter label=com.docker.compose.project=sjtu-ow-next --format '{{.Name}}'
docker buildx du --format '{{json .}}' > /root/sjtu-ow-301-build-cache.jsonl
printf 'BUILD-CACHE-DESCRIPTORS-SAVED\n'
docker buildx prune --help | head -60
for name in .env.next deploy/docker-compose.next-vps.yml deploy/Caddyfile.next-vps; do
    if [[ -f "$name" ]]; then stat -c '%n mode=%a bytes=%s' "$name"; fi
done
test -f /etc/cron.d/sjtu-ow && printf 'LEGACY-CRON-PRESENT\n'
printf 'PRODUCTION-PREFLIGHT-END\n'
