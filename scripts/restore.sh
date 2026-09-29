#!/usr/bin/env bash
# Restaura un volcado de la base de Zabbix generado por scripts/backup.sh.
# Uso:  scripts/restore.sh backups/zabbix_AAAAMMDD_HHMM.sql.gz
# ATENCIÓN: reemplaza TODA la configuración e historial actuales.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVO="${1:?Indicá el archivo .sql.gz a restaurar}"
COMPOSE_DIR="${COMPOSE_DIR:-$ROOT}"
[ -f "$ARCHIVO" ] || { echo "No existe: $ARCHIVO" >&2; exit 1; }

read -r -p "Se reemplazará la base de Zabbix con $ARCHIVO. Escribí RESTAURAR para continuar: " ok
[ "$ok" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

cd "$COMPOSE_DIR"
echo "==> Deteniendo zabbix-server y zabbix-web..."
docker compose stop zabbix-server zabbix-web
echo "==> Restaurando..."
gunzip -c "$ARCHIVO" | docker compose exec -T mysql-server sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
echo "==> Iniciando servicios..."
docker compose start zabbix-server zabbix-web
echo "Listo. Verificar con: bin/lagunitas verificar"
