#!/bin/sh
# Agente SNMP simulado del laboratorio.
#   PERFIL   airmax-ap | airmax-sm | mikrotik   (archivo data/<perfil>.snmprec)
#   NOMBRE   sysName del equipo          MODELO    modelo informado por el equipo
#   REMOTO   estación asociada (nombre)  IPREMOTA  IP de la estación asociada
# Se publica con la comunidad "public" (nombre del archivo .snmprec).
# /usr/local/bin/perfil-reset regenera los valores normales (lo usa "lab escenario normal").
set -e
cat > /usr/local/bin/perfil-reset <<'SCRIPT'
#!/bin/sh
set -e
PERFIL="${PERFIL:-airmax-sm}"
mkdir -p /tmp/snmp
sed -e "s/__NOMBRE__/${NOMBRE:-$HOSTNAME}/g" \
    -e "s/__MODELO__/${MODELO:-LiteBeam 5AC Gen2}/g" \
    -e "s/__REMOTO__/${REMOTO:-estacion-remota}/g" \
    -e "s/__IPREMOTA__/${IPREMOTA:-10.50.0.254}/g" \
    "/usr/local/snmpsim/data/${PERFIL}.snmprec" > /tmp/snmp/public.snmprec
chown -R snmpsim /tmp/snmp
SCRIPT
chmod +x /usr/local/bin/perfil-reset
/usr/local/bin/perfil-reset
exec snmpsim-command-responder --data-dir=/tmp/snmp --agent-udpv4-endpoint=0.0.0.0:161 \
  --process-user=snmpsim --process-group=snmpsim --cache-dir=/tmp/snmp/cache
