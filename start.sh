#!/usr/bin/env bash
# Arranque/apagado del LABORATORIO completo (Mac con Colima).
#   ./start.sh          levanta Colima, el stack Zabbix y la red simulada
#   ./start.sh down     apaga la red simulada y el stack (conserva los datos)
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-up}" in
  down)
    echo "==> Deteniendo equipos simulados..."
    bin/lagunitas lab apagar
    echo "==> Deteniendo stack Zabbix..."
    docker compose down
    echo "Listo, todo apagado (los datos se conservan)."
    ;;
  up)
    if command -v colima >/dev/null && ! colima status >/dev/null 2>&1; then
      echo "==> Iniciando Colima..."
      colima start
    fi
    [ -f .env ] || { echo "Falta .env: copiá .env.example a .env y completalo." >&2; exit 1; }

    echo "==> Levantando stack Zabbix..."
    docker network inspect lagunitas_net >/dev/null 2>&1 || \
      docker network create --subnet=10.50.0.0/24 lagunitas_net >/dev/null
    docker compose up -d

    echo "==> Esperando el frontend..."
    for _ in $(seq 1 60); do
      curl -sf "http://localhost:${ZABBIX_WEB_PORT:-8090}" >/dev/null && break
      sleep 3
    done

    echo "==> Levantando equipos simulados (desde config/inventory.lab.yaml)..."
    bin/lagunitas lab levantar

    if [ "${ABRIR_NAVEGADOR:-1}" = "1" ] && command -v open >/dev/null; then
      open "http://localhost:${ZABBIX_WEB_PORT:-8090}"
    fi
    echo "Listo, laboratorio arriba."
    ;;
  *)
    echo "Uso: $0 [up|down]" >&2
    exit 2
    ;;
esac
