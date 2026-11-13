#!/usr/bin/env bash
# Pruebas de validación del LAB.
# Uso:  scripts/pruebas-validacion.sh        menú interactivo: tirar abajo y levantar equipos
#       scripts/pruebas-validacion.sh 1      prueba guiada: degradación por SNMP
#       scripts/pruebas-validacion.sh 2      prueba guiada: caída troncal (Unión de los Ríos)
#       scripts/pruebas-validacion.sh 3      prueba guiada: aviso por Telegram (Nodo Kika)
# Equivale a: bin/lagunitas lab pruebas [1|2|3]
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin/lagunitas" lab pruebas "$@"
