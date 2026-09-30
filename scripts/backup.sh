#!/usr/bin/env bash
# Backup de Zabbix: volcado de la base (gzip) + export YAML de templates/mapa.
# Uso:  scripts/backup.sh [directorio_destino]      (por defecto ./backups)
# Retención: borra backups de más de RETENCION_DIAS (por defecto 14).
# Programar diario (cron en Linux):  0 3 * * *  /opt/zabbix-lagunitas/scripts/backup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$ROOT/backups}"
RETENCION_DIAS="${RETENCION_DIAS:-14}"
STAMP="$(date +%Y%m%d_%H%M)"
COMPOSE_DIR="${COMPOSE_DIR:-$ROOT}"   # en producción: $ROOT/deploy/produccion

mkdir -p "$DEST"
cd "$COMPOSE_DIR"

echo "==> Volcando base de datos..."
docker compose exec -T mysql-server sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE" 2>/dev/null' \
  | gzip > "$DEST/zabbix_${STAMP}.sql.gz"

# Validación mínima: el volcado debe terminar con la marca de mysqldump.
if ! gunzip -c "$DEST/zabbix_${STAMP}.sql.gz" | tail -1 | grep -q "Dump completed"; then
  echo "ERROR: el volcado está incompleto: $DEST/zabbix_${STAMP}.sql.gz" >&2
  exit 1
fi
echo "    $DEST/zabbix_${STAMP}.sql.gz ($(du -h "$DEST/zabbix_${STAMP}.sql.gz" | cut -f1))"

echo "==> Exportando templates y mapa (YAML)..."
"$ROOT/bin/lagunitas" exportar >/dev/null && \
  tar -czf "$DEST/config_${STAMP}.tar.gz" -C "$ROOT" zabbix/export config && \
  echo "    $DEST/config_${STAMP}.tar.gz" || echo "    (aviso) no se pudo exportar la configuración"

echo "==> Eliminando backups con más de ${RETENCION_DIAS} días..."
find "$DEST" -maxdepth 1 -name 'zabbix_*.sql.gz' -mtime +"$RETENCION_DIAS" -print -delete
find "$DEST" -maxdepth 1 -name 'config_*.tar.gz' -mtime +"$RETENCION_DIAS" -print -delete
echo "Listo."
