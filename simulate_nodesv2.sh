#!/bin/bash
# Nodos "operativos" en la red real: se levantan como contenedores activos.
HOSTS=(
    "10.50.0.11:Union_de_los_Rios"
    "10.50.0.12:Rodeo_del_Padre"
    "10.50.0.13:Ex_Aserradero"
    "10.50.0.14:El_Carrizal"
    "10.50.0.15:Escuela_Rural"
    "10.50.0.21:Nodo_Kika"
    "10.50.0.22:Nodo_CheoMaricel"
    "10.50.0.23:Nodo_AlePatricio"
    "10.50.0.25:Mesada"
    "10.50.0.31:Kika"
    "10.50.0.32:CheoMaricel"
    "10.50.0.33:AlePatricio"
    "10.50.0.35:Esther"
    "10.50.0.38:Walter"
)

# Nodos "en proceso" / "sin configurar" en la red real: quedan sin contenedor
# a propósito, para que Zabbix los muestre caídos hasta que se activen.
# Para activarlos, mové la línea correspondiente al array HOSTS de arriba.
PENDING=(
    "10.50.0.24:Nodo_Franco"
    "10.50.0.26:Nodo_JuanCarlos"
    "10.50.0.27:Cerro_Blanco"
    "10.50.0.28:Nodo_MartinDonJulio"
    "10.50.0.34:Franco"
    "10.50.0.36:JuanCarlos"
    "10.50.0.37:FabianLucianaLasGuindas"
    "10.50.0.39:Gladys"
    "10.50.0.40:EulaliaDomingo"
    "10.50.0.41:Martin"
    "10.50.0.42:DonJulio"
)

echo "Limpiando nodos anteriores (si existen)..."
for old in Torre-1 Torre-2 Torre-3 Torre-4 Nodo-A Nodo-B Casa-1 Casa-2 Escuela; do
    docker stop "$old" 2>/dev/null
done

for data in "${HOSTS[@]}"; do
    IP=${data%%:*}
    NAME=${data##*:}
    echo "Levantando $NAME ($IP)..."
    docker run -d --rm --name "$NAME" --network lagunitas_net --ip "$IP" alpine tail -f /dev/null
done

echo ""
echo "Elementos 'en proceso' / 'sin configurar' (sin contenedor, quedarán caídos en Zabbix):"
for data in "${PENDING[@]}"; do
    IP=${data%%:*}
    NAME=${data##*:}
    echo "  - $NAME ($IP)"
done

echo ""
echo "Listo. Verificar con: docker ps --format '{{.Names}}\t{{.Status}}'"
