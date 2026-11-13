#!/usr/bin/env bash
# Restaura un volcado de la base de Zabbix generado por scripts/backup.sh.
# Uso:  scripts/restore.sh backups/zabbix_AAAAMMDD_HHMM.sql.gz
#       (en producción: COMPOSE_DIR=deploy/produccion scripts/restore.sh <archivo>)
# ATENCIÓN: reemplaza TODA la configuración e historial actuales.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVO="${1:?Indicá el archivo .sql.gz a restaurar}"
COMPOSE_DIR="${COMPOSE_DIR:-$ROOT}"
[ -f "$ARCHIVO" ] || { echo "No existe: $ARCHIVO" >&2; exit 1; }
# Rutas absolutas: el script cambia de directorio antes de leer el archivo.
ARCHIVO="$(cd "$(dirname "$ARCHIVO")" && pwd)/$(basename "$ARCHIVO")"
COMPOSE_DIR="$(cd "$COMPOSE_DIR" && pwd)"

# Validar el volcado antes de tocar nada: gzip íntegro y marca final de mysqldump.
echo "==> Verificando $ARCHIVO..."
gzip -t "$ARCHIVO" || { echo "ERROR: el archivo está dañado (gzip)." >&2; exit 1; }
gunzip -c "$ARCHIVO" | tail -1 | grep -q "Dump completed" \
  || { echo "ERROR: el volcado está incompleto (falta la marca final de mysqldump)." >&2; exit 1; }

cd "$COMPOSE_DIR"
docker compose ps --status running --services | grep -qx mysql-server \
  || { echo "ERROR: el contenedor mysql-server no está en marcha en $COMPOSE_DIR." >&2; exit 1; }

read -r -p "Se reemplazará la base de Zabbix con $ARCHIVO. Escribí RESTAURAR para continuar: " ok
[ "$ok" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

# Pase lo que pase, los servicios vuelven a quedar en marcha.
trap 'echo "==> Iniciando servicios..."; docker compose start zabbix-server zabbix-web' EXIT

echo "==> Deteniendo zabbix-server y zabbix-web..."
docker compose stop zabbix-server zabbix-web
echo "==> Restaurando..."
gunzip -c "$ARCHIVO" | docker compose exec -T mysql-server sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
echo "Restauración completa. Verificar con: bin/lagunitas verificar"
