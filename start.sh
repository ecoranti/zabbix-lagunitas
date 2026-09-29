#!/bin/bash
set -e
cd "$(dirname "$0")"

NODOS_OPERATIVOS=(Union_de_los_Rios Rodeo_del_Padre Ex_Aserradero El_Carrizal Escuela_Rural Nodo_Kika Nodo_CheoMaricel Nodo_AlePatricio Mesada Kika CheoMaricel AlePatricio Esther Walter)

case "$1" in
  down)
    echo "Bajando nodos simulados..."
    for c in $(docker ps --filter "network=lagunitas_net" --format '{{.Names}}'); do
      docker stop "$c"
    done
    echo "Bajando stack Zabbix..."
    docker compose down
    echo "Listo, todo apagado."
    ;;
  *)
    if ! colima status > /dev/null 2>&1; then
      echo "Iniciando Colima..."
      colima start
    fi

    echo "Levantando stack Zabbix..."
    docker compose up -d

    echo "Esperando a que el frontend responda..."
    until curl -sf http://localhost:8090 > /dev/null 2>&1; do
      sleep 2
    done

    echo "Limpiando restos de nodos simulados previos..."
    for n in "${NODOS_OPERATIVOS[@]}"; do
      docker rm -f "$n" > /dev/null 2>&1 || true
    done

    echo "Levantando nodos simulados..."
    bash simulate_nodesv2.sh

    echo "Abriendo dashboard..."
    open "http://localhost:8090"

    echo "Listo, stack completo arriba."
    ;;
esac
