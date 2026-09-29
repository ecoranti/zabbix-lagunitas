# Manual de administración — Monitoreo de la Red Las Lagunitas

**Versión 2.2** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas

Referencia operativa del día a día: cómo leer el estado de la red, atender alarmas, dar de alta
o activar equipos, generar reportes, respaldar y resolver los problemas más frecuentes. La
instalación está en la [Guía de implementación](guia-implementacion.md) y la incorporación de
equipos en la [Guía de integración de equipos](guia-integracion-equipos.md).

---

## 1. Conceptos clave

| Concepto | Significado |
|---|---|
| **Inventario** | `config/inventory.*.yaml`: lista de equipos con rol, IP, padre y estado. Es la fuente de verdad: los cambios se hacen ahí y se aplican con `bin/lagunitas aprovisionar`. Los cambios manuales en Zabbix sobre objetos gestionados se pisan en el siguiente aprovisionamiento. |
| **Rol** | Gateway (salida a Internet), Torre (backbone), Nodo intermedio, Hogar, Institución, Access point. |
| **Sitio y dispositivos** | Un sitio del mapa (torre, nodo, hogar) puede tener varios equipos con IP: el principal y sus *dispositivos* (por ejemplo, la radio que recibe, el AP que retransmite y el router del hogar). Cada uno es un host con sus propias métricas. |
| **Perfiles** | Cómo se monitorea cada equipo: `icmp` (disponibilidad), `airos_snmp` (radios airMAX), `mikrotik_snmp` (routers Mikrotik), `unifi_api` (AP UniFi). |
| **Estado del tramo** | `operativo` (monitoreado), `en_proceso` o `sin_configurar` (el equipo existe en Zabbix pero deshabilitado; en el mapa se ve en gris). |
| **Padre** | Equipo del que depende la conectividad. Define las dependencias de alarmas y la disponibilidad *de servicio*. |
| **Disponibilidad propia** | Porcentaje del tiempo en que el propio equipo respondió. |
| **Disponibilidad del servicio** | Descuenta además las caídas de sus ancestros: lo que realmente vivió el hogar. |

### Objetos que crea el provisionador

| Tipo | Nombre |
|---|---|
| Grupos de hosts | `Las Lagunitas` y subgrupos `Gateway`, `Torres`, `Nodos`, `Hogares e instituciones`, `Access points` |
| Templates | `Lagunitas - Disponibilidad ICMP`, `Lagunitas - Ubiquiti airMAX por SNMP`, `Lagunitas - Mikrotik por SNMP`, `Lagunitas - AP UniFi por API` (grupo `Templates/Las Lagunitas`) |
| Mapa | `Las Lagunitas - Topología` |
| Dashboard | `Las Lagunitas - Centro de monitoreo` |
| Servicios / SLA | `Red Las Lagunitas` (y sub-servicios) · SLA `Las Lagunitas - Disponibilidad mensual` |
| Alertas | Grupo `Operadores Las Lagunitas` · Acción `Las Lagunitas - Notificar caídas` |
| Módulos | `Red Las Lagunitas` (widget) · `Reporte de disponibilidad - Las Lagunitas` |

---

## 2. Acceso

Frontend: `https://<ZBX_DOMAIN>` (nombre definido en la instalación).

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
- **Tablas por rol** con disponibilidad de 24 h, latencia, pérdida, **enlace / energía** (señal y
  CCQ en radios airMAX; voltaje y clientes DHCP en el Mikrotik), equipo del que depende y
  problemas activos. Las filas problemáticas se ordenan primero.
- **Clic en un equipo** abre su detalle:
  - *Resumen*: indicadores, datos del equipo (función, modelo, firmware, sitio) y accesos
    directos (detalle técnico de 7 días, dashboard del equipo, últimos datos, problemas,
    configuración).
  - *Radio* (airMAX): señal, ruido, SNR, CCQ, calidad y capacidad airMAX, modo, SSID, frecuencia,
    ancho de canal, potencia, distancia, antena, DFS, tasas TX/RX, CPU/memoria, temperatura.
  - *Estaciones* (airMAX): cada equipo conectado a la radio con su señal, ruido, CCQ, calidad,
    capacidad, tasas, distancia, latencia y tiempo conectado.
  - *Router y energía* (Mikrotik): voltaje, CPU, memoria, temperatura, clientes DHCP, estado de
    Internet (PPPoE), modelo, RouterOS, firmware, número de serie.
  - *Interfaces*: estado, tráfico entrante/saliente, errores y velocidad de cada interfaz.
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

### 4.6 Cómo leer las métricas de radio y energía

| Métrica | Bien | Revisar | Mal | Acción típica |
|---|---|---|---|---|
| Señal (airMAX) | -50 a -65 dBm | -65 a -75 dBm | < -75 dBm | Alineación, obstrucciones (árboles), potencia del otro extremo |
| Piso de ruido | -90 a -100 dBm | -85 a -90 dBm | > -85 dBm | Interferencia: cambiar frecuencia o reducir ancho de canal (airView) |
| SNR | > 30 dB | 20–30 dB | < 15–20 dB | Mejorar señal o reducir ruido |
| CCQ | > 90 % | 75–90 % | < 75 % | Interferencia o señal marginal |
| Calidad / capacidad airMAX | > 80 % / > 60 % | | < 60 % / < 40 % | Enlace inestable o degradado |
| Voltaje (Mikrotik, batería 12 V) | 12,4–13,8 V | 12,0–12,4 V | < 11,8 V o > 14,8 V | Panel sucio o sombreado, días nublados, batería o regulador |
| Clientes DHCP | habitual del sitio | caída brusca | 0 | Falla de la red de distribución o del DHCP |
| Temperatura | < 55 °C | 55–65 °C | > 65 °C | Ventilación del gabinete, exposición solar |

Detalle completo y alertas asociadas en la [Guía de integración de equipos](guia-integracion-equipos.md).

## 5. Reportes

### 5.1 Reports → Disponibilidad de la red

1. Filtros: **Tipo de reporte** (técnico o gerencial), **Período** (hoy, 24 h, 7 días, 30 días, mes
   actual, mes anterior o personalizado con fechas), **Grupo**, **Equipo**, **Tipo de equipo**
   (radios airMAX, Mikrotik, solo ICMP, AP UniFi), **Mantenimientos** (excluir o incluir los
   eventos suprimidos) y **SLA objetivo**. Pulsar **Generar reporte**.
2. **Personalizar encabezado**: organización y título del reporte. Se recuerdan en ese navegador
   y se aplican al reporte, al detalle técnico y a la impresión.
3. Tarjetas: equipos, evaluados, disponibilidad media, cumplen / no cumplen SLA, sin indicador,
   caídas, horas-equipo de caída, horas sin servicio, MTTR medio, salud normal y degradados.
4. **Conclusiones automáticas**: disponibilidad media, equipos que no cumplen, caída más larga,
   caída de mayor impacto (cuántos equipos dejó sin servicio), equipos con salud degradada.
5. Tabla: equipo, IP, grupo, **indicador detectado** (ICMP / SNMP / API), disponibilidad propia y
   del servicio, caída, incidentes, MTTR, mayor caída, **salud actual** (Normal o Degradado con la
   cantidad de problemas no críticos activos), **estado actual** (Disponible, Con caída activa, Sin
   servicio, En mantenimiento), SLA y **Ver detalle**. Debajo de cada equipo con caídas se
   despliega el detalle de incidentes indicando si fue propia o de un equipo aguas arriba.
6. **Exportar CSV** (separador `;`, abre directo en Excel/LibreOffice) o **Imprimir / Guardar PDF**
   (A4 apaisado; en el diálogo elegir "Guardar como PDF").

La vista *gerencial* oculta los datos técnicos (indicador, disponibilidad propia, MTTR, mayor
caída): pensada para rendir cuentas a la comunidad o a financiadores.

### 5.2 Detalle técnico de un equipo

Botón **Ver detalle** del reporte (o *Detalle técnico (7 días)* desde el modal del widget):

- **Tarjetas**: disponibilidad propia (y por qué indicador), disponibilidad del servicio, SLA,
  mantenimiento, caída propia y MTTR, problemas del período, problemas activos, tiempo afectado
  único (sin duplicar alertas simultáneas), horas-evento acumuladas, salud operativa y equipos
  dependientes.
- **Conclusiones y recomendaciones** según el tipo de equipo: señal pobre (revisar alineación y
  obstrucciones), interferencia (cambiar frecuencia), batería en descarga (revisar panel y
  regulador), picos de CPU/memoria, pérdida de paquetes, problemas con *flapping*, horas sin
  servicio por caídas aguas arriba.
- **Comportamiento de recursos y enlace**: una tarjeta por métrica disponible (latencia, pérdida,
  señal, SNR, CCQ, ruido, capacidad airMAX, voltaje, CPU, memoria, temperatura, clientes) con
  valor actual, promedio y extremo del período, estado *Ahora* y *Pico*, gráfico de tendencia con
  las líneas de umbral y **horas aproximadas fuera de umbral** (advertencia / crítico).
- **Estado de interfaces**: tarjetas (total, UP, DOWN, con errores, con cambios, tráfico total),
  buscador y filtros, y por interfaz: estado, tráfico, errores máximos, cambios de estado,
  velocidad y diagnóstico del período (*Estable*, *Con errores*, *Inestable*, *Sin enlace*).
- **Estaciones asociadas** (radios): señal actual y mínima del período por estación.
- **Problemas agrupados** con buscador y filtros (severidad, categoría, estado): veces,
  horas-evento, primero, último, reconocido y marca **FLAPPING** (3 o más repeticiones); al final,
  los eventos individuales.

### 5.3 Services → SLA report

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
```

**Agregar un equipo nuevo**: agregar un bloque al inventario con `host` (sin espacios, único),
`nombre`, `rol`, `ip`, `padre`, `estado`, `perfiles`, `equipo` y `mapa: [x, y]` (posición en el
mapa, 1000 × 1000). Luego `bin/lagunitas aprovisionar`.

**Cambiar la IP o el padre**: editar el campo y re-aprovisionar (se actualizan interfaz,
dependencias, mapa y servicios).

**Dar de baja un equipo**: pasarlo a `sin_configurar` (queda deshabilitado, conserva el
historial) o quitarlo del inventario y borrar el host en *Data collection → Hosts*.

**Monitorear un equipo por SNMP**: habilitar SNMP en el equipo, comprobarlo con
`bin/lagunitas probar-snmp <ip>`, agregar el perfil `airos_snmp` o `mikrotik_snmp`, definir
`SNMP_COMMUNITY` en `.env` y re-aprovisionar. Paso a paso por tipo de equipo en la
[Guía de integración de equipos](guia-integracion-equipos.md).

**Agregar los equipos secundarios de un sitio** (AP que retransmite, router del hogar): bloque
`dispositivos:` dentro del sitio (ver la guía de integración, §4.3 y §6).

**Ajustar un umbral para un solo equipo** (por ejemplo, un enlace largo con señal naturalmente
más baja): clave `macros:` en su bloque del inventario, por ejemplo
`"{$AIRMAX.SENAL.WARN}": "-78"`, y re-aprovisionar.

El provisionador valida el inventario antes de tocar Zabbix: IPs repetidas, padres inexistentes,
ciclos, roles o estados inválidos.

---

## 7. Pruebas de alarma controladas

Conviene probar periódicamente (por ejemplo, después de cada cambio en la red o una vez por mes)
que la cadena de alertas funciona:

1. Acordar una ventana de prueba con la comunidad y elegir un **equipo de borde** (un router de
   hogar o una radio de cliente), para no dejar sin servicio a otros.
2. Desconectarlo (o bloquear temporalmente el ping desde el servidor en el firewall del Mikrotik).
3. A los ~90 segundos debe aparecer **una sola** alerta "sin respuesta (ICMP)", el equipo en rojo
   en el mapa y "Caído" en el widget; si tiene dependientes, esos quedan "Sin servicio" sin alertas
   propias. Debe llegar la notificación (Telegram/email).
4. Reconectarlo: el problema se cierra solo y llega el aviso de recuperación.
5. Registrar la prueba (fecha, equipo, tiempos de detección y de notificación).

Para trabajos planificados en una torre, crear antes un **mantenimiento** (§4.3) para no disparar
alertas.

---

## 8. Mantenimiento del sistema

| Tarea | Cómo |
|---|---|
| Backup | `COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion scripts/backup.sh /var/backups/zabbix` (base comprimida + export YAML de templates y mapa). Programado por cron diario (Guía de implementación §3.10). |
| Restauración | `COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion scripts/restore.sh /var/backups/zabbix/zabbix_AAAAMMDD_HHMM.sql.gz` (pide confirmación). |
| Chequeo de salud | `bin/lagunitas verificar` |
| Exportar templates | `bin/lagunitas exportar` → `zabbix/export/*.yaml` (importables en otro Zabbix). |
| Actualizar Zabbix | Hacer backup; cambiar el tag `ubuntu-7.0.x` en `deploy/produccion/docker-compose.yml` (misma versión mayor 7.0 LTS); en ese directorio `docker compose pull && docker compose up -d`; luego `bin/lagunitas verificar`. Para pasar a otra versión mayor leer primero las notas de actualización de Zabbix. |
| Rotar la API key de UniFi | Crear la nueva en UniFi, actualizar `UNIFI_API_KEY` en `.env` y `bin/lagunitas aprovisionar --solo hosts`. |
| Historial | Los items guardan 90 días de historia y 1 año de tendencias. Limpieza automática: *Administration → Housekeeping*. |

---

## 9. Resolución de problemas

**Un equipo aparece "Sin datos".** *Monitoring → Latest data* filtrando por el equipo: si el item
muestra un ícono de error, pasar el mouse para ver el motivo. Comprobar que el equipo responda
ping desde el servidor y, si es SNMP, `bin/lagunitas probar-snmp <ip>`.

**Todos los equipos "Sin datos" o caídos a la vez.** En `/opt/zabbix-lagunitas/deploy/produccion`
revisar que el Zabbix server esté arriba (`docker compose ps`) y su log
(`docker compose logs --tail 50 zabbix-server`); luego el enlace/VPN entre el servidor y la red.
Si el gateway Mikrotik también figura caído, el problema es la conexión hacia la red comunitaria.

**Un AP UniFi no reporta.** Si aparece *controlador UniFi no accesible*, el problema es la
aplicación UniFi (encendida, IP y puerto correctos: el puerto de un UniFi OS Server puede cambiar
al reiniciarse). Verificar con `bin/lagunitas unifi-ids <ip-controlador> <puerto>` y corregir
`{$UNIFI.HOST}` / `{$UNIFI.PORT}` en el inventario. Si aparece *sin datos de la API*, revisar la
API key y los IDs de site/dispositivo.

**Un equipo SNMP no reporta datos de radio o energía.** `bin/lagunitas probar-snmp <ip>` muestra
qué responde el equipo. Causas y soluciones en la guía de integración (§12).

**El widget "Red Las Lagunitas" no aparece o el reporte no está en el menú.**
`bin/lagunitas aprovisionar --solo modulos` (registra y habilita los módulos); verificar en
*Administration → General → Modules*. En `deploy/produccion/docker-compose.yml`, las carpetas
`zabbix/modules/*` deben estar montadas en el contenedor web.

**Un widget muestra "No permissions to referred object or it does not exist".** El equipo
seleccionado no tiene ese ítem (por ejemplo, un AP UniFi sin ítems de radio airMAX). Es esperable.

**Docker no arranca tras un reinicio del servidor.** `sudo systemctl enable --now docker`; los
contenedores tienen `restart: unless-stopped` y vuelven solos.

**Cambios hechos a mano en Zabbix desaparecieron.** El provisionador sobrescribe los objetos que
gestiona. Hacer el cambio en el inventario o en el código del proyecto.

**Recuperar desde cero.** Stack nuevo + `scripts/restore.sh <último backup>`; o bien stack nuevo
vacío + `bin/lagunitas aprovisionar` (recrea toda la configuración, sin el historial).

---

## 10. Referencia rápida

```bash
cd /opt/zabbix-lagunitas
bin/lagunitas aprovisionar                    # aplicar inventario y configuración
bin/lagunitas aprovisionar --solo mapa        # un paso puntual
bin/lagunitas verificar                       # salud
bin/lagunitas validar                         # valida el inventario (sin Zabbix)
bin/lagunitas probar-snmp <ip>                # prueba SNMP antes de integrar un equipo
bin/lagunitas unifi-ids <ip> <puerto>         # IDs de site/AP de un controlador UniFi
COMPOSE_DIR=deploy/produccion scripts/backup.sh /var/backups/zabbix   # respaldo
(cd deploy/produccion && docker compose ps)   # estado del stack
(cd deploy/produccion && docker compose logs --tail 50 zabbix-server)   # logs
```
