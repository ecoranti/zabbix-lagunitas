# Guía de integración de equipos

**Versión 2.4** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas

Esta guía explica, equipo por equipo, cómo incorporar al monitoreo cada dispositivo de la red
real: qué configurar en el equipo, cómo comprobar desde el servidor que responde, cómo cargarlo
en el inventario, qué se mide, con qué umbrales se alerta y cómo verificar que Zabbix obtiene
todos sus datos. Complementa a la [Guía de implementación](guia-implementacion.md) (instalación
del sistema) y al [Manual de administración](manual-administracion.md) (operación diaria).

**Alcance y estado de validación.** Los templates, los umbrales y los comandos de diagnóstico que
se describen se validaron en el laboratorio, con agentes SNMP simulados que responden los OIDs de
Ubiquiti airMAX y de Mikrotik y con un access point UniFi real consultado por su API. El
despliegue sobre la red física quedó pendiente, por lo que los pasos que se ejecutan en cada
equipo (airOS, RouterOS, UniFi Network) deben confirmarse durante la primera integración de cada
modelo. Los puntos que requieren esa confirmación están indicados en el texto. Qué reemplaza en
la red real a cada pieza simulada, cómo pasar las IP del relevamiento al inventario y cómo repetir
las pruebas de validación sin el simulador se explica en la sección *Del laboratorio a la red
real* de la [Guía de implementación](guia-implementacion.md).

---

## Flujo de integración (resumen)

Para **cada equipo** se sigue el mismo circuito:

1. **Relevar**: sitio, función (AP, SM, router), modelo, IP de gestión y de qué equipo depende.
2. **Preparar el equipo**: habilitar SNMP (airMAX, Mikrotik) o crear la API key (UniFi); permitir
   ICMP y SNMP desde la IP del servidor Zabbix.
3. **Probar desde el servidor**: `bin/lagunitas probar-snmp <ip>` (o `bin/lagunitas unifi-ids`
   para UniFi).
4. **Cargar en el inventario** (`config/inventory.produccion.yaml`) y validar:
   `bin/lagunitas -i config/inventory.produccion.yaml validar`.
5. **Aprovisionar**: `bin/lagunitas aprovisionar`.
6. **Verificar** en Zabbix (ver *Verificación después de integrar*) y registrar la integración
   (fecha, responsable, observaciones).

Los comandos se ejecutan en el servidor de monitoreo, desde la carpeta del proyecto
(`/opt/zabbix-lagunitas` en producción). El inventario que usa `bin/lagunitas` es el indicado en
`LAGUNITAS_INVENTORY` del archivo `.env`; la opción `-i` permite señalar otro archivo.

---

## Qué se monitorea según el tipo de equipo

| Tipo de equipo | Perfiles | Métricas principales | Pestañas en el detalle |
|---|---|---|---|
| Radio Ubiquiti airMAX (PowerBeam, LiteBeam, NanoStation, NanoLoco) | `icmp`, `airos_snmp` | Disponibilidad, latencia, pérdida · señal, ruido, SNR, CCQ, calidad y capacidad airMAX, tasas TX/RX, frecuencia, ancho de canal, potencia, distancia, modo, SSID · estaciones asociadas (señal, CCQ, distancia, latencia de cada una) · interfaces (estado, tráfico, errores) · CPU, memoria, temperatura, firmware, uptime | Resumen, Radio, Estaciones, Interfaces, Problemas, Rendimiento, Dependencias |
| Router Mikrotik (RouterOS; RB750Gr3 en el inventario) | `icmp`, `mikrotik_snmp` | Disponibilidad · **voltaje de alimentación** (batería), temperatura, CPU, memoria · **clientes DHCP activos** · **estado del enlace PPPoE a Internet** · interfaces · RouterOS, RouterBOOT, número de serie | Resumen, Router y energía, Interfaces, Problemas, Rendimiento, Dependencias |
| Router Ubiquiti airCube | `icmp` | Disponibilidad, latencia, pérdida (el equipo no ofrece SNMP ni una API documentada) | Resumen, Problemas, Rendimiento, Dependencias |
| Access point UniFi | `icmp`, `unifi_api` | Estado según el controlador, CPU, memoria, carga, clientes Wi-Fi, uplink RX/TX, reintentos por banda (2.4/5/6 GHz), firmware, modelo, controlador accesible | Resumen, UniFi, Problemas, Rendimiento, Dependencias |
| Cualquier otro equipo con IP | `icmp` | Disponibilidad, latencia, pérdida, disponibilidad de 24 h y de 7 días | Resumen, Problemas, Rendimiento, Dependencias |

Todos los equipos aparecen en el widget **Red Las Lagunitas** y en el reporte **Disponibilidad de
la red** (con su *Detalle técnico*). El mapa de topología y el árbol de servicios con su SLA
mensual trabajan por **sitio**, es decir, con el equipo principal de cada elemento del
inventario; los dispositivos secundarios de un sitio (ver *Relevamiento y convenciones*) no
tienen ícono propio en el mapa ni servicio propio en el SLA.

---

## Relevamiento y convenciones

Para cada sitio (torre, nodo, hogar) completar una planilla con **todos los equipos que tienen IP**:

| Campo | Ejemplo | Notas |
|---|---|---|
| Sitio | Mesada | Elemento del mapa |
| Nombre técnico (`host`) | `Mesada_AP_Escuela` | Sin espacios ni tildes; formato `Sitio_Función`. No se cambia después (es la clave en Zabbix) |
| Nombre visible | Mesada · AP a Escuela | Se ve en dashboards y reportes |
| IP de gestión | 192.168.88.51 | Fija (estática o reserva DHCP). No puede repetirse en el inventario |
| Función | ap / sm / ptp / router | También se admiten `switch` y `otro` |
| Modelo | Ubiquiti LiteBeam 5AC Gen2 | airOS → *System* → *Device Model* |
| Depende de | Mesada | Equipo del que recibe conectividad (`padre`) |
| Firmware | airOS 8.7.11 | Dato de relevamiento; Zabbix lo lee del equipo |
| Alimentación | Solar 12 V / red eléctrica | Para interpretar alertas de energía |

Las IP de la tabla y de los ejemplos de esta guía son las del archivo
`config/inventory.produccion.yaml`, que usa el rango por defecto del Mikrotik (192.168.88.0/24) y
las marca con `# COMPLETAR`. Deben reemplazarse por las IP de gestión reales al relevar.

### Campos del inventario

| Campo | Valores | Efecto |
|---|---|---|
| `host` | Texto sin espacios, único | Nombre técnico del host en Zabbix |
| `nombre` | Texto libre | Nombre visible |
| `rol` | `gateway`, `torre`, `nodo`, `hogar`, `institucion`, `ap` | Grupo de hosts, ícono del mapa y rama del árbol de servicios |
| `ip` | IPv4 | Interfaz del host (agente para ICMP, SNMP en el puerto 161 para los perfiles SNMP) |
| `padre` | `host` de otro equipo, o `null` en la raíz | Dependencia de alertas, camino en el mapa y disponibilidad del servicio |
| `estado` | `operativo`, `en_proceso`, `sin_configurar` | Solo `operativo` se monitorea; los demás se crean deshabilitados |
| `perfiles` | `icmp`, `airos_snmp`, `mikrotik_snmp`, `unifi_api` (se combinan) | Templates que se vinculan. Si se omite, se asume `[icmp]` |
| `funcion` | `ap`, `sm`, `ptp`, `router`, `switch`, `otro` | Dato informativo (tag e inventario de Zabbix) |
| `modelo`, `equipo` | Texto libre | Modelo exacto y descripción del hardware (inventario de Zabbix) |
| `mapa` | `[x, y]` | Posición del sitio en el mapa (obligatorio en los sitios, no en los dispositivos) |
| `dispositivos` | Lista de equipos | Equipos secundarios del sitio. Heredan `rol` y `estado` del sitio y, si no se indica otro, su `padre` es el equipo principal |
| `macros` | Pares macro y valor | Umbrales propios del equipo (ver *Alertas y umbrales*) |

El perfil `icmp_sonda` existe solo para el laboratorio (ver la
[Guía del laboratorio](laboratorio.md)) y no se usa en producción.

Las contraseñas de los equipos **no** se cargan en el inventario ni en Zabbix: el monitoreo solo
usa SNMP de lectura. La comunidad SNMP se define una vez en `.env` (`SNMP_COMMUNITY`) y el
aprovisionamiento la guarda en cada host como macro secreta (`{$SNMP_COMMUNITY}`). Si
`SNMP_COMMUNITY` no está definida, el provisionador avisa y **no actualiza ninguna macro** de los
hosts con perfil SNMP, incluidos sus umbrales propios.

---

## Disponibilidad por ICMP (todos los equipos)

El perfil `icmp` vincula el template *Lagunitas - Disponibilidad ICMP*. Es la base del monitoreo:
funciona con cualquier equipo que tenga IP y es el que define si un equipo está caído.

**Qué configurar.** El equipo debe responder al ping desde la IP del servidor Zabbix. En la red
esto implica que el firewall del Mikrotik y la VPN permitan ICMP desde el servidor hacia las IP
de gestión.

**Qué se mide** (chequeos simples con `fping` desde el Zabbix server, sin agente en el equipo):

| Métrica | Clave | Unidad | Intervalo |
|---|---|---|---|
| Disponibilidad (ICMP) | `icmpping` | 1 = responde, 0 = no responde | 10 s |
| Pérdida de paquetes (ICMP) | `icmppingloss` | % | 10 s |
| Latencia (ICMP), tiempo de ida y vuelta | `icmppingsec` | s (el frontend la muestra en ms) | 10 s |
| Disponibilidad últimas 24 h | `lagunitas.disponibilidad[24h]` | % (promedio de `icmpping`) | 1 min |
| Disponibilidad últimos 7 días | `lagunitas.disponibilidad[7d]` | % (promedio de `icmpping`) | 1 min |

El intervalo de 10 s es el valor de la macro global `{$LAGUNITAS.INTERVALO}`, común a todas las
mediciones dinámicas (ICMP, SNMP y API de UniFi).

**Alertas:**

| Alerta | Condición por defecto | Severidad | Macro |
|---|---|---|---|
| Sin respuesta (ICMP) | Ninguna respuesta durante `{$ICMP.CAIDA.PERIODO}` | High | `{$ICMP.CAIDA.PERIODO}` (90 s en la raíz, más 15 s por nivel) |
| Pérdida de paquetes alta | Mínimo de 5 min mayor que 20 %, sin ninguna medición con pérdida total en esos 5 min | Warning | `{$ICMP.PERDIDA.WARN}` |
| Latencia alta | Promedio de 5 min mayor que 0,15 s (150 ms) | Warning | `{$ICMP.LATENCIA.WARN}` |

**Por qué esos valores:**

- **Caída a los 90 s.** Con una medición cada 10 s equivale a nueve chequeos consecutivos sin
  respuesta. Evita declarar caído a un equipo por un microcorte o por el reinicio de una radio
  tras un cambio de configuración.
- **Escalonado de 15 s por nivel.** El provisionador calcula `{$ICMP.CAIDA.PERIODO}` para cada
  host según su profundidad en la topología (90 s el gateway, 105 s las torres que cuelgan de él,
  y así hasta 225 s en el equipo más profundo del inventario actual). De ese modo, cuando un
  padre y sus hijos dejan de responder a la vez, el padre entra primero en problema y la
  dependencia suprime las alertas de los hijos. Si se define esa macro a mano en el bloque
  `macros` de un equipo, el provisionador respeta el valor indicado.
- **Pérdida sobre el mínimo de 5 min.** Usar el mínimo exige que la pérdida supere el umbral
  durante toda la ventana, con lo que se descartan ráfagas aisladas. La condición "menor que
  100 %" evita duplicar la alerta de caída.
- **Latencia de 150 ms.** Es un tiempo de ida y vuelta medido dentro de la propia red, donde cada
  salto de radio agrega normalmente pocos milisegundos. Un promedio sostenido de 150 ms no se
  explica por la distancia, sino por saturación del enlace o por retransmisiones.

Las advertencias de pérdida y latencia dependen de la caída del mismo equipo, y la caída de cada
equipo depende de la de su `padre`.

---

## Ubiquiti airMAX (airOS 6 / airOS 8)

### Habilitar SNMP en el equipo

1. Ingresar a la interfaz web del equipo: `https://<IP del equipo>`.
2. Ir a la pestaña **Services** (en airOS 8, dentro del menú de configuración con ícono de
   engranaje).
3. En **SNMP Agent**: activar **Enable**, completar **SNMP Community** (la misma que
   `SNMP_COMMUNITY`; **no usar** `public`), **Contact** (por ejemplo `Red Las Lagunitas`) y
   **Location** (nombre del sitio).
4. Recomendado en la misma pestaña:
   - **NTP Client**: habilitado (hora correcta en los registros).
   - **Ping Watchdog**: habilitado, apuntando a la IP del equipo padre, para que la radio se
     reinicie sola si pierde el enlace durante varios minutos.
5. **System** → **Device Name**: usar el nombre técnico (por ejemplo `Mesada_AP_Escuela`).
6. Guardar y aplicar los cambios.

> airOS no permite limitar SNMP por IP de origen en todas las versiones. El agente es de solo
> lectura, pero SNMP v2c transmite la comunidad sin cifrar: restringir el acceso a UDP/161 desde
> el firewall del Mikrotik y usar una comunidad no trivial.

### Probar desde el servidor

 ```bash
 bin/lagunitas probar-snmp 192.168.88.51
 ```

El comando consulta por SNMP v2c desde la red del contenedor `zabbix-server`, es decir, con la
misma conectividad que tendrá Zabbix. Requiere que el stack esté en marcha. Usa la comunidad de
`SNMP_COMMUNITY` (o `public` si no está definida) y admite `--comunidad <valor>` para probar otra.
La primera ejecución construye una imagen auxiliar con las herramientas SNMP, por lo que demora
más y necesita acceso a Internet.

Salida de referencia, obtenida en el laboratorio contra un AP airMAX simulado:

 ```
 Probando SNMP v2c en 10.50.0.51 (comunidad 'public') desde la red de zabbix-lab-zabbix-server-1...

 Sistema:
   ✔ Nombre (sysName)               Mesada_AP_Escuela
   ✔ Descripción (sysDescr)         Linux 2.6.32 #1 Mon Jun 3 2024 mips
   ✔ Uptime                         ...

 Métricas Ubiquiti airMAX:
   ✔ Modelo                         "Ubiquiti LiteBeam 5AC Gen2"
   ✔ Firmware airOS                 "XC.ar8.v8.7.11.46972.220614.0419"
   ✔ Modo (1=SM, 2=AP)              2
   ✔ Frecuencia (MHz)               5745
   ✔ SSID                           "LAGUNITAS-PTMP"
   ✔ Señal (dBm)                    -65
   ✔ Ruido (dBm)                    -92
   ✔ CCQ (%)                        93
   ✔ airMAX calidad (%)             88
   ✔ airMAX capacidad (%)           79
   ✔ Estaciones asociadas           1
   ✔ CPU (%) [airOS 8]              6

 Resultado: equipo compatible. Usar perfiles: [icmp, airos_snmp]
 ```

- La primera línea muestra la comunidad en texto claro: no copiar esa salida en chats ni capturas.
- En equipos con **airOS 6** (serie M, por ejemplo NanoStation Loco M5) la **CPU** puede aparecer
  con `✘`, porque el grupo `ubntHost` es propio de airOS 8. El resto de las métricas funciona. En
  Zabbix, los ítems de CPU y de temperatura quedarán como *no soportados* y se pueden
  deshabilitar en ese host.
- Si aparece `ERROR: Timeout: No Response from <ip>`, ver *Problemas frecuentes al integrar*.
- El resultado se decide por las respuestas del equipo. Si sugiere un perfil que no corresponde
  al fabricante, prevalece el tipo real del equipo.

### Cargar en el inventario

Equipo principal del sitio y un dispositivo secundario:

 ```yaml
   - host: Mesada
     nombre: Mesada
     rol: nodo
     ip: 192.168.88.25
     padre: El_Carrizal
     estado: operativo
     perfiles: [icmp, airos_snmp]
     funcion: sm
     modelo: Ubiquiti LiteBeam 5AC Gen2
     equipo: SM LiteBeam (enlace desde El Carrizal) + AP LiteBeam a Escuela
     mapa: [625, 450]
     dispositivos:
       - host: Mesada_AP_Escuela
         nombre: Mesada · AP a Escuela
         ip: 192.168.88.51
         funcion: ap
         modelo: Ubiquiti LiteBeam 5AC Gen2
         perfiles: [icmp, airos_snmp]
 ```

Si la Escuela recibe la señal del AP de Mesada, su `padre` debe ser `Mesada_AP_Escuela`. Así, si
cae ese AP, la Escuela queda "Sin servicio" y la alerta es una sola.

### Qué se mide

Template *Lagunitas - Ubiquiti airMAX por SNMP* (SNMP v2c, 28 ítems y 16 prototipos de ítem). Los
datos dinámicos se leen cada 10 s y los estáticos cada 1 h.

| Grupo | Métrica | Unidad | Origen |
|---|---|---|---|
| Enlace | Señal recibida | dBm | `ubntWlStatSignal` |
| Enlace | RSSI | sin unidad | `ubntWlStatRssi` |
| Enlace | Piso de ruido | dBm | `ubntWlStatNoiseFloor` |
| Enlace | SNR | dB | Calculado: señal menos piso de ruido |
| Enlace | CCQ | % | `ubntWlStatCcq` |
| Enlace | Tasas TX y RX (modulación negociada, no tráfico) | bps | `ubntWlStatTxRate`, `ubntWlStatRxRate` |
| Enlace | Estaciones asociadas | cantidad | `ubntWlStatStaCount` |
| Enlace | Calidad y capacidad airMAX | % | `ubntAirMaxQuality`, `ubntAirMaxCapacity` |
| Radio | Modo (estación, AP, AP repetidor, AP WDS) | — | `ubntRadioMode` |
| Radio | Frecuencia y ancho de canal | MHz | `ubntRadioFreq`, `ubntWlStatChanWidth` |
| Radio | Potencia de transmisión | dBm | `ubntRadioTxPower` |
| Radio | Distancia configurada | m | `ubntRadioDistance` |
| Radio | SSID, antena, DFS habilitado | texto | `ubntWlStatSsid`, `ubntRadioAntenna`, `ubntRadioDfsEnabled` |
| Sistema | Uso de CPU | % | `ubntHostCpuLoad` (airOS 8) |
| Sistema | Temperatura | °C | `ubntHostTemperature` (solo algunos modelos) |
| Sistema | Memoria total y libre; uso calculado | B; % | FROGFOOT-RESOURCES-MIB |
| Sistema | Uptime, nombre, modelo, firmware airOS | — | MIB-II e IEEE802dot11-MIB |
| Sistema | Disponibilidad del agente SNMP | — | Ítem interno de Zabbix |
| Interfaces (descubiertas) | Estado, tráfico entrante y saliente, errores de entrada y de salida, velocidad | —, bps, errores/s, bps | IF-MIB |
| Estaciones (descubiertas) | Señal, ruido, CCQ, distancia, calidad y capacidad airMAX, tasas TX/RX, latencia TX, tiempo conectada | dBm, dBm, %, m, %, bps, ms, tiempo | `ubntStaTable` |

- **Interfaces.** El descubrimiento corre cada 1 h y toma las interfaces cuyo nombre coincide con
  la macro `{$AIRMAX.IF.MATCHES}`, que por defecto incluye las `eth`, `ath`, `wlan` y `br`
  numeradas. Una interfaz que desaparece se conserva 7 días.
- **Estaciones.** El descubrimiento corre cada 10 min. En un AP crea un conjunto de ítems por
  cada cliente conectado; en una estación, por el AP al que se asocia. Una estación que deja de
  verse se elimina al cabo de 1 día.
- **Unidades a confirmar en hardware.** El template interpreta las tasas TX/RX en kbps y las
  convierte a bps, y la memoria en kB. Así responden los agentes simulados del laboratorio; en la
  primera radio real conviene comparar esos valores con los que muestra airOS.

### Cómo leer las métricas de radio

| Métrica | Buena | Aceptable | Mala | Qué indica |
|---|---|---|---|---|
| Señal | -50 a -65 dBm | -65 a -75 dBm | Menor que -75 dBm | Potencia recibida del otro extremo |
| Piso de ruido | -90 a -100 dBm | -85 a -90 dBm | Mayor que -85 dBm | Interferencia en el canal |
| SNR (señal menos ruido) | Mayor que 30 dB | 20 a 30 dB | Menor que 20 dB | Margen para modulaciones altas |
| CCQ | Mayor que 90 % | 75 a 90 % | Menor que 75 % | Proporción de transmisiones exitosas |
| Calidad airMAX | Mayor que 80 % | 60 a 80 % | Menor que 60 % | Estabilidad del enlace TDMA |
| Capacidad airMAX | Mayor que 60 % | 40 a 60 % | Menor que 40 % | Fracción de la capacidad teórica |
| Tasas TX/RX | Según modelo y ancho de canal | | | Modulación negociada (no es tráfico real) |
| Estaciones asociadas | 1 o más en un AP | | 0 en un AP | Clientes conectados al AP |

Una señal más fuerte que -40 dBm tampoco es deseable en enlaces muy cortos, porque puede saturar
el receptor; en ese caso se reduce la potencia de transmisión.

### Alertas y umbrales (macros)

| Alerta | Condición por defecto | Severidad | Macro para ajustar |
|---|---|---|---|
| Señal débil | Promedio de 10 min menor que -75 dBm | Warning | `{$AIRMAX.SENAL.WARN}` |
| Señal crítica | Promedio de 10 min menor que -82 dBm | Average | `{$AIRMAX.SENAL.CRIT}` |
| Ruido alto en el canal | Promedio de 15 min mayor que -85 dBm | Warning | `{$AIRMAX.RUIDO.WARN}` |
| SNR bajo | Promedio de 15 min menor que 20 dB | Warning | `{$AIRMAX.SNR.WARN}` |
| CCQ bajo | Promedio de 15 min menor que 75 % | Warning | `{$AIRMAX.CCQ.WARN}` |
| Calidad airMAX baja | Promedio de 15 min menor que 60 % | Warning | `{$AIRMAX.CALIDAD.WARN}` |
| Capacidad airMAX baja | Promedio de 15 min menor que 40 % | Information | `{$AIRMAX.CAPACIDAD.WARN}` |
| Radio AP sin estaciones asociadas | 0 estaciones durante 5 min con la radio en modo AP | Average | — |
| Señal débil de una estación | Promedio de 10 min menor que `{$AIRMAX.SENAL.WARN}` | Warning | `{$AIRMAX.SENAL.WARN}` |
| Interfaz sin enlace | La interfaz pasa de *up* a *down* | Average | — |
| Errores en una interfaz | Errores de entrada por encima de 2 por segundo durante 5 min | Warning | `{$IF.ERRORES.WARN}` |
| Sin datos SNMP | 5 min sin respuesta del agente mientras el equipo responde al ping | Average | `{$SNMP.SIN.DATOS}` |
| Uso de CPU alto | Mínimo de 5 min mayor que 90 % | Warning | `{$AIRMAX.CPU.WARN}` |
| Uso de memoria alto | Mínimo de 5 min mayor que 90 % | Warning | `{$AIRMAX.MEMORIA.WARN}` |
| Temperatura alta | Promedio de 10 min mayor que 75 °C | Warning | `{$AIRMAX.TEMP.WARN}` |
| El equipo se reinició | Uptime menor que 10 min | Information | — |
| Cambió el firmware o la frecuencia de radio | Cambio de valor | Information | — |

Relaciones entre alertas: "señal débil" depende de "señal crítica" (se informa solo la más
grave), "radio AP sin estaciones" depende de "sin datos SNMP", y "sin datos SNMP" depende de la
caída ICMP del mismo equipo, de modo que un equipo apagado genera una sola alerta. Además, "sin
datos SNMP" exige que el equipo haya respondido el ping durante todo el período (ítem
`icmpping[,1]` del template SNMP) y "pérdida de paquetes alta" se descarta si en los 5 minutos hubo
una medición sin respuesta. Así, cuando se recupera un tramo troncal, los equipos aguas abajo no
abren alertas mientras reanudan las consultas. Las alertas de
severidad Information se ven en los dashboards y reportes pero no se notifican; la acción de
notificación avisa a partir de Warning.

**Enlaces largos.** Si un enlace es naturalmente débil (por ejemplo -74 dBm estable), ajustar el
umbral **solo para ese equipo** en el inventario, sin tocar el template:

 ```yaml
     macros:
       "{$AIRMAX.SENAL.WARN}": "-78"
       "{$AIRMAX.SENAL.CRIT}": "-84"
 ```

### Fundamento de los umbrales de radio

Los valores por defecto son puntos de partida conservadores para enlaces airMAX en 5 GHz. Las
cifras de sensibilidad y de SNR requerido que se citan son órdenes de magnitud habituales en las
hojas de datos; para un ajuste fino debe consultarse la del modelo instalado.

- **Señal.** La modulación que negocia un enlace depende de la potencia recibida. En los equipos
  802.11n de la serie M, la sensibilidad para las modulaciones más altas ronda los -75 dBm en
  canales de 20 MHz, y los equipos airMAX AC exigen más señal para sus modulaciones superiores.
  Por debajo de -75 dBm el enlace sigue funcionando, pero baja de modulación y pierde capacidad:
  es una advertencia. A -82 dBm el margen sobre la sensibilidad de la modulación más robusta
  (del orden de -96 dBm en 20 MHz) se reduce a unos 10 a 15 dB, insuficiente para absorber el
  desvanecimiento, la vegetación o una leve desalineación: el enlace está cerca del corte.
- **Piso de ruido.** El ruido térmico en un canal de ancho B es -174 dBm/Hz + 10·log10(B). Para
  20 MHz resulta -101 dBm, y con la figura de ruido del receptor (unos 5 dB) el piso esperable
  es cercano a -96 dBm. Un piso medido por encima de -85 dBm está unos 10 dB sobre ese valor, lo
  que solo se explica por interferencia. Cada vez que se duplica el ancho de canal el piso
  térmico sube 3 dB (cerca de -93 dBm en 40 MHz y de -90 dBm en 80 MHz), por lo que en canales
  anchos el umbral queda más cerca del piso normal y puede convenir subirlo en ese equipo.
- **SNR.** Es la señal menos el piso de ruido medido, no una medición de interferencia
  instantánea. Las modulaciones QPSK y 16-QAM funcionan con relaciones del orden de 10 a 18 dB,
  64-QAM requiere algo más de 20 dB y 256-QAM cerca de 30 dB. Por debajo de 20 dB el enlace no
  sostiene 64-QAM y entrega menos de la mitad de su capacidad.
- **CCQ.** Resume la eficiencia de transmisión de la radio a partir de las retransmisiones. Con
  menos de 75 % una fracción apreciable de las tramas se reenvía, lo que reduce el caudal útil
  y aumenta la latencia. En modo airMAX (TDMA) los indicadores preferidos por el fabricante son
  la calidad y la capacidad airMAX, y la interfaz de airOS 8 ya no muestra CCQ. En la primera
  integración de un equipo airMAX AC conviene confirmar qué valor entrega el OID de CCQ; si no
  fuera representativo, la alerta se anula en ese equipo definiendo `{$AIRMAX.CCQ.WARN}` en 0.
- **Calidad y capacidad airMAX.** La calidad baja (menor que 60 %) indica reintentos dentro del
  protocolo y se trata como advertencia. La capacidad compara la tasa efectiva con la teórica y
  depende también de la distancia y del modelo del cliente, por eso su alerta es solo
  informativa.
- **Ventanas de 10 y 15 minutos.** La señal y el ruido fluctúan por desvanecimiento y por el
  tráfico de redes vecinas. Evaluar promedios evita alertas intermitentes; el costo es una
  demora de detección de ese orden, aceptable porque se trata de degradación y no de corte.
- **Radio AP sin estaciones (Average).** En un AP de la red troncal, quedarse sin estaciones
  equivale a un enlace caído aunque el propio AP siga respondiendo al ping.

**Colores del widget y del reporte.** Los indicadores visuales usan niveles de observación algo
más exigentes que los triggers, para anticipar la degradación: la señal se marca en amarillo por
debajo de -72 dBm y en rojo por debajo de -80 dBm, el SNR por debajo de 25 y 15 dB, y el CCQ por
debajo de 85 y 70 %. Un valor en amarillo en el widget no implica que exista una alerta.

### Validar las alertas en el laboratorio

Los escenarios del simulador permiten comprobar cada alerta sin hardware (detalle en la
[Guía del laboratorio](laboratorio.md)):

| Escenario | Valores simulados | Alertas esperadas |
|---|---|---|
| `senal-debil` | Señal -78 dBm, estación -79 dBm, CCQ 82 % | Señal débil, señal débil de la estación, SNR bajo |
| `senal-critica` | Señal -86 dBm, CCQ 64 %, calidad 48 %, capacidad 25 % | Señal crítica, CCQ bajo, calidad y capacidad airMAX bajas |
| `interferencia` | Ruido -74 dBm, CCQ 58 %, calidad 52 %, capacidad 33 % | Ruido alto, SNR bajo, CCQ bajo, calidad y capacidad airMAX bajas |
| `sin-estaciones` | 0 estaciones en un AP | Radio AP sin estaciones asociadas |

 ```bash
 bin/lagunitas lab escenario Walter senal-debil
 bin/lagunitas lab escenario Walter normal
 ```

---

## Router Mikrotik (RouterOS 6 / 7)

### Habilitar SNMP (terminal / Winbox → New Terminal)

 ```
 /system identity set name=Gateway_Mikrotik
 /snmp community add name=<COMUNIDAD> addresses=<IP_SERVIDOR_ZABBIX>/32 read-access=yes write-access=no
 /snmp community set [find default=yes] read-access=no
 /snmp set enabled=yes contact="Red Las Lagunitas" location="<SITIO>"
 /ip firewall filter add chain=input protocol=udp dst-port=161 src-address=<IP_SERVIDOR_ZABBIX> action=accept place-before=0 comment="Zabbix SNMP"
 /ip firewall filter add chain=input protocol=icmp src-address=<IP_SERVIDOR_ZABBIX> action=accept place-before=0 comment="Zabbix ICMP"
 ```

En Winbox: **IP → SNMP** (habilitar, *Communities* → agregar) y **IP → Firewall** (reglas).
La comunidad por defecto `public` no puede eliminarse, por eso se le quita el acceso de lectura.
`<COMUNIDAD>` es el valor de `SNMP_COMMUNITY`, `<IP_SERVIDOR_ZABBIX>` es la IP con la que el
servidor llega al router y `<SITIO>` el lugar de instalación.

Las reglas anteriores (cadena `input`) habilitan el monitoreo del propio router. Si el firewall
filtra el tráfico que atraviesa el router, el servidor necesita además reglas equivalentes en la
cadena `forward` para alcanzar por ICMP y por UDP/161 a las radios que están detrás.

### Probar y cargar

 ```bash
 bin/lagunitas probar-snmp 192.168.88.10
 ```

Salida de referencia, obtenida en el laboratorio contra el Mikrotik simulado:

 ```
 Sistema:
   ✔ Nombre (sysName)               Gateway_Mikrotik
   ✔ Descripción (sysDescr)         RouterOS RB750Gr3
   ✔ Uptime                         ...

 Métricas Mikrotik:
   ✔ RouterOS                       "7.14.3"
   ✔ Número de serie                "HE308G1XM2Q"
   ✔ Voltaje (décimas de V)         123
   ✔ Temperatura (décimas de °C)    418
   ✔ Leases DHCP activos            6
   ✔ Carga CPU núcleo 1 (%)         6

 Resultado: equipo compatible. Usar perfiles: [icmp, mikrotik_snmp]
 ```

El voltaje y la temperatura se informan en décimas (123 equivale a 12,3 V); el template los
convierte a V y °C. En el inventario usar `perfiles: [icmp, mikrotik_snmp]`, `funcion: router` y
el modelo exacto:

 ```yaml
   - host: Gateway_Mikrotik
     nombre: Gateway Mikrotik
     rol: gateway
     ip: 192.168.88.10
     padre: null
     estado: operativo
     perfiles: [icmp, mikrotik_snmp]
     funcion: router
     modelo: Mikrotik RB750Gr3
     equipo: Mikrotik RB750 — DHCP, NAT, PPPoE a Internet
     mapa: [45, 480]
 ```

- **Voltaje y temperatura** dependen del hardware: los modelos sin sensor dejan esos ítems como
  no soportados. Debe confirmarse en el router instalado que `probar-snmp` los informa.
- **Enlace a Internet**: se detecta la interfaz cuyo nombre coincide con `{$MIKROTIK.WAN.IFNAME}`
  (por defecto `^pppoe-out[0-9]+$`). Si la salida es otra (por ejemplo `ether1` con IP fija),
  ajustar la macro en el inventario del gateway:

 ```yaml
     macros:
       "{$MIKROTIK.WAN.IFNAME}": "^ether1$"
 ```

### Qué se mide

Template *Lagunitas - Mikrotik por SNMP* (SNMP v2c, 15 ítems y 7 prototipos de ítem).

| Grupo | Métrica | Unidad | Origen |
|---|---|---|---|
| Energía | Voltaje de alimentación | V | `mtxrHlVoltage` (décimas de V) |
| Energía | Temperatura de placa y de CPU | °C | `mtxrHlTemperature`, `mtxrHlProcessorTemperature` (décimas de °C) |
| Servicio | Clientes DHCP activos (leases) | cantidad | `mtxrDHCPLeaseCount` |
| Servicio | Estado del enlace a Internet (interfaz WAN descubierta) | *up* / *down* | `ifOperStatus` |
| Sistema | Uso de CPU (promedio de todos los núcleos) | % | `hrProcessorLoad` |
| Sistema | Memoria total y usada; uso calculado | B; % | `hrStorageSize`, `hrStorageUsed` (índice 65536) |
| Sistema | Uptime, nombre, modelo (`sysDescr`), número de serie, versión de RouterOS y de RouterBOOT | — | MIB-II y MIKROTIK-MIB |
| Sistema | Disponibilidad del agente SNMP | — | Ítem interno de Zabbix |
| Interfaces (descubiertas) | Estado, tráfico entrante y saliente, errores, velocidad | —, bps, errores/s, bps | IF-MIB |

El descubrimiento de interfaces corre cada 1 h y toma las que empiezan con `ether`, `sfp`,
`wlan`, `bridge`, `pppoe`, `vlan` o `lte` (macro `{$MIKROTIK.IF.MATCHES}`). El descubrimiento del
enlace WAN corre cada 10 min.

Como los routers airCube de los hogares trabajan en modo puente y el direccionamiento está
centralizado en el Mikrotik, la cantidad de leases DHCP representa de forma aproximada los
dispositivos conectados en toda la red.

### Alertas y umbrales

| Alerta | Condición por defecto | Severidad | Macro |
|---|---|---|---|
| **Sin enlace a Internet** | Interfaz WAN en un estado distinto de *up*, o sin datos de esa interfaz durante 5 min | **Disaster** | `{$MIKROTIK.WAN.IFNAME}` |
| Voltaje bajo | Promedio de 10 min menor que 12,0 V | Warning | `{$MIKROTIK.VOLTAJE.WARN}` |
| Voltaje crítico | Promedio de 5 min menor que 11,6 V | High | `{$MIKROTIK.VOLTAJE.CRIT}` |
| Voltaje excesivo | Promedio de 10 min mayor que 14,8 V | Average | `{$MIKROTIK.VOLTAJE.MAX}` |
| Sin clientes DHCP | 0 leases durante 30 min | Warning | — |
| Uso de CPU alto | Mínimo de 5 min mayor que 85 % | Warning | `{$MIKROTIK.CPU.WARN}` |
| Uso de memoria alto | Mínimo de 5 min mayor que 90 % | Warning | `{$MIKROTIK.MEMORIA.WARN}` |
| Temperatura alta | Promedio de 10 min de la temperatura de placa mayor que 65 °C | Warning | `{$MIKROTIK.TEMP.WARN}` |
| Interfaz sin enlace | La interfaz pasa de *up* a *down* | Average | — |
| Errores en una interfaz | Errores de entrada por encima de 2 por segundo durante 5 min | Warning | `{$IF.ERRORES.WARN}` |
| Sin datos SNMP | 5 min sin respuesta del agente mientras el equipo responde al ping | Average | `{$SNMP.SIN.DATOS}` |
| El router se reinició | Uptime menor que 10 min | Information | — |
| Cambió la versión de RouterOS | Cambio de valor | Information | — |

"Voltaje bajo" depende de "voltaje crítico" y "sin clientes DHCP" depende de "sin datos SNMP".

La alerta **sin enlace a Internet** incluye la condición de falta de datos, por lo que también
se dispara cuando el router deja de responder SNMP durante 5 min, aunque la sesión PPPoE siga
activa. Ante esa alerta conviene mirar primero si el mismo equipo tiene además "sin respuesta
(ICMP)" o "sin datos SNMP": en ese caso el problema es el router o el camino hacia él, no
necesariamente el proveedor.

### Fundamento de los umbrales de energía

Referencia de una batería VRLA de 12 V **en reposo** (sin carga ni consumo, a unos 25 °C):

| Tensión en bornes | Estado de carga aproximado |
|---|---|
| 12,7 V o más | 100 % |
| 12,4 V | 75 % |
| 12,2 V | 50 % |
| 12,0 V | 25 % |
| 11,8 V o menos | Descarga profunda (acorta la vida útil) |

- El router mide la tensión **con consumo**, que es algo menor que la de reposo, y de día la
  medición refleja además la tensión de carga del regulador (entre 13,5 y 14,5 V
  aproximadamente). Por eso la tabla es orientativa y los umbrales se evalúan sobre promedios.
- **12,0 V (Warning)**: con el consumo del nodo conectado corresponde a una batería que ya entregó cerca de la mitad
  de su carga o más. Es el punto para revisar el panel antes de la noche siguiente.
- **11,6 V (High)**: descarga profunda. La ventana es más corta (5 min) porque el corte del nodo
  es inminente y la descarga profunda repetida daña la batería.
- **14,8 V (Average)**: por encima de la tensión de carga normal de una batería de 12 V; indica
  una falla del regulador.
- El dato solo representa a la batería si el router se alimenta directamente de ella. Si lo hace
  a través de un conversor o de una fuente regulada, el voltaje leído será constante y estas
  alertas no aplican.

Escenarios del laboratorio para validar: `bateria-baja` (11,8 V), `bateria-critica` (11,3 V),
`sin-internet` (interfaz `pppoe-out1` en *down*) y `sin-clientes` (0 leases; la alerta aparece a
los 30 min).

---

## Routers airCube (hogares)

El airCube no ofrece SNMP ni una API documentada: se monitorea solo por **ICMP**.

1. Asignarle una IP de gestión fija (reserva DHCP en el Mikrotik por su MAC).
2. Verificar el ping desde el servidor, con la misma herramienta que usa Zabbix:

   ```bash
   cd /opt/zabbix-lagunitas/deploy/produccion
   docker compose exec zabbix-server fping -c3 <IP>
   ```

3. Cargarlo como **dispositivo** del hogar, con el equipo de radio del hogar como padre:

 ```yaml
     dispositivos:
       - host: Esther_Router
         nombre: Esther · Router airCube
         ip: 192.168.88.53
         funcion: router
         modelo: Ubiquiti airCube AC
         perfiles: [icmp]
 ```

Qué se mide y con qué umbrales se alerta: ver *Disponibilidad por ICMP*. Si el router del hogar
está caído pero la radio responde, el problema es del lado del hogar (energía, router apagado);
si cae la radio, el router queda "Sin servicio".

---

## Access points UniFi (API de UniFi Network)

Los AP UniFi se consultan a través del **controlador** (UniFi Network), no del propio AP. El
servidor Zabbix necesita acceso HTTPS al controlador.

### Preparar el controlador y cargar el AP

1. En **UniFi Network** crear una API key (*Settings → Control Plane → Integrations → Create API
   Key*; la ubicación del menú puede variar según la versión). Guardarla en `.env` como
   `UNIFI_API_KEY`. El aprovisionamiento la carga en Zabbix como macro secreta del host.
2. Averiguar la IP y el puerto HTTPS del controlador. En un **UniFi OS Server** instalado sobre
   una PC o Mac el puerto puede no ser 443 y **cambiar al reiniciarse**; en ese equipo se puede
   consultar con:

   ```bash
   lsof -nP -iTCP -sTCP:LISTEN | grep -iE "gvproxy|unifi"
   ```

3. Obtener los ID de site y de dispositivo (el puerto es opcional y por defecto es 443):

   ```bash
   bin/lagunitas unifi-ids <IP_CONTROLADOR> <PUERTO>
   ```

   Formato de la salida (los valores dependen del controlador):

   ```
   Site: <nombre del site>   {$UNIFI.SITE.ID} = <id del site>
     - <nombre del AP>   modelo=<modelo>  ip=<IP del AP>  estado=ONLINE  {$UNIFI.DEVICE.ID} = <id del AP>

   Macros del host en el inventario: {$UNIFI.HOST}: <IP_CONTROLADOR>  {$UNIFI.PORT}: "<PUERTO>"
   ```

4. Cargar el AP en el inventario con esas macros. Los valores entre `<>` son parámetros a
   completar:

 ```yaml
   - host: <Sitio>_AP_WiFi
     nombre: <Sitio> · AP Wi-Fi
     rol: ap
     ip: <IP del AP>
     padre: <host del equipo que le da conectividad>
     estado: operativo
     perfiles: [icmp, unifi_api]
     funcion: ap
     modelo: <modelo del AP>
     mapa: [<x>, <y>]
     macros:
       "{$UNIFI.HOST}": <IP del controlador>
       "{$UNIFI.PORT}": "443"
       "{$UNIFI.SITE.ID}": <id del site>
       "{$UNIFI.DEVICE.ID}": <id del AP>
 ```

El inventario de producción no incluye hoy ningún AP UniFi. La integración se validó en el
laboratorio con un UniFi U7 Pro Wall real.

### Qué se mide

Template *Lagunitas - AP UniFi por API* (18 ítems). Tres consultas HTTPS a la API de integración
(`/proxy/network/integration/v1`), cada 10 s y con la API key en la cabecera `X-API-KEY`,
devuelven documentos JSON de los que se extraen las métricas:

| Métrica | Unidad | Consulta de origen |
|---|---|---|
| Estado informado por UniFi y disponibilidad (1 si el estado es ONLINE) | texto; 1 / 0 | Dispositivo |
| Versión de firmware y modelo | texto | Dispositivo |
| Uptime | tiempo | Estadísticas |
| Uso de CPU y de memoria | % | Estadísticas |
| Carga promedio de 1 min | sin unidad | Estadísticas |
| Tráfico del uplink TX y RX | bps | Estadísticas |
| Reintentos de transmisión por banda (2.4, 5 y 6 GHz) | % | Estadísticas |
| Clientes conectados al AP | cantidad | Clientes del site |
| Controlador accesible (puerto HTTPS abierto) | 1 / 0 | Chequeo TCP desde el Zabbix server |

- Las bandas se asignan por la posición de cada radio en la respuesta de la API (primera 2.4 GHz,
  segunda 5 GHz, tercera 6 GHz). En un modelo distinto del validado conviene confirmar ese orden.
  Si el AP no tiene alguna banda, el ítem queda sin valores y no genera error.
- El conteo de clientes se calcula sobre una consulta limitada a 200 clientes por site.
- La consulta no verifica el certificado TLS del controlador, que suele ser autofirmado.

### Alertas y umbrales

| Alerta | Condición por defecto | Severidad | Macro |
|---|---|---|---|
| Controlador UniFi no accesible | Puerto HTTPS del controlador cerrado durante 3 min | Average | `{$UNIFI.HOST}`, `{$UNIFI.PORT}` |
| Sin datos de la API de UniFi | Sin estadísticas durante 5 min | Average | `{$AP.SIN.DATOS}` |
| AP fuera de línea según UniFi | El controlador informa un estado distinto de ONLINE | High | — |
| Uso de CPU alto | Mínimo de 5 min mayor que 85 % | Warning | `{$AP.CPU.WARN}` |
| Uso de memoria alto | Mínimo de 5 min mayor que 85 % | Warning | `{$AP.MEM.WARN}` |
| Reintentos altos en 2.4, 5 o 6 GHz | Promedio de 15 min mayor que 20 % | Warning | `{$AP.REINTENTOS.WARN}` |
| El AP se reinició | Uptime menor que 10 min | Information | — |
| Cambió la versión de firmware | Cambio de valor | Information | — |

Las alertas se encadenan para informar la causa más básica: "AP fuera de línea" depende de "sin
datos de la API", que depende de "controlador no accesible". Con el perfil `icmp`, la caída del
AP la define el ping, y las alertas del controlador y de la API dependen de ella.

Los reintentos miden la proporción de tramas que el AP debe retransmitir. Un promedio sostenido
por encima de 20 % indica interferencia, canal saturado o clientes con mala señal; es una
advertencia porque degrada el servicio sin interrumpirlo.

---

## Otros equipos

- **Switches, cámaras, servidores, sensores con IP**: agregarlos con `perfiles: [icmp]`.
- **Equipos con SNMP estándar** (switches administrables, UPS): se puede vincular a mano un
  template oficial de Zabbix (por ejemplo *Generic by SNMP*) desde *Data collection → Hosts*, o
  sumar un perfil nuevo en `lagunitas/model.py` (`PERFILES`) para que lo gestione el
  provisionador. El aprovisionamiento desvincula de los hosts del inventario los templates que
  no correspondan a sus perfiles, por lo que la segunda opción es la única permanente.

---

## Energía de los nodos solares

Los controladores de carga **Epever LS-E** instalados no tienen puerto de comunicación, por lo que
Zabbix no puede leer la batería directamente. Alternativas, en orden de costo:

1. **Voltaje del Mikrotik** (ya soportado): si el router se alimenta de la batería del nodo,
   `mtxrHlVoltage` refleja su estado de carga y dispara las alertas de voltaje bajo y crítico.
2. **Ping Watchdog y reinicios**: la alerta "el equipo se reinició" en horarios nocturnos es un
   indicador indirecto de batería insuficiente.
3. **Reemplazo por controladores con RS-485/Modbus** más un pequeño gateway Modbus-TCP, o un
   sensor de tensión en la red LoRaWAN existente: se integrarían con un template adicional
   (voltaje de batería, corriente de panel, energía generada). Es una línea de trabajo futuro,
   no implementada.

---

## Verificación después de integrar

- [ ] `bin/lagunitas verificar`: el equipo figura y no tiene ítems no soportados inesperados.
- [ ] *Monitoring → Latest data* (filtrar por el equipo): los ítems tienen valores recientes.
- [ ] El descubrimiento creó las estaciones (hasta 10 min, en airMAX), el enlace WAN (hasta
      10 min, en Mikrotik) y las interfaces (hasta 1 h). Para no esperar: *Data collection →
      Hosts → Discovery* del equipo, marcar las reglas y pulsar *Execute now*.
- [ ] En el widget **Red Las Lagunitas** aparece "En línea" y la columna *Enlace / energía* muestra
      señal y CCQ (airMAX) o voltaje y clientes DHCP (Mikrotik).
- [ ] El modal del equipo muestra las pestañas propias de su tipo y *Depende de* es correcto.
- [ ] Si es el equipo principal de un sitio, aparece en el mapa en su posición y con el enlace
      hacia el sitio del que depende.
- [ ] *Data collection → Hosts → Macros* del equipo: `{$ICMP.CAIDA.PERIODO}` tiene el valor que
      corresponde a su nivel y están los umbrales propios definidos en el inventario.
- [ ] **Prueba de alerta controlada** (en una ventana acordada): desconectar el equipo o bloquear el
      ping y confirmar que llega **una sola** alerta y que los equipos que dependen de él quedan
      "Sin servicio".

---

## Referencia de OIDs utilizados

| Dato | OID | MIB |
|---|---|---|
| Nombre, descripción, uptime | `1.3.6.1.2.1.1.5.0`, `1.3.6.1.2.1.1.1.0`, `1.3.6.1.2.1.1.3.0` | SNMPv2-MIB (`sysName`, `sysDescr`, `sysUpTime`) |
| Modelo y firmware airOS | `1.2.840.10036.3.1.2.1.3.5`, `1.2.840.10036.3.1.2.1.4.5` | IEEE802dot11-MIB |
| Modo, frecuencia, DFS, potencia, distancia, antena | `1.3.6.1.4.1.41112.1.4.1.1.{2,4,5,6,7,9}.1` | UBNT-AirMAX-MIB (`ubntRadioTable`) |
| SSID, señal, RSSI, CCQ, ruido, tasa TX, tasa RX, ancho de canal, estaciones | `1.3.6.1.4.1.41112.1.4.5.1.{2,5,6,7,8,9,10,14,15}.1` | UBNT-AirMAX-MIB (`ubntWlStatTable`) |
| Calidad y capacidad airMAX | `1.3.6.1.4.1.41112.1.4.6.1.{3,4}.1` | UBNT-AirMAX-MIB (`ubntAirMaxTable`) |
| Estaciones: nombre, señal, ruido, distancia, CCQ, calidad, capacidad, IP, tasas, tiempo conectada, latencia | `1.3.6.1.4.1.41112.1.4.7.1.{2,3,4,5,6,8,9,10,11,12,15,21}` | UBNT-AirMAX-MIB (`ubntStaTable`) |
| CPU y temperatura (airOS 8) | `1.3.6.1.4.1.41112.1.4.8.{3,4}.0` | UBNT-AirMAX-MIB (`ubntHost`) |
| Memoria total y libre (airOS) | `1.3.6.1.4.1.10002.1.1.1.1.{1,2}.0` | FROGFOOT-RESOURCES-MIB |
| Voltaje, temperatura de placa y de CPU (Mikrotik) | `1.3.6.1.4.1.14988.1.1.3.{8,10,11}.0` | MIKROTIK-MIB (décimas) |
| Leases DHCP, versión de RouterOS | `1.3.6.1.4.1.14988.1.1.6.1.0`, `1.3.6.1.4.1.14988.1.1.4.4.0` | MIKROTIK-MIB |
| Número de serie y versión de RouterBOOT | `1.3.6.1.4.1.14988.1.1.7.{3,4}.0` | MIKROTIK-MIB |
| CPU por núcleo (Mikrotik) | `1.3.6.1.2.1.25.3.3.1.2` | HOST-RESOURCES-MIB (`hrProcessorLoad`) |
| Memoria total y usada (Mikrotik) | `1.3.6.1.2.1.25.2.3.1.{5,6}.65536` | HOST-RESOURCES-MIB (`hrStorageTable`) |
| Interfaces: tipo, estado, errores de entrada y de salida | `1.3.6.1.2.1.2.2.1.{3,8,14,20}` | IF-MIB (`ifTable`) |
| Interfaces: nombre, octetos entrantes y salientes, velocidad, alias | `1.3.6.1.2.1.31.1.1.1.{1,6,10,15,18}` | IF-MIB (`ifXTable`) |

La notación `{a,b}` abrevia varios OIDs que solo difieren en ese componente. La definición
completa de ítems y triggers está en `lagunitas/templates.py` y `lagunitas/templates_snmp.py`, y
exportada en `zabbix/export/`.

---

## Problemas frecuentes al integrar

| Síntoma | Causa probable | Solución |
|---|---|---|
| `probar-snmp`: `ERROR: Timeout: No Response` | SNMP deshabilitado, comunidad distinta, firewall o ruta | Revisar la habilitación de SNMP en el equipo; probar ping; revisar las reglas UDP/161 del Mikrotik y de la VPN |
| `probar-snmp`: "No encontré el contenedor zabbix-server" | El stack no está en marcha | Levantarlo con `docker compose up -d` en `deploy/produccion` |
| `probar-snmp`: "responde SNMP pero no se reconoció" | El equipo no es airMAX ni Mikrotik | Integrarlo solo con `[icmp]` |
| CPU y temperatura airMAX *no soportados* | airOS 6 (serie M) no expone `ubntHost` | Normal: deshabilitar esos dos ítems en el host |
| Voltaje Mikrotik *no soportado* | Modelo sin sensor | Normal; ver *Energía de los nodos solares* |
| No se descubre el "enlace a Internet" | La WAN no se llama `pppoe-outN` | Ajustar `{$MIKROTIK.WAN.IFNAME}` |
| Las estaciones o las interfaces no aparecen | El descubrimiento corre cada 10 min (estaciones) o cada 1 h (interfaces) | Esperar o usar *Execute now* en la regla de descubrimiento |
| Aviso "SNMP_COMMUNITY no definida" al aprovisionar | Falta la variable en `.env` | Definirla y ejecutar `bin/lagunitas aprovisionar --solo hosts` |
| Todos los ítems SNMP *no soportados* tras integrar | La comunidad del equipo no coincide con la de `.env` | Igualarlas y volver a aprovisionar los hosts |
| UniFi: *controlador no accesible* | La IP o el puerto del controlador cambiaron | `lsof` en el controlador (ver *Access points UniFi*) y corregir `{$UNIFI.HOST}` y `{$UNIFI.PORT}` |
| `unifi-ids`: `HTTP 000` | No hay conexión con el controlador | Revisar IP, puerto y que el controlador esté encendido |
| `unifi-ids`: `HTTP 401` | API key inválida o revocada | Crear una nueva, actualizar `UNIFI_API_KEY` y ejecutar `bin/lagunitas aprovisionar --solo hosts` |
| `unifi-ids`: `HTTP 404` | La ruta de la API no existe en esa versión del controlador, o el ID es incorrecto | Verificar la versión de UniFi Network y repetir `bin/lagunitas unifi-ids` |
| Aviso "UNIFI_API_KEY no definida" al aprovisionar | Falta la variable en `.env` | Definirla; mientras falte, no se actualizan las macros de los AP UniFi |
| Alerta duplicada "sin datos SNMP" más "sin respuesta" | — | No ocurre: "sin datos SNMP" depende de la caída ICMP del mismo equipo |

---

## Control de versiones

| Versión | Fecha | Cambios |
|---|---|---|
| 2.1 | 2026-09-29 | Primera edición de la guía |
| 2.2 | 2026-09-30 | Medición cada 10 s; guía orientada a producción |
| 2.4 | 2026-11-13 | Notificación desde Warning; «sin datos SNMP» solo si el equipo responde ping y «pérdida de paquetes» excluye la caída total, para evitar falsas alertas al recuperarse un tramo |
| 2.3 | 2026-11-12 | Revisión técnica contra el código. Se agregan las secciones de disponibilidad por ICMP, métricas con unidad por tipo de equipo, fundamento de los umbrales y validación en laboratorio; se completan las tablas de alertas de Mikrotik y UniFi y la referencia de OIDs |
