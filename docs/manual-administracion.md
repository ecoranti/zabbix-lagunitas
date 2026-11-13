# Manual de administración

**Versión 2.3** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas

Referencia operativa del día a día: cómo leer el estado de la red, atender alarmas, dar de alta
o de baja equipos, generar reportes, respaldar y resolver los problemas más frecuentes. La
instalación está en la [Guía de implementación](guia-implementacion.md) y la incorporación de
equipos en la [Guía de integración de equipos](guia-integracion-equipos.md).

**Alcance.** Los procedimientos se verificaron en el laboratorio (red simulada más un access
point UniFi real). El despliegue sobre la red física quedó pendiente, de modo que las rutas
`/opt/zabbix-lagunitas` y `/var/backups/zabbix` y el nombre `<ZBX_DOMAIN>` corresponden a la
instalación prevista en la Guía de implementación. Salvo indicación en contrario, los comandos
se ejecutan en el servidor de monitoreo desde la carpeta del proyecto.

---

## Conceptos clave

| Concepto | Significado |
|---|---|
| **Inventario** | `config/inventory.*.yaml`: lista de equipos con rol, IP, padre y estado. Es la fuente de verdad: los cambios se hacen ahí y se aplican con `bin/lagunitas aprovisionar`. Los cambios manuales en Zabbix sobre objetos gestionados se pisan en el siguiente aprovisionamiento. |
| **Rol** | Gateway (salida a Internet), Torre (backbone), Nodo intermedio, Hogar, Institución, Access point. |
| **Sitio y dispositivos** | Un sitio del mapa (torre, nodo, hogar) puede tener varios equipos con IP: el principal y sus *dispositivos* (por ejemplo, la radio que recibe, el AP que retransmite y el router del hogar). Cada uno es un host con sus propias métricas. El mapa y el SLA trabajan por sitio. |
| **Perfiles** | Cómo se monitorea cada equipo: `icmp` (disponibilidad), `airos_snmp` (radios airMAX), `mikrotik_snmp` (routers Mikrotik), `unifi_api` (AP UniFi). |
| **Estado del tramo** | `operativo` (monitoreado), `en_proceso` o `sin_configurar` (el equipo existe en Zabbix pero deshabilitado; en el mapa se ve en gris). |
| **Padre** | Equipo del que depende la conectividad. Define las dependencias de alarmas y la disponibilidad *de servicio*. |
| **Disponibilidad propia** | Porcentaje del tiempo en que el propio equipo respondió. |
| **Disponibilidad del servicio** | Descuenta además las caídas de sus ancestros: lo que realmente vivió el hogar. |
| **MTTR** | Tiempo medio de recuperación: duración promedio de las caídas ya resueltas del período. |

### Objetos que crea el provisionador

| Tipo | Nombre |
|---|---|
| Grupos de hosts | `Las Lagunitas` y subgrupos `Gateway`, `Torres`, `Nodos`, `Hogares e instituciones`, `Access points` |
| Templates | `Lagunitas - Disponibilidad ICMP`, `Lagunitas - Ubiquiti airMAX por SNMP`, `Lagunitas - Mikrotik por SNMP`, `Lagunitas - AP UniFi por API` (grupo `Templates/Las Lagunitas`). En el laboratorio se suma `Lagunitas - Disponibilidad ICMP - sonda externa` |
| Macro global | `{$LAGUNITAS.INTERVALO}` (intervalo de todas las mediciones) |
| Mapa | `Las Lagunitas - Topología` |
| Dashboard | `Las Lagunitas - Centro de monitoreo` |
| Servicios / SLA | `Red Las Lagunitas` (y sub-servicios por rol y por sitio) · SLA `Las Lagunitas - Disponibilidad mensual` (objetivo 99,5 %) |
| Alertas | Grupo `Operadores Las Lagunitas` · Acción `Las Lagunitas - Notificar caídas` |
| Módulos | `Red Las Lagunitas` (widget) · `Reporte de disponibilidad - Las Lagunitas` |

---

## Acceso

Frontend: `https://<ZBX_DOMAIN>` (nombre definido en la instalación).

Usuarios: `Admin` (super administrador; contraseña cambiada en la instalación) y los operadores
que se creen en el grupo **Operadores Las Lagunitas** (permiso de lectura sobre la red y
destinatarios de las notificaciones). Para crear un operador: *Users → Users → Create user*,
grupo *Operadores Las Lagunitas*, rol *User role*; en la pestaña *Media* cargar su medio de
contacto.

> El paso `alertas` del aprovisionamiento vuelve a definir el grupo de operadores con el usuario
> `Admin` como miembro. Después de ejecutar `bin/lagunitas aprovisionar`, comprobar en *Users →
> User groups* que los operadores creados a mano sigan en el grupo y volver a agregarlos si hace
> falta. Las notificaciones por Telegram no dependen de esto, porque se envían al grupo de
> Telegram a través del usuario `Admin`.

---

## Uso diario: el Centro de monitoreo

*Dashboards → Las Lagunitas - Centro de monitoreo*. Tiene las páginas *Estado de la red*,
*Equipos*, *Detalle por equipo*, *AP UniFi* (solo si el inventario incluye un AP UniFi operativo)
y *SLA*; con **Start slideshow** rotan automáticamente, útil para una pantalla fija.

### Página "Estado de la red"

- **Panal de equipos**: un hexágono por equipo monitoreado, verde o rojo.
- **Problemas por severidad** y **Alertas activas** en tiempo real.
- **Mapa de topología**: un ícono por sitio, con las mismas convenciones que el esquema de campo
  (línea sólida = operativo, discontinua = en proceso, punteada = sin configurar). Un tramo se
  pinta **rojo y grueso** cuando cae el equipo principal del sitio del extremo. Clic en un
  sitio → *Detalle del equipo* o *Problemas del equipo*.

### Página "Equipos" (widget Red Las Lagunitas)

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
    ancho de canal, potencia, distancia, antena, DFS, tasas TX/RX, CPU y memoria, temperatura.
  - *Estaciones* (airMAX): cada equipo conectado a la radio con su señal, ruido, CCQ, calidad,
    capacidad, tasas, distancia, latencia y tiempo conectado.
  - *Router y energía* (Mikrotik): voltaje, CPU, memoria, temperatura, clientes DHCP, estado de
    Internet (PPPoE), modelo, RouterOS, firmware, número de serie.
  - *Interfaces*: estado, tráfico entrante y saliente, errores y velocidad de cada interfaz.
  - *Problemas*: los activos y los incidentes de los últimos 30 días con su duración (hasta 20).
  - *Rendimiento*: gráficos de latencia, pérdida y disponibilidad (1 h / 24 h / 7 d / 30 d).
  - *Dependencias*: camino hasta el backbone y **qué equipos quedan sin servicio si este cae**.
  - *UniFi* (solo AP): estado, modelo, firmware, reintentos por banda y uplink.

Significado de los estados:

| Estado | Significado | Acción |
|---|---|---|
| **En línea** | Responde y no tiene problemas activos de severidad Warning o mayor. | — |
| **Advertencia** | Responde, pero tiene algún problema activo de severidad Warning o mayor (pérdida, latencia, señal, energía, recursos). | Abrir el equipo y revisar la pestaña *Problemas*. |
| **Caído** | No responde y su trigger de caída está activo. | Atender (ver *Alarmas*). |
| **Sin servicio** | No responde porque cayó un equipo del que depende (se indica cuál). | Atender la causa raíz, no este equipo. |
| **Sin datos** | Zabbix no recibe valores de disponibilidad hace más de 5 min (ítem con error o chequeo detenido). | Ver *Resolución de problemas*. |
| **Mantenimiento** | El equipo está dentro de un período de mantenimiento. Se cuenta en la tarjeta *No monitoreados*. | — |
| **No monitoreado** | Tramo en proceso o sin configurar (host deshabilitado). | — |

Los colores de las barras y de los valores son ayudas visuales con niveles propios, algo más
exigentes que los de las alarmas: latencia en amarillo desde 100 ms y en rojo desde 150 ms,
pérdida desde 5 % y 20 %, disponibilidad de 24 h por debajo de 99,5 % y de 95 %, señal por debajo
de -72 dBm y de -80 dBm. Un valor en amarillo no implica que haya una alarma.

### Página "Detalle por equipo"

Navegador de equipos agrupado por rol (sin los access points, que tienen su página): al elegir
uno, todos los widgets de la página (estado, disponibilidad de 24 h y de 7 días, latencia,
gráficos y problemas) muestran ese equipo.

### Páginas "AP UniFi" y "SLA"

- *AP UniFi*: estado, uptime, firmware y controlador; CPU, memoria, clientes y reintentos; tráfico
  del uplink y reintentos por banda; latencia y pérdida por ICMP; disponibilidad según UniFi;
  evolución de CPU y memoria y de clientes; y los problemas del AP.
- *SLA*: cumplimiento mensual por sitio (servicio) y ranking de disponibilidad de 7 días de
  todos los equipos.

Además, cada equipo tiene su **dashboard propio** (*Monitoring → Hosts → columna Dashboards*),
generado por su template.

---

## Alarmas

### Severidades y notificación

| Severidad | Uso en esta red | Se notifica |
|---|---|---|
| Disaster | Pérdida del enlace a Internet | Sí |
| High | Equipo sin respuesta, AP fuera de línea, voltaje crítico | Sí |
| Average | Sin datos SNMP o de la API, interfaz sin enlace, radio AP sin estaciones, señal crítica, voltaje excesivo | Sí |
| Warning | Degradación: señal, ruido, SNR, CCQ, pérdida, latencia, recursos, temperatura, voltaje bajo | No (se ve en dashboards y reportes) |
| Information | Reinicios, cambios de firmware o de frecuencia, capacidad airMAX baja | No |

### Catálogo de alarmas y respuesta

Las condiciones exactas, las macros y el fundamento de cada umbral están en la
[Guía de integración de equipos](guia-integracion-equipos.md). El nombre de cada problema empieza
con el nombre del equipo.

**Disponibilidad (todos los equipos, template Lagunitas - Disponibilidad ICMP):**

| Alarma | Condición | Severidad | Qué hacer |
|---|---|---|---|
| Sin respuesta (ICMP) | Sin respuesta al ping durante `{$ICMP.CAIDA.PERIODO}`: 90 s en el gateway y 15 s más por cada nivel de la topología | High | Procedimiento *Qué hacer ante una caída* |
| Pérdida de paquetes alta | Mínimo de 5 min mayor que 20 % | Warning | Revisar señal y CCQ del enlace hacia el padre; buscar saturación o interferencia |
| Latencia alta | Promedio de 5 min mayor que 0,15 s | Warning | Revisar tráfico de las interfaces y calidad del enlace |

**Radios airMAX:**

| Alarma | Condición | Severidad | Qué hacer |
|---|---|---|---|
| Señal débil / crítica | Promedio de 10 min menor que -75 / -82 dBm | Warning / Average | Alineación, obstrucciones (vegetación), potencia del otro extremo, conectores |
| Ruido alto en el canal | Promedio de 15 min mayor que -85 dBm | Warning | Interferencia: evaluar cambio de frecuencia o de ancho de canal con airView |
| SNR bajo | Promedio de 15 min menor que 20 dB | Warning | Mejorar la señal o reducir el ruido |
| CCQ bajo | Promedio de 15 min menor que 75 % | Warning | Interferencia o señal marginal |
| Calidad / capacidad airMAX baja | Promedio de 15 min menor que 60 % / 40 % | Warning / Information | Enlace inestable o degradado: revisar las anteriores |
| Radio AP sin estaciones asociadas | 0 estaciones durante 5 min | Average | El enlace con las estaciones remotas cayó: revisar los equipos que dependen del AP |
| Señal débil de la estación | Promedio de 10 min menor que -75 dBm | Warning | Revisar la estación indicada en el nombre del problema |
| Interfaz sin enlace | La interfaz pasó de *up* a *down* | Average | Cable, conector (humedad) o equipo vecino. Se cierra sola cuando la interfaz vuelve; admite cierre manual |
| Errores en la interfaz | Más de 2 errores de entrada por segundo durante 5 min | Warning | Cable o conector dañado |
| Sin datos SNMP | 5 min sin respuesta SNMP con el equipo respondiendo al ping | Average | Verificar agente SNMP, comunidad y firewall: `bin/lagunitas probar-snmp <ip>` |
| CPU, memoria o temperatura altas | Más de 90 %, 90 % o 75 °C | Warning | Correlacionar con el tráfico; ventilación y exposición solar |
| Reinicio, cambio de firmware o de frecuencia | Uptime menor que 10 min o cambio de valor | Information | Confirmar que fue intencional y cerrar el problema a mano. Reinicios nocturnos repetidos sugieren batería insuficiente |

**Router Mikrotik:**

| Alarma | Condición | Severidad | Qué hacer |
|---|---|---|---|
| Sin enlace a Internet | Interfaz WAN distinta de *up*, o sin datos de esa interfaz durante 5 min | Disaster | Procedimiento *Sin enlace a Internet* |
| Voltaje bajo / crítico | Promedio menor que 12,0 V (10 min) / 11,6 V (5 min) | Warning / High | Procedimiento *Voltaje bajo o crítico* |
| Voltaje excesivo | Promedio de 10 min mayor que 14,8 V | Average | Posible falla del regulador de carga: revisar en sitio |
| Sin clientes DHCP | 0 leases durante 30 min | Warning | Falla de la red de distribución o del servidor DHCP |
| CPU, memoria o temperatura altas | Más de 85 %, 90 % o 65 °C | Warning | Correlacionar con el tráfico; ventilación del gabinete |
| Interfaz sin enlace / con errores | Igual que en las radios | Average / Warning | Cable, conector o equipo vecino |
| Sin datos SNMP | 5 min sin respuesta SNMP | Average | Verificar `/snmp` en el router y el firewall (UDP 161 desde el servidor) |
| Reinicio, cambio de versión de RouterOS | Uptime menor que 10 min o cambio de valor | Information | Confirmar y cerrar a mano |

**Access points UniFi:**

| Alarma | Condición | Severidad | Qué hacer |
|---|---|---|---|
| Controlador UniFi no accesible | Puerto HTTPS del controlador cerrado durante 3 min | Average | Ver *Un AP UniFi no reporta* |
| Sin datos de la API de UniFi | Sin estadísticas por `{$AP.SIN.DATOS}` (5 min) | Average | Revisar la API key y los ID de site y de dispositivo |
| AP fuera de línea según UniFi | El controlador informa un estado distinto de ONLINE | High | Alimentación (PoE) y cableado del AP |
| Uso de CPU / memoria alto | Mínimo de 5 min mayor que 85 % | Warning | Observar; reiniciar el AP si persiste |
| Reintentos altos en 2.4 / 5 / 6 GHz | Promedio de 15 min mayor que `{$AP.REINTENTOS.WARN}` (20 %) | Warning | Interferencia o canal saturado: cambiar de canal |
| El AP se reinició / cambió el firmware | Uptime menor que 10 min o cambio de versión | Information | Confirmar y cerrar a mano |

### Una caída troncal genera una sola alerta

Las advertencias dependen del trigger de caída del mismo equipo, y el trigger de caída de cada
equipo depende del de su padre. Para que esto funcione cuando padre e hijos caen a la vez, cada
nivel tarda 15 s más que su padre en declarar la caída (90 s el gateway, 105 s las torres que
cuelgan de él, 120 s el nivel siguiente y así hasta 225 s en el equipo más profundo del
inventario actual). El aprovisionamiento lo calcula desde el inventario (macro
`{$ICMP.CAIDA.PERIODO}` de cada host). Sin este escalonado, un hijo que se detecta un segundo
antes que su padre genera una alerta propia.

La excepción es el gateway: si el Mikrotik deja de responder, a la alerta "sin respuesta (ICMP)"
se suma a los 5 minutos "sin enlace a Internet", porque esa alarma también se activa por falta
de datos.

### Qué hacer ante una caída

1. Abrir el equipo en la página *Equipos* → pestaña *Dependencias* para ver el impacto.
2. Revisar si otros equipos del mismo tramo están "Sin servicio" (confirma que el problema es de
   ese equipo o de su enlace hacia el padre).
3. Comprobar desde el servidor si el equipo responde:

   ```bash
   cd /opt/zabbix-lagunitas/deploy/produccion
   docker compose exec zabbix-server fping -c3 <IP>
   ```

4. Si el padre es una radio airMAX, mirar en su pestaña *Estaciones* si el equipo caído sigue
   asociado. Si figura asociado, el enlace de radio funciona y el problema es de red o del propio
   equipo; si no figura, es el enlace o la alimentación del sitio.
5. Causas habituales en la red: **alimentación** (panel solar, batería de 12 V, controlador de
   carga), **desalineación** de antenas por viento, **equipo colgado** (reinicio remoto o en
   sitio), **corte del enlace troncal**.
6. Registrar lo actuado: en *Alertas activas* → columna *Update* → *Acknowledge* con un mensaje
   (queda en el historial del problema y se notifica al grupo).
7. Al volver el equipo, el problema se cierra solo y llega el aviso de recuperación.

### Sin enlace a Internet

1. Verificar si el gateway tiene además "sin respuesta (ICMP)" o "sin datos SNMP". Si es así, el
   problema es el router o el camino entre el servidor y la red, y se atiende como una caída.
2. Si el gateway responde, abrir su detalle → *Router y energía* e *Interfaces* y mirar el estado
   de la interfaz WAN (por defecto `pppoe-out1`) y de la interfaz física por la que sale.
3. Con la interfaz física en *up* y la sesión PPPoE caída, el problema es del lado del proveedor
   (Cooperativa de Alpa Corral) o de las credenciales PPPoE: contactar al proveedor.
4. Con la interfaz física en *down*, revisar el cable o el equipo de acceso del proveedor.

La red interna puede seguir funcionando mientras tanto: los equipos se ven "En línea".

### Voltaje bajo o crítico

1. Abrir el gateway → *Rendimiento* → gráfico de voltaje con el rango de 7 días. Una batería sana
   baja de noche y se recupera de día.
2. Si la recuperación diurna es cada vez menor: panel sucio o sombreado, o varios días nublados.
3. Si el voltaje cae rápido aun con días de sol: batería agotada o regulador defectuoso.
4. Con **voltaje crítico** (menos de 11,6 V) el corte del nodo es inminente: avisar a la
   comunidad y planificar la visita.

### Mantenimientos programados

Antes de trabajar en una torre (cambio de batería, realineación), crear un mantenimiento para no
generar alertas: *Data collection → Maintenance → Create maintenance period*, elegir los hosts
(la torre y, si corresponde, los equipos que dependen de ella) y el horario. Durante el
mantenimiento los equipos figuran con el estado "Mantenimiento" en el widget, sus problemas no se
notifican y el reporte permite excluir esos eventos.

### Ajustar umbrales

Los umbrales son **macros**.

- **En un solo equipo** (por ejemplo, un enlace largo con señal naturalmente más baja): clave
  `macros:` en su bloque del inventario y `bin/lagunitas aprovisionar --solo hosts`.

  ```yaml
      macros:
        "{$AIRMAX.SENAL.WARN}": "-78"
  ```

  Una macro cargada a mano en *Data collection → Hosts → Macros* sirve para una prueba, pero se
  pierde en el siguiente aprovisionamiento.
- **En toda la red**: editar el valor por defecto en `lagunitas/templates.py` (ICMP y UniFi) o en
  `lagunitas/templates_snmp.py` (airMAX y Mikrotik) y ejecutar
  `bin/lagunitas aprovisionar --solo templates`.

### Frecuencia de actualización

| Qué | Frecuencia | Dónde se cambia |
|---|---|---|
| Mediciones de todos los equipos (ICMP, SNMP, API UniFi, interfaces y estaciones) | 10 s | Macro global `{$LAGUNITAS.INTERVALO}` |
| Disponibilidad de 24 h y de 7 días (ítems calculados) | 1 min | `lagunitas/templates.py` |
| Datos estáticos (modelo, firmware, SSID, antena, número de serie, velocidad de interfaz) | 1 h | `lagunitas/templates_snmp.py` |
| Descubrimiento de estaciones y del enlace a Internet / de interfaces | 10 min / 1 h | `lagunitas/templates_snmp.py` |
| Widgets de los dashboards | 10 s | `REFRESCO_WIDGETS` en `lagunitas/model.py` |
| Pantallas del frontend (*Problems*, *Latest data*, etc.) | 10 s | El paso `servidor` del aprovisionamiento lo fija en 10 s para todos los usuarios |

Los triggers se evalúan con cada dato nuevo, así que también reaccionan cada 10 s. Sus ventanas
(por ejemplo, "promedio de 5 min") son de tiempo y no cambian con el intervalo.

Para cambiar el intervalo en toda la red **sin reaprovisionar**: *Administration → Macros* →
`{$LAGUNITAS.INTERVALO}`. El aprovisionamiento respeta un valor ajustado a mano. Si los enlaces de
radio se saturan o el servidor queda corto de recursos, subirlo a `30s` o `1m`.

### Notificaciones

La acción *Las Lagunitas - Notificar caídas* avisa los problemas de severidad Warning o mayor al
grupo *Operadores Las Lagunitas* por todos sus medios, envía un recordatorio a los 30 minutos si
el problema sigue abierto y avisa la recuperación y las actualizaciones (por ejemplo, un
*Acknowledge*). Los problemas suprimidos por mantenimiento no se notifican. Configuración de
Telegram: ver la Guía de implementación, sección *Notificaciones por Telegram*.

Para agregar a otra persona: sumarla al grupo de Telegram de operadores (no hace falta tocar
Zabbix). Para comprobar que el canal funciona: `bin/lagunitas probar-telegram`, que envía un
mensaje de prueba y revisa la configuración de seguridad del bot. Si las alertas no llegan,
revisar *Reports → Action log* (columna *Info* con el error de Telegram).

El bot es de solo envío y lo que se le escriba no tiene efecto. Si aparecen mensajes que no
generó Zabbix, el token está comprometido: revocarlo como indica la Guía de implementación
(*Seguridad del bot de Telegram*).

### Cómo leer las métricas de radio y energía

| Métrica | Bien | Revisar | Mal | Acción típica |
|---|---|---|---|---|
| Señal (airMAX) | -50 a -65 dBm | -65 a -75 dBm | Menor que -75 dBm | Alineación, obstrucciones (árboles), potencia del otro extremo |
| Piso de ruido | -90 a -100 dBm | -85 a -90 dBm | Mayor que -85 dBm | Interferencia: cambiar frecuencia o reducir ancho de canal (airView) |
| SNR | Mayor que 30 dB | 20 a 30 dB | Menor que 20 dB | Mejorar señal o reducir ruido |
| CCQ | Mayor que 90 % | 75 a 90 % | Menor que 75 % | Interferencia o señal marginal |
| Calidad / capacidad airMAX | Mayor que 80 % / 60 % | | Menor que 60 % / 40 % | Enlace inestable o degradado |
| Voltaje (Mikrotik, batería de 12 V) | 12,4 a 14,5 V | 12,0 a 12,4 V | Menor que 11,6 V o mayor que 14,8 V | Panel sucio o sombreado, días nublados, batería o regulador |
| Clientes DHCP | Habitual del sitio | Caída brusca | 0 | Falla de la red de distribución o del DHCP |
| Temperatura (Mikrotik) | Menor que 55 °C | 55 a 65 °C | Mayor que 65 °C | Ventilación del gabinete, exposición solar |

---

## Reportes

### Reports → Disponibilidad de la red

1. Filtros: **Tipo de reporte** (técnico o gerencial), **Período** (hoy, 24 h, 7 días, 30 días, mes
   actual, mes anterior o personalizado con fechas), **Grupo**, **Equipo**, **Tipo de equipo**
   (radios airMAX, Mikrotik, solo ICMP, AP UniFi), **Mantenimientos** (excluir o incluir los
   eventos suprimidos) y **SLA objetivo** (99,5 % por defecto). Pulsar **Generar reporte**.
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
6. **Exportar CSV** (separador `;`, abre directo en Excel o LibreOffice) o **Imprimir / Guardar
   PDF** (A4 apaisado; en el diálogo elegir "Guardar como PDF").

La vista *gerencial* oculta los datos técnicos (indicador, disponibilidad propia, MTTR, mayor
caída): está pensada para rendir cuentas a la comunidad o a financiadores.

La disponibilidad se calcula a partir de los eventos del trigger de caída de cada equipo, no de
las mediciones individuales. Las estadísticas de métricas del detalle técnico usan las tendencias
horarias (que se conservan un año) y recurren al historial solo en períodos cortos.

### Detalle técnico de un equipo

Botón **Ver detalle** del reporte (o *Detalle técnico (7 días)* desde el modal del widget):

- **Tarjetas**: disponibilidad propia (y por qué indicador), disponibilidad del servicio, SLA,
  mantenimiento, caída propia y MTTR, problemas del período, problemas activos, tiempo afectado
  único (sin duplicar alertas simultáneas), horas-evento acumuladas, salud operativa y equipos
  dependientes.
- **Conclusiones y recomendaciones** según el tipo de equipo: señal pobre (revisar alineación y
  obstrucciones), interferencia (cambiar frecuencia), batería en descarga (revisar panel y
  regulador), picos de CPU o memoria, pérdida de paquetes, problemas con *flapping*, horas sin
  servicio por caídas aguas arriba.
- **Comportamiento de recursos y enlace**: una tarjeta por métrica disponible (latencia, pérdida,
  señal, SNR, CCQ, ruido, calidad y capacidad airMAX, voltaje, CPU, memoria, temperatura,
  clientes) con valor actual, promedio y extremo del período, estado *Ahora* y *Pico*, gráfico de
  tendencia con las líneas de umbral y **horas aproximadas fuera de umbral** (advertencia /
  crítico). Estos niveles son los de observación del reporte, más exigentes que los de las
  alarmas (por ejemplo, señal -72 / -80 dBm, SNR 25 / 15 dB, CCQ 85 / 70 %).
- **Estado de interfaces**: tarjetas (total, UP, DOWN, con errores, con cambios, tráfico total),
  buscador y filtros, y por interfaz: estado, tráfico, errores máximos, cambios de estado,
  velocidad y diagnóstico del período (*Estable*, *Con errores*, *Inestable*, *Sin enlace*).
- **Estaciones asociadas** (radios): señal actual y mínima del período por estación.
- **Problemas agrupados** con buscador y filtros (severidad, categoría, estado): veces,
  horas-evento, primero, último, reconocido y marca **FLAPPING** (3 o más repeticiones); al final,
  los eventos individuales.

### Services → SLA report

Reporte nativo de Zabbix del SLA mensual *Las Lagunitas - Disponibilidad mensual* (objetivo
99,5 %). Hay un servicio por cada sitio operativo, agrupados por rol, y solo cuentan las caídas
(no las advertencias). Es útil para ver la evolución mes a mes.

---

## Gestión de equipos

Todas las operaciones se hacen editando el inventario y reaprovisionando. Circuito general:

 ```bash
 cd /opt/zabbix-lagunitas
 nano config/inventory.produccion.yaml        # o el editor que se prefiera
 bin/lagunitas validar                         # revisa el inventario sin tocar Zabbix
 bin/lagunitas aprovisionar                    # aplica los cambios
 bin/lagunitas verificar                       # chequeo de salud
 ```

`validar` detecta nombres duplicados o con espacios, IP faltantes o repetidas, padres
inexistentes, ciclos, y roles, estados, funciones o perfiles inválidos. El aprovisionamiento
ejecuta la misma validación antes de tocar Zabbix.

**Activar un tramo que estaba en proceso** (por ejemplo Franco):

 ```yaml
   - host: Nodo_Franco
     estado: operativo        # antes: en_proceso
 ```

**Agregar un sitio nuevo**: agregar un bloque al inventario con `host` (sin espacios, único),
`nombre`, `rol`, `ip`, `padre`, `estado`, `perfiles`, `funcion`, `modelo`, `equipo` y
`mapa: [x, y]` (posición en el mapa, de 1000 × 1010 puntos; la franja inferior está ocupada por
la leyenda). Antes, preparar y probar el equipo como indica la
[Guía de integración de equipos](guia-integracion-equipos.md).

**Agregar los equipos secundarios de un sitio** (AP que retransmite, router del hogar): bloque
`dispositivos:` dentro del sitio (ver la guía de integración, secciones *Cargar en el inventario*
y *Routers airCube*).

**Cambiar la IP o el padre**: editar el campo y reaprovisionar (se actualizan interfaz,
dependencias, tiempos de detección de caída, mapa y servicios).

**Monitorear un equipo por SNMP**: habilitar SNMP en el equipo, comprobarlo con
`bin/lagunitas probar-snmp <ip>`, agregar el perfil `airos_snmp` o `mikrotik_snmp`, verificar que
`SNMP_COMMUNITY` esté definida en `.env` y reaprovisionar.

**Dar de baja un equipo**:

- Baja temporal: pasarlo a `sin_configurar` o `en_proceso`. El host queda deshabilitado, conserva
  su historial y su servicio se quita del SLA.
- Baja definitiva: quitar su bloque del inventario, cambiar el `padre` de los equipos que
  dependían de él, reaprovisionar y luego borrar el host en *Data collection → Hosts* (el
  provisionador no elimina hosts). Al borrarlo se pierde su historial.

**Cambiar el nombre técnico** (`host`): no se recomienda, porque para Zabbix es un equipo nuevo.
Si es imprescindible, tratarlo como una baja definitiva más un alta. El nombre visible
(`nombre`) sí puede cambiarse libremente.

---

## Pruebas de alarma controladas

Conviene probar periódicamente (por ejemplo, después de cada cambio en la red o una vez por mes)
que la cadena de alertas funciona:

1. Acordar una ventana de prueba con la comunidad y elegir un **equipo de borde** (un router de
   hogar o una radio de cliente), para no dejar sin servicio a otros.
2. Desconectarlo (o bloquear temporalmente el ping desde el servidor en el firewall del Mikrotik).
3. Esperar el tiempo de detección de ese equipo: 90 s más 15 s por cada nivel que lo separa del
   gateway (entre 2 y 4 minutos para un equipo de borde; el valor exacto es su macro
   `{$ICMP.CAIDA.PERIODO}`). Debe aparecer **una sola** alerta "sin respuesta (ICMP)", el sitio
   en rojo en el mapa y "Caído" en el widget; si tiene dependientes, esos quedan "Sin servicio"
   sin alertas propias. Debe llegar la notificación.
4. Reconectarlo: el problema se cierra solo y llega el aviso de recuperación.
5. Registrar la prueba (fecha, equipo, tiempos de detección y de notificación).

Para trabajos planificados en una torre, crear antes un **mantenimiento** (ver *Mantenimientos
programados*) para no disparar alertas. En el laboratorio las mismas pruebas se hacen con
`bin/lagunitas lab caida` y `bin/lagunitas lab escenario` (ver la
[Guía del laboratorio](laboratorio.md)); esos comandos no se usan en producción.

---

## Mantenimiento del sistema

### Tareas periódicas

| Tarea | Frecuencia sugerida | Cómo |
|---|---|---|
| Revisar el Centro de monitoreo y las alertas sin reconocer | Diaria | Página *Estado de la red* |
| Comprobar que el backup se generó | Semanal | `ls -lh /var/backups/zabbix` (un `zabbix_*.sql.gz` y un `config_*.tar.gz` por día) |
| Chequeo de salud | Semanal y después de cada cambio | `bin/lagunitas verificar` |
| Prueba de alarma controlada y del canal de Telegram | Mensual | *Pruebas de alarma controladas* y `bin/lagunitas probar-telegram` |
| Reporte de disponibilidad | Mensual | *Reports → Disponibilidad de la red*, período "Mes anterior" |
| Espacio en disco del servidor | Mensual | `df -h` y `docker system df` |
| Restauración de prueba del backup | Semestral | En un stack de prueba, nunca sobre producción |

### Backup

 ```bash
 cd /opt/zabbix-lagunitas
 COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion scripts/backup.sh /var/backups/zabbix
 ```

Genera dos archivos con la fecha y la hora en el nombre:

- `zabbix_AAAAMMDD_HHMM.sql.gz`: volcado completo de la base (configuración e historial). El
  script verifica que el volcado haya terminado bien y, si no, sale con error.
- `config_AAAAMMDD_HHMM.tar.gz`: inventarios (`config/`) y export YAML de templates y mapa
  (`zabbix/export/`).

Borra los respaldos de más de 14 días (variable `RETENCION_DIAS`). La programación diaria por
cron y la copia fuera del servidor están en la Guía de implementación, sección *Backups*.

Los archivos `.env` y `deploy/produccion/.env` **no** se incluyen en el backup. Guardar una copia
en un lugar seguro, porque sin ellos no se puede reconstruir el servidor.

### Restauración

 ```bash
 cd /opt/zabbix-lagunitas
 COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion scripts/restore.sh /var/backups/zabbix/zabbix_AAAAMMDD_HHMM.sql.gz
 bin/lagunitas verificar
 ```

- Reemplaza **toda** la configuración y el historial actuales por los del respaldo.
- Antes de detener nada comprueba que el archivo sea un gzip íntegro, que el volcado esté completo
  y que la base esté en marcha; si algo falla, no modifica el sistema.
- Pide escribir `RESTAURAR` para continuar; detiene el Zabbix server y el frontend, carga el
  volcado y los vuelve a iniciar, también si la importación falla.
- Los datos posteriores al respaldo se pierden. Si después de ese respaldo cambió el inventario,
  ejecutar `bin/lagunitas aprovisionar` para volver a aplicar la configuración vigente.

### Historial y espacio en disco

- Los ítems principales guardan 90 días de historial; el tráfico y los errores de interfaces y
  los datos de estaciones, 30 días. Las tendencias horarias se conservan 365 días. La limpieza es
  automática (*Administration → Housekeeping*).
- **Retención global.** La clave opcional `retencion_historial` del inventario (por ejemplo
  `retencion_historial: 7d`) hace que el paso `servidor` del aprovisionamiento active en
  *Housekeeping* la retención global del historial con ese período, para todos los ítems. Las
  tendencias no cambian. El inventario del laboratorio la define en 7 días, porque con mediciones
  cada 10 s el historial de 90 días ocupa varios GB; el de producción no la define y conserva
  los valores de cada ítem.
- Con una retención global menor, los gráficos de detalle fino solo cubren ese período; los
  reportes y los gráficos de períodos largos siguen disponibles porque usan las tendencias.
- Quitar la clave del inventario no revierte el cambio: para volver a la retención por ítem,
  desmarcar *Override item history period* en *Administration → Housekeeping*.
- Las otras palancas para reducir el volumen son el intervalo `{$LAGUNITAS.INTERVALO}` y la
  cantidad de equipos con SNMP.
- **Registros binarios de MySQL.** En producción se purgan solos al cabo de un día. En el
  laboratorio están desactivados (`--skip-log-bin` en `docker-compose.yml`), porque sin
  replicación solo ocupaban disco.

### Otras tareas

| Tarea | Cómo |
|---|---|
| Exportar templates y mapa | `bin/lagunitas exportar` → `zabbix/export/*.yaml` (importables en otro Zabbix). El backup lo ejecuta automáticamente. |
| Actualizar Zabbix | Hacer backup; cambiar el tag `ubuntu-7.0.x` de las tres imágenes de Zabbix en `deploy/produccion/docker-compose.yml` (misma versión mayor 7.0 LTS); en ese directorio `docker compose pull && docker compose up -d`; luego `bin/lagunitas verificar`. Detalle en la Guía de implementación, sección *Actualización*. |
| Rotar la API key de UniFi | Crear la nueva en UniFi, actualizar `UNIFI_API_KEY` en `.env` y ejecutar `bin/lagunitas aprovisionar --solo hosts`. |
| Cambiar la comunidad SNMP | Cambiarla en los equipos, actualizar `SNMP_COMMUNITY` en `.env` y ejecutar `bin/lagunitas aprovisionar --solo hosts`. |
| Rotar el token del bot de Telegram | Guía de implementación, sección *Seguridad del bot de Telegram*. |

---

## Resolución de problemas

**Un equipo aparece "Sin datos".** *Monitoring → Latest data* filtrando por el equipo: si el ítem
muestra un ícono de error, pasar el mouse para ver el motivo. Comprobar que el equipo responda
ping desde el servidor y, si es SNMP, `bin/lagunitas probar-snmp <ip>`.

**Todos los equipos "Sin datos" o caídos a la vez.** En `/opt/zabbix-lagunitas/deploy/produccion`
revisar que el Zabbix server esté arriba (`docker compose ps`) y su log
(`docker compose logs --tail 50 zabbix-server`); luego el enlace o la VPN entre el servidor y la
red. Si el gateway Mikrotik también figura caído, el problema es la conexión hacia la red
comunitaria.

**El chequeo de salud lista ítems no soportados.** `bin/lagunitas verificar` muestra el equipo, el ítem y el error.
Son esperables la CPU y la temperatura en radios con airOS 6 y el voltaje en routers sin sensor
(se pueden deshabilitar en el host). Un error de tiempo de espera o de autenticación indica un
problema de SNMP o de la API.

**Un AP UniFi no reporta.** Si aparece *controlador UniFi no accesible*, el problema es la
aplicación UniFi (encendida, IP y puerto correctos: el puerto de un UniFi OS Server puede cambiar
al reiniciarse). Verificar con `bin/lagunitas unifi-ids <ip-controlador> <puerto>` y corregir
`{$UNIFI.HOST}` y `{$UNIFI.PORT}` en el inventario. Si aparece *sin datos de la API*, revisar la
API key y los ID de site y de dispositivo.

**Un equipo SNMP no reporta datos de radio o energía.** `bin/lagunitas probar-snmp <ip>` muestra
qué responde el equipo. Causas y soluciones en la guía de integración (sección *Problemas
frecuentes al integrar*).

**Al aprovisionar aparece "SNMP_COMMUNITY no definida" o "UNIFI_API_KEY no definida".** Falta esa
variable en `.env`. Mientras falte, no se actualizan las macros de esos hosts (tampoco sus
umbrales propios). Definirla y ejecutar `bin/lagunitas aprovisionar --solo hosts`.

**El aprovisionamiento se detiene con "Inventario inválido".** El mensaje enumera los errores.
Corregir el archivo y repetir `bin/lagunitas validar`. Si el error es de YAML, poner entre
comillas los textos que contengan dos puntos o numeral.

**Las notificaciones no llegan.** `bin/lagunitas probar-telegram`; luego *Reports → Action log*.
Recordar que solo se notifican los problemas de severidad Warning o mayor y que no se notifican
los equipos en mantenimiento.

**El widget "Red Las Lagunitas" no aparece o el reporte no está en el menú.**
`bin/lagunitas aprovisionar --solo modulos` (registra y habilita los módulos); verificar en
*Administration → General → Modules*. En `deploy/produccion/docker-compose.yml`, las carpetas
`zabbix/modules/*` deben estar montadas en el contenedor web.

**Un widget muestra "No permissions to referred object or it does not exist".** El equipo
seleccionado no tiene ese ítem (por ejemplo, un AP UniFi sin ítems de radio airMAX). Es esperable.

**Docker no arranca tras un reinicio del servidor.** `sudo systemctl enable --now docker`; los
contenedores tienen `restart: unless-stopped` y vuelven solos.

**El disco del servidor se llena.** Ver *Historial y espacio en disco*. Revisar además el tamaño
de `/var/backups/zabbix` y, con `docker system df`, las imágenes antiguas.

**Cambios hechos a mano en Zabbix desaparecieron.** El provisionador sobrescribe los objetos que
gestiona, incluidas las macros de los hosts. Hacer el cambio en el inventario o en el código del
proyecto.

**Recuperar desde cero.** Stack nuevo más `scripts/restore.sh` con el último backup; o bien stack
nuevo vacío más `bin/lagunitas aprovisionar` (recrea toda la configuración, sin el historial).

---

## Referencia rápida

 ```bash
 cd /opt/zabbix-lagunitas
 bin/lagunitas aprovisionar                    # aplicar inventario y configuración
 bin/lagunitas aprovisionar --solo mapa        # uno o más pasos: templates hosts dependencias
                                               #   servidor mapa servicios modulos dashboard alertas
 bin/lagunitas verificar                       # chequeo de salud
 bin/lagunitas validar                         # valida el inventario (sin Zabbix)
 bin/lagunitas -i <archivo.yaml> validar       # usar otro inventario
 bin/lagunitas exportar                        # templates y mapa a zabbix/export/
 bin/lagunitas probar-snmp <ip> [--comunidad X]   # prueba SNMP antes de integrar un equipo
 bin/lagunitas unifi-ids <ip> [puerto]         # ID de site y de AP de un controlador UniFi
 bin/lagunitas telegram-chat-id                # chat ID para TELEGRAM_CHAT_ID
 bin/lagunitas probar-telegram                 # mensaje de prueba y chequeo del bot
 COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion scripts/backup.sh /var/backups/zabbix   # respaldo
 (cd deploy/produccion && docker compose ps)   # estado del stack
 (cd deploy/produccion && docker compose logs --tail 50 zabbix-server)   # logs
 ```

El subcomando `bin/lagunitas lab` (simulador) es exclusivo del laboratorio.

---

## Control de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| 2.0 | 2026-09-29 | Primera edición del manual para la versión 2 del sistema |
| 2.1 | 2026-09-29 | Detalle por tipo de equipo y reporte técnico |
| 2.2 | 2026-09-30 | Medición cada 10 s, notificaciones por Telegram y escalonado de la detección de caídas |
| 2.3 | 2026-11-12 | Revisión técnica contra el código. Se agregan el catálogo completo de alarmas con su respuesta, los procedimientos de Internet y de energía, las tareas periódicas, el detalle de backup y restauración y la política de retención del historial (`retencion_historial`); se corrigen los estados del widget, el ajuste de umbrales y los tiempos de las pruebas de alarma |
