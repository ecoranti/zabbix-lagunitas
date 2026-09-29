#!/bin/bash
HOSTS=(
    "10.50.0.10:Torre-1"
    "10.50.0.20:Torre-2"
    "10.50.0.30:Torre-3"
    "10.50.0.40:Torre-4"
    "10.50.0.50:Nodo-A"
    "10.50.0.60:Nodo-B"
    "10.50.0.70:Casa-1"
    "10.50.0.80:Casa-2"
    "10.50.0.90:Escuela"
)
for data in "${HOSTS[@]}"; do
    IP=${data%%:*}
    NAME=${data##*:}
    echo "Levantando $NAME ($IP)..."
    docker run -d --rm --name "$NAME" --network lagunitas_net --ip "$IP" alpine tail -f /dev/null
done

echo "Listo. Verificar con: docker ps --format '{{.Names}}\t{{.Status}}'"
