# Monitoreo de la Red Comunitaria y Científica Las Lagunitas (Zabbix 7.0)

Sistema de monitoreo para la red WISP comunitaria de **Las Lagunitas** (Alpa Corral, Córdoba),
desarrollado en el marco de la Práctica Profesional Supervisada — Ingeniería en
Telecomunicaciones, UNRC.

Toda la configuración de Zabbix se genera **como código** a partir de un inventario de la red
(`config/inventory.*.yaml`): hosts, templates, dependencias entre equipos, mapa de topología,
servicios/SLA, dashboards y alertas. Así el mismo proyecto sirve para el laboratorio y para el
despliegue productivo, y cualquier cambio en la red se aplica con un solo comando.

## Qué incluye

| Componente | Descripción |
|---|---|
| `config/inventory.lab.yaml` | Inventario de la red (fuente única de verdad): 4 torres, 9 nodos, 13 hogares/instituciones + el AP real del laboratorio. |
| `lagunitas/` + `bin/lagunitas` | Provisionador idempotente vía API de Zabbix y simulador del laboratorio. |
| Templates propios | **Lagunitas - Disponibilidad ICMP** (disponibilidad, pérdida, latencia, disponibilidad 24 h / 7 d) y **Lagunitas - AP UniFi por API** (CPU, memoria, clientes, uplink, reintentos por banda, firmware). Cada uno con su *dashboard de detalle por equipo*. |
| Dependencias padre → hijo | Si cae una torre, se alerta solo por la torre; los nodos y hogares que cuelgan de ella no generan tormenta de alarmas. |
| Módulo **Red Las Lagunitas** (widget) | Tarjetas de resumen, buscador, filtros y tablas por rol con barras de disponibilidad/latencia/pérdida. Clic en un equipo → modal con *Resumen, Problemas, Rendimiento, Dependencias* (qué queda sin servicio si ese equipo cae). |
| Módulo **Disponibilidad de la red** (Reports) | Reporte técnico/gerencial por período: disponibilidad *propia* y *de servicio* (incluye caídas aguas arriba), caídas, MTTR, cumplimiento de objetivo, conclusiones automáticas, CSV e impresión a PDF. |
| Dashboard **Las Lagunitas - Centro de monitoreo** | Páginas: Equipos · Estado de la red (panal + mapa + alertas) · Detalle por equipo (navegador) · AP UniFi · SLA. |
| Servicios y SLA | Árbol de servicios Red → rol → equipo y SLA mensual (objetivo 99,5 %). |
| Alertas | Grupo *Operadores Las Lagunitas*, acción de notificación (≥ Average) y Telegram opcional. |
| `deploy/produccion/` | Stack productivo con HTTPS (Caddy), volúmenes con nombre y logs rotados. |
| `scripts/` | Backup/restauración de la base y arranque automático (launchd). |

## Inicio rápido (laboratorio)

```bash
cp .env.example .env        # completar claves y UNIFI_API_KEY
./start.sh                  # Colima + stack Zabbix + red simulada
bin/lagunitas aprovisionar  # crea/actualiza toda la configuración en Zabbix
bin/lagunitas verificar     # chequeo de salud
```

Frontend: <http://localhost:8090> → *Dashboards → Las Lagunitas - Centro de monitoreo*.

Simular una caída y su recuperación:

```bash
bin/lagunitas lab caida Nodo_Kika       # ~90 s después: alerta + mapa en rojo
bin/lagunitas lab recuperar Nodo_Kika
```

## Documentación

- [Guía de implementación](docs/guia-implementacion.md): instalación en laboratorio y en producción paso a paso.
- [Manual de administración](docs/manual-administracion.md): operación diaria, alarmas, altas/bajas de equipos, backups y resolución de problemas.
- `docs/referencia/`: informe de la PPS, diagramas y documentos de la versión anterior.

## Estructura

```
config/                 inventarios (lab y producción)
lagunitas/              provisionador (Python) — python -m lagunitas / bin/lagunitas
zabbix/modules/         módulos del frontend (widget y reporte, PHP/JS/CSS)
zabbix/export/          templates y mapa exportados en YAML (bin/lagunitas exportar)
deploy/produccion/      docker compose + Caddy para el servidor productivo
scripts/                backup, restauración, arranque automático
legacy/                 scripts de la versión 1 (histórico, no usar)
docs/                   guías y material de referencia
```

## Seguridad

- Las claves (base de datos, API key de UniFi, comunidad SNMP, bot de Telegram) viven en `.env`,
  que **no** se versiona. La API key de UniFi se guarda en Zabbix como *macro secreta*.
- En producción: cambiar la contraseña de `Admin`, usar un API token para el provisionador y
  acceder al frontend solo por HTTPS.
