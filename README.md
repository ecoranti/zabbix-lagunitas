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
| `config/inventory.*.yaml` | Inventario de la red (fuente única de verdad): gateway Mikrotik, 4 torres, 9 nodos, 13 hogares/instituciones y los equipos secundarios de cada sitio (AP, SM, routers), con modelo, función y perfiles de monitoreo. |
| `lagunitas/` + `bin/lagunitas` | Provisionador idempotente vía API de Zabbix y simulador del laboratorio. |
| Templates propios | **Disponibilidad ICMP** (todos los equipos) · **Ubiquiti airMAX por SNMP** (señal, ruido, SNR, CCQ, calidad/capacidad airMAX, estaciones asociadas, interfaces, sistema) · **Mikrotik por SNMP** (voltaje de batería, clientes DHCP, enlace PPPoE a Internet, recursos, interfaces) · **AP UniFi por API** (CPU, memoria, clientes, uplink, reintentos por banda, firmware). Cada uno con su *dashboard de detalle por equipo*. |
| Dependencias padre → hijo | Si cae una torre, se alerta solo por la torre; los nodos y hogares que cuelgan de ella no generan tormenta de alarmas. |
| Módulo **Red Las Lagunitas** (widget) | Tarjetas de resumen, buscador, filtros y tablas por rol con disponibilidad, latencia, pérdida y *enlace/energía* (señal/CCQ o voltaje/DHCP). Clic en un equipo → modal con pestañas según su tipo: *Resumen, Radio, Estaciones, Router y energía, Interfaces, Problemas, Rendimiento, Dependencias, UniFi*. |
| Módulo **Disponibilidad de la red** (Reports) | Reporte técnico/gerencial con filtros de período, grupo, equipo, tipo y mantenimientos; disponibilidad *propia* y *de servicio*, indicador detectado, salud y estado actual, MTTR, conclusiones, CSV y PDF. **Detalle técnico** por equipo: comportamiento de cada métrica (actual/promedio/extremo, tendencia, horas fuera de umbral), interfaces, estaciones, problemas agrupados con *flapping* y recomendaciones. |
| Laboratorio con SNMP simulado | `lab/snmpsim`: agentes SNMP con los OIDs reales de Ubiquiti airMAX y Mikrotik, y escenarios de falla (señal débil, interferencia, batería baja, sin Internet) para validar alertas sin hardware. |
| Diagnóstico de integración | `bin/lagunitas probar-snmp <ip>` y `bin/lagunitas unifi-ids <ip> <puerto>`. |
| Dashboard **Las Lagunitas - Centro de monitoreo** | Páginas: Equipos · Estado de la red (panal + mapa + alertas) · Detalle por equipo (navegador) · AP UniFi · SLA. |
| Servicios y SLA | Árbol de servicios Red → rol → equipo y SLA mensual (objetivo 99,5 %). |
| Alertas | Grupo *Operadores Las Lagunitas*, acción de notificación (≥ Average) y Telegram opcional. |
| `deploy/produccion/` | Stack productivo con HTTPS (Caddy), volúmenes con nombre y logs rotados. |
| `scripts/` | Backup/restauración de la base y arranque automático (launchd). |

## Inicio rápido

Producción: seguir la [Guía de implementación](docs/guia-implementacion.md).

Laboratorio (desarrollo y pruebas, ver [docs/laboratorio.md](docs/laboratorio.md)):

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
bin/lagunitas lab escenario Walter senal-debil   # falla de radio simulada por SNMP
bin/lagunitas lab escenario Walter normal
```

## Documentación

- [Informe de la PPS](docs/informe/README.md): versión web del informe del trabajo final (se genera desde `docs/informe/Informe PPS Elias.docx` con `scripts/informe2md.py`).
- [Guía de implementación](docs/guia-implementacion.md): instalación en laboratorio y en producción paso a paso.
- [Guía de integración de equipos](docs/guia-integracion-equipos.md): cómo incorporar cada tipo de equipo (airMAX, Mikrotik, airCube, UniFi), qué datos y alertas aporta, y cómo validarlo.
- [Manual de administración](docs/manual-administracion.md): operación diaria, alarmas, altas/bajas de equipos, backups y resolución de problemas.
- [Guía del laboratorio](docs/laboratorio.md): puesta en marcha y uso del laboratorio en la Mac (arranque, pruebas de alertas, AP real con sonda ICMP, problemas frecuentes). Solo desarrollo; no forma parte de producción.
- Versiones Word de las guías: `docs/*.docx`. Se regeneran desde el Markdown con
  `.venv/bin/pip install -r requirements-docs.txt` y `scripts/md2docx.py <origen.md> <destino.docx>`.
- `docs/referencia/`: informe de la PPS, diagramas y documentos de la versión anterior.

## Estructura

```
config/                 inventarios (lab y producción)
lagunitas/              provisionador (Python) — python -m lagunitas / bin/lagunitas
zabbix/modules/         módulos del frontend (widget y reporte, PHP/JS/CSS)
zabbix/export/          templates y mapa exportados en YAML (bin/lagunitas exportar)
lab/snmpsim/            agentes SNMP simulados (airMAX AP/SM, Mikrotik) para el laboratorio
deploy/produccion/      docker compose + Caddy para el servidor productivo
scripts/                backup, restauración, arranque automático
legacy/                 scripts de la versión 1 (histórico, no usar)
docs/                   guías y material de referencia
```

## Agradecimientos

A **Willian Tola** ([LinkedIn](https://www.linkedin.com/in/willian-tola-68661b80/)), autor de
[Reportes-Zabbix](https://github.com/lab24com/Reportes-Zabbix) (lab24com), cuyo trabajo sirvió de
referencia e inspiración para mejorar la primera versión de este sistema, en particular el módulo de
reportes. El módulo de este repositorio es una implementación propia para Zabbix 7.0.

## Seguridad

- Las claves (base de datos, API key de UniFi, comunidad SNMP, bot de Telegram) viven en `.env`,
  que **no** se versiona. La API key de UniFi se guarda en Zabbix como *macro secreta*.
- En producción: cambiar la contraseña de `Admin`, usar un API token para el provisionador y
  acceder al frontend solo por HTTPS.
