# Agente SNMP simulado para el laboratorio: responde como un equipo real
# (Ubiquiti airMAX o Mikrotik) a partir de archivos .snmprec con OIDs del fabricante.
FROM python:3.12-alpine
RUN pip install --no-cache-dir snmpsim-lextudio==1.1.1 \
 && adduser -D -H snmpsim
COPY data /usr/local/snmpsim/data
COPY entrypoint.sh /entrypoint.sh
EXPOSE 161/udp
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
