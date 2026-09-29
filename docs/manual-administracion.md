# Manual de administración — Monitoreo de la Red Las Lagunitas

**Versión 2.0** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas

Referencia operativa del día a día: cómo leer el estado de la red, atender alarmas, dar de alta
o activar equipos, generar reportes, respaldar y resolver los problemas más frecuentes. La
instalación está en la [Guía de implementación](guia-implementacion.md).

---

## 1. Conceptos clave

| Concepto | Significado |
|---|---|
| **Inventario** | `config/inventory.*.yaml`: lista de equipos con rol, IP, padre y estado. Es la fuente de verdad: los cambios se hacen ahí y se aplican con `bin/lagunitas aprovisionar`. Los cambios manuales en Zabbix sobre objetos gestionados se pisan en el siguiente aprovisionamiento. |
| **Rol** | Torre (backbone), Nodo intermedio, Hogar, Institución, Access point (laboratorio). |
| **Estado del tramo** | `operativo` (monitoreado), `en_proceso` o `sin_configurar` (el equipo existe en Zabbix pero deshabilitado; en el mapa se ve en gris). |
| **Padre** | Equipo del que depende la conectividad. Define las dependencias de alarmas y la disponibilidad *de servicio*. |
| **Disponibilidad propia** | Porcentaje del tiempo en que el propio equipo respondió. |
| **Disponibilidad del servicio** | Descuenta además las caídas de sus ancestros: lo que realmente vivió el hogar. |

### Objetos que crea el provisionador

| Tipo | Nombre |
|---|---|
| Grupos de hosts | `Las Lagunitas` y subgrupos `Torres`, `Nodos`, `Hogares e instituciones`, `Equipos de laboratorio` |
| Templates | `Lagunitas - Disponibilidad ICMP`, `Lagunitas - AP UniFi por API` (grupo `Templates/Las Lagunitas`) |
| Mapa | `Las Lagunitas - Topología` |
| Dashboard | `Las Lagunitas - Centro de monitoreo` |
| Servicios / SLA | `Red Las Lagunitas` (y sub-servicios) · SLA `Las Lagunitas - Disponibilidad mensual` |
| Alertas | Grupo `Operadores Las Lagunitas` · Acción `Las Lagunitas - Notificar caídas` |
| Módulos | `Red Las Lagunitas` (widget) · `Reporte de disponibilidad - Las Lagunitas` |

---

## 2. Acceso

| Entorno | URL |
|---|---|
| Laboratorio | `http://localhost:8090` (desde otra PC de la LAN: `http://<IP-de-la-Mac>:8090`) |
| Producción | `https://<ZBX_DOMAIN>` |

Usuarios: `Admin` (super administrador; contraseña cambiada en la instalación) y los operadores
que se creen en el grupo **Operadores Las Lagunitas** (permiso de lectura sobre la red y
destinatarios de las notificaciones). Para crear un operador: *Users → Users → Create user*,
grupo *Operadores Las Lagunitas*, rol *User role*; en la pestaña *Media* cargar su Telegram o email.

---

## 3. Uso diario: el Centro de monitoreo

*Dashboards → Las Lagunitas - Centro de monitoreo*. Tiene cinco páginas (pestañas inferiores);
con **Start slideshow** rotan automáticamente, útil para una pantalla fija.

### 3.1 Página "Equipos" (widget Red Las Lagunitas)

- **Tarjetas superiores**: Total · En línea · Advertencias · Caídos · Sin servicio · Sin datos ·
  No monitoreados. Un clic en una tarjeta filtra la tabla.
- **Buscador y filtros rápidos**: por nombre, IP, rol o hardware; chips por estado y por rol.
- **Tablas por rol** con disponibilidad de 24 h, latencia, pérdida, equipo del que depende y
  problemas activos. Las filas problemáticas se ordenan primero.
- **Clic en un equipo** abre su detalle:
  - *Resumen*: indicadores, datos del equipo y accesos directos (dashboard del equipo, últimos
    datos, problemas, configuración).
  - *Problemas*: activos y los incidentes de los últimos 30 días con su duración.
  - *Rendimiento*: gráficos de latencia, pérdida y disponibilidad (1 h / 24 h / 7 d / 30 d).
  - *Dependencias*: camino hasta el backbone y **qué equipos quedan sin servicio si este cae**.
  - *UniFi* (solo AP): estado, modelo, firmware, reintentos por banda y uplink.

Significado de los estados:

| Estado | Significado | Acción |
|---|---|---|
| **En línea** | Responde y sin problemas. | — |
| **Advertencia** | Responde, pero con pérdida o latencia altas (u otra advertencia). | Revisar calidad del enlace. |
| **Caído** | No responde y su trigger de caída está activo. | Atender (ver §4). |
| **Sin servicio** | No responde porque cayó un equipo del que depende (se indica cuál). | Atender la causa raíz, no este equipo. |
| **Sin datos** | Zabbix no recibe valores hace más de 5 min (item con error o chequeo detenido). | Ver §9. |
| **No monitoreado** | Tramo en proceso / sin configurar, o equipo en mantenimiento. | — |

### 3.2 Página "Estado de la red"

- **Panal de equipos**: un hexágono por equipo monitoreado, verde o rojo.
- **Problemas por severidad** y **Alertas activas** en tiempo real.
- **Mapa de topología**: mismas convenciones que el esquema de campo (línea sólida = operativo,
  discontinua = en proceso, punteada = sin configurar). Un tramo se pinta **rojo y grueso**
  cuando cae el equipo del extremo. Clic en un equipo → *Detalle del equipo* o *Problemas*.

### 3.3 Página "Detalle por equipo"

Navegador de equipos agrupado por rol: al elegir uno, todos los widgets de la página (estado,
disponibilidad 24 h / 7 d, latencia, gráficos y problemas) muestran ese equipo.

### 3.4 Páginas "AP UniFi" y "SLA"

- *AP UniFi*: CPU, memoria, clientes, reintentos, tráfico del uplink y estado del controlador.
- *SLA*: cumplimiento mensual por equipo (servicio) y ranking de disponibilidad de 7 días.

Además, cada equipo tiene su **dashboard propio** (*Monitoring → Hosts → columna Dashboards*),
generado por el template.

---

## 4. Alarmas

### 4.1 Triggers configurados

**Template Lagunitas - Disponibilidad ICMP** (todos los equipos de la red):

| Trigger | Condición | Severidad |
|---|---|---|
| `<equipo>: sin respuesta (ICMP)` | Sin respuesta al ping durante `{$ICMP.CAIDA.PERIODO}` (90 s) | High |
| `<equipo>: pérdida de paquetes alta` | Pérdida mínima de 5 min > `{$ICMP.PERDIDA.WARN}` (20 %) | Warning |
| `<equipo>: latencia alta` | Latencia promedio de 5 min > `{$ICMP.LATENCIA.WARN}` (0,15 s) | Warning |

**Template Lagunitas - AP UniFi por API**:

| Trigger | Condición | Severidad |
|---|---|---|
| `controlador UniFi no accesible` | Puerto HTTPS del controlador cerrado 3 chequeos | Average |
| `sin datos de la API de UniFi` | Sin estadísticas por `{$AP.SIN.DATOS}` (5 min) | Average |
| `AP fuera de línea según UniFi` | El controlador informa un estado distinto de ONLINE | High |
| `uso de CPU / memoria alto` | Mínimo de 5 min > 85 % | Warning |
| `reintentos altos en 2.4 / 5 / 6 GHz` | Promedio de 15 min > `{$AP.REINTENTOS.WARN}` (20 %) | Warning |
| `el AP se reinició` | Uptime < 10 min | Information |
| `cambió la versión de firmware` | Cambio de versión | Information |

Las advertencias dependen del trigger de caída del mismo equipo, y el trigger de caída de cada
equipo depende del de su padre: **una caída troncal genera una sola alerta**.

### 4.2 Qué hacer ante una caída

1. Abrir el equipo en la página *Equipos* → pestaña *Dependencias* para ver el impacto.
2. Revisar si otros equipos del mismo tramo están "Sin servicio" (confirma que el problema es de
   ese equipo o de su enlace hacia el padre).
3. Causas habituales en la red: **alimentación** (panel solar / batería de 12 V, controlador de
   carga), **desalineación** de antenas por viento, **equipo colgado** (reinicio remoto o en
   sitio), **corte del enlace troncal**.
4. Registrar lo actuado: en *Alertas activas* → columna *Update* → *Acknowledge* con un mensaje
   (queda en el historial del problema).
5. Al volver el equipo, el problema se cierra solo (recuperación automática).

### 4.3 Mantenimientos programados

Antes de trabajar en una torre (cambio de batería, realineación), crear un mantenimiento para no
generar alertas: *Data collection → Maintenance → Create maintenance period*, elegir los hosts
(la torre y, si corresponde, los equipos que dependen de ella) y el horario. Durante el
mantenimiento los equipos se ven como "No monitoreados" en el widget.

### 4.4 Ajustar umbrales

Los umbrales son **macros**. Para cambiarlos en un solo equipo (por ejemplo un enlace largo con
más latencia): *Data collection → Hosts → <equipo> → Macros → Inherited and host macros* y
sobrescribir `{$ICMP.LATENCIA.WARN}`. Para cambiarlos en toda la red, editar el valor por
defecto en `lagunitas/templates.py` y ejecutar `bin/lagunitas aprovisionar --solo templates`.

### 4.5 Notificaciones

La acción *Las Lagunitas - Notificar caídas* avisa (≥ Average) al grupo *Operadores Las
Lagunitas* por todos sus medios, repite a los 30 minutos si el problema sigue y avisa la
recuperación. Los problemas suprimidos (mantenimiento) no se notifican. Configuración de
Telegram: ver la Guía de implementación §4.9.

---

## 5. Reportes

### 5.1 Reports → Disponibilidad de la red

1. Elegir **Período** (hoy, 24 h, 7 días, 30 días, mes actual, mes anterior o fechas), **Rol**,
   **Objetivo (%)** y **Vista** (*Técnica* o *Gerencial*), y pulsar **Generar**.
2. El encabezado (nombre de la organización y título) se edita haciendo clic sobre el texto; se
   recuerda en ese navegador.
3. Contenido: tarjetas de resumen, **conclusiones automáticas** (disponibilidad media, equipos
   que no cumplen, caída más larga, caída de mayor impacto), y una tabla por rol. Un clic en el
   nombre de un equipo despliega sus incidentes, indicando si fue una caída propia o de un equipo
   aguas arriba.
4. **Exportar CSV** (separador `;`, abre directo en Excel/LibreOffice) o **Imprimir / PDF**
   (A4 apaisado; en el diálogo de impresión elegir "Guardar como PDF").

La vista *gerencial* muestra solo disponibilidad del servicio, tiempo sin servicio, caídas y
cumplimiento: pensada para rendir cuentas a la comunidad o a financiadores.

### 5.2 Services → SLA report

Reporte nativo de Zabbix del SLA mensual por servicio (equipo operativo). Útil para ver la
evolución mes a mes.

---

## 6. Gestión de equipos

Todas las operaciones se hacen editando el inventario y re-aprovisionando.

**Activar un tramo que estaba en proceso** (por ejemplo Franco):

```yaml
  - host: Nodo_Franco
    estado: operativo        # antes: en_proceso
```

```bash
bin/lagunitas aprovisionar
bin/lagunitas lab levantar   # solo en el laboratorio: crea su contenedor
```

**Agregar un equipo nuevo**: agregar un bloque al inventario con `host` (sin espacios, único),
`nombre`, `rol`, `ip`, `padre`, `estado`, `perfiles`, `equipo` y `mapa: [x, y]` (posición en el
mapa, 1000 × 1000). Luego `bin/lagunitas aprovisionar`.

**Cambiar la IP o el padre**: editar el campo y re-aprovisionar (se actualizan interfaz,
dependencias, mapa y servicios).

**Dar de baja un equipo**: pasarlo a `sin_configurar` (queda deshabilitado, conserva el
historial) o quitarlo del inventario y borrar el host en *Data collection → Hosts*.

**Monitorear un equipo por SNMP** (producción): agregar el perfil `airos_snmp` o
`mikrotik_snmp`, definir `SNMP_COMMUNITY` en `.env` y re-aprovisionar.

El provisionador valida el inventario antes de tocar Zabbix: IPs repetidas, padres inexistentes,
ciclos, roles o estados inválidos.

---

## 7. Laboratorio: simulación de caídas

```bash
bin/lagunitas lab estado                     # contenedor de cada equipo
bin/lagunitas lab caida Nodo_Kika            # un hogar queda "Sin servicio"; alerta por el nodo
bin/lagunitas lab recuperar Nodo_Kika
bin/lagunitas lab caida Union_de_los_Rios    # caída troncal: 1 alerta, el resto "Sin servicio"
bin/lagunitas lab recuperar Union_de_los_Rios
```

Los contenedores se crean con reinicio automático y sin `--rm`, por lo que *caída* y
*recuperar* son un `docker stop` / `docker start`. `./start.sh` y `./start.sh down` levantan o
apagan todo el laboratorio conservando los datos.

---

## 8. Mantenimiento del sistema

| Tarea | Cómo |
|---|---|
| Backup | `scripts/backup.sh` (base comprimida + export YAML de templates y mapa). Producción: cron diario (Guía §4.10). |
| Restauración | `scripts/restore.sh backups/zabbix_AAAAMMDD_HHMM.sql.gz` (pide confirmación). |
| Chequeo de salud | `bin/lagunitas verificar` |
| Exportar templates | `bin/lagunitas exportar` → `zabbix/export/*.yaml` (importables en otro Zabbix). |
| Actualizar Zabbix | Hacer backup; cambiar el tag `ubuntu-7.0.x` en el compose (misma versión mayor 7.0 LTS); `docker compose pull && docker compose up -d`; `bin/lagunitas verificar`. Para pasar a otra versión mayor leer primero las notas de actualización de Zabbix. |
| Rotar la API key de UniFi | Crear la nueva en UniFi, actualizar `UNIFI_API_KEY` en `.env` y `bin/lagunitas aprovisionar --solo hosts`. |
| Historial | Los items guardan 90 días de historia y 1 año de tendencias. Limpieza automática: *Administration → Housekeeping*. |

---

## 9. Resolución de problemas

**Un equipo aparece "Sin datos".** *Monitoring → Latest data* filtrando por el equipo: si el item
muestra un ícono de error, pasar el mouse para ver el motivo. En el laboratorio, confirmar el
contenedor con `bin/lagunitas lab estado`.

**Todos los equipos "Sin datos" o caídos a la vez.** Revisar que el Zabbix server esté arriba
(`docker compose ps`), su log (`docker compose logs --tail 50 zabbix-server`) y, en producción,
el enlace/VPN hacia la red. En el laboratorio, `colima status`.

**El AP UniFi no reporta.** Si aparece *controlador UniFi no accesible*, el problema es la
aplicación UniFi (encendida, puerto correcto); si aparece *sin datos de la API*, revisar la API
key y los IDs de site/dispositivo (macros del host).

**En el laboratorio el AP "responde ping" aunque esté apagado.** Es la limitación de Colima
descripta en la guía: responde ICMP por cualquier IP externa. Por eso el AP del laboratorio se
monitorea solo por API.

**El widget "Red Las Lagunitas" no aparece o el reporte no está en el menú.**
`bin/lagunitas aprovisionar --solo modulos` (registra y habilita los módulos); verificar en
*Administration → General → Modules*. En el compose, las carpetas `zabbix/modules/*` deben estar
montadas en el contenedor web.

**Un widget muestra "No permissions to referred object or it does not exist".** El equipo
seleccionado no tiene ese item (por ejemplo, el AP no tiene ítems ICMP). Es esperable.

**`docker: failed to connect to the docker API ... colima`** (laboratorio). Colima detenida:
`colima start` o `./start.sh`.

**Cambios hechos a mano en Zabbix desaparecieron.** El provisionador sobrescribe los objetos que
gestiona. Hacer el cambio en el inventario o en el código del proyecto.

**Recuperar desde cero.** Stack nuevo + `scripts/restore.sh <último backup>`; o bien stack nuevo
vacío + `bin/lagunitas aprovisionar` (recrea toda la configuración, sin el historial).

---

## 10. Referencia rápida

```bash
./start.sh | ./start.sh down                  # laboratorio completo
bin/lagunitas aprovisionar                    # aplicar inventario y configuración
bin/lagunitas aprovisionar --solo mapa        # un paso puntual
bin/lagunitas verificar                       # salud
bin/lagunitas lab caida|recuperar <equipo>    # simulación
scripts/backup.sh                             # respaldo
docker compose logs --tail 50 zabbix-server   # logs
```
