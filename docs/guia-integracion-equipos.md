# Guía de integración de equipos — Red Las Lagunitas

**Versión 2.1** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas

Esta guía explica, equipo por equipo, cómo incorporar al monitoreo cada dispositivo de la red
real: qué configurar en el equipo, cómo comprobar desde el servidor que responde, cómo cargarlo
en el inventario y cómo verificar que Zabbix obtiene todos sus datos. Complementa a la
[Guía de implementación](guia-implementacion.md) (instalación del sistema) y al
[Manual de administración](manual-administracion.md) (operación diaria).

---

## 1. Flujo de integración (resumen)

Para **cada equipo** se sigue el mismo circuito:

1. **Relevar**: sitio, función (AP, SM, router), modelo, IP de gestión y de qué equipo depende.
2. **Preparar el equipo**: habilitar SNMP (airMAX, Mikrotik) o crear la API key (UniFi); permitir
   ping y SNMP desde la IP del servidor Zabbix.
3. **Probar desde el servidor**: `bin/lagunitas probar-snmp <ip>` (o `unifi-ids` para UniFi).
4. **Cargar en el inventario** (`config/inventory.produccion.yaml`) y validar:
   `bin/lagunitas -i config/inventory.produccion.yaml validar`.
5. **Aprovisionar**: `bin/lagunitas aprovisionar`.
6. **Verificar** en Zabbix (§10) y registrar la integración (fecha, responsable, observaciones).

> Recomendación: validar primero en el **laboratorio** con el agente SNMP simulado (§11), para
> conocer de antemano qué datos y qué alertas va a producir cada tipo de equipo.

---

## 2. Qué se monitorea según el tipo de equipo

| Tipo de equipo | Perfiles | Métricas principales | Pestañas en el detalle |
|---|---|---|---|
| Radio Ubiquiti airMAX (PowerBeam, LiteBeam, NanoStation, NanoLoco) | `icmp`, `airos_snmp` | Disponibilidad, latencia, pérdida · señal, ruido, SNR, CCQ, calidad y capacidad airMAX, tasas TX/RX, frecuencia, ancho de canal, potencia, distancia, modo, SSID · estaciones asociadas (señal, CCQ, distancia, latencia de cada una) · interfaces (estado, tráfico, errores) · CPU, memoria, temperatura, firmware, uptime | Resumen, Radio, Estaciones, Interfaces, Problemas, Rendimiento, Dependencias |
| Router Mikrotik (RB750, RB950, hAP) | `icmp`, `mikrotik_snmp` | Disponibilidad · **voltaje de alimentación** (batería), temperatura, CPU, memoria · **clientes DHCP activos** · **estado del enlace PPPoE a Internet** · interfaces · RouterOS, firmware, número de serie | Resumen, Router y energía, Interfaces, Problemas, Rendimiento, Dependencias |
| Router Ubiquiti airCube | `icmp` | Disponibilidad, latencia, pérdida (el equipo no ofrece SNMP ni API) | Resumen, Problemas, Rendimiento, Dependencias |
| Access point UniFi | `unifi_api` (+ `icmp` en producción) | Estado según el controlador, CPU, memoria, load, clientes Wi-Fi, uplink RX/TX, reintentos por banda (2.4/5/6 GHz), firmware, modelo, controlador accesible | Resumen, UniFi, Problemas, Rendimiento, Dependencias |
| Cualquier otro equipo con IP | `icmp` | Disponibilidad, latencia, pérdida, disponibilidad 24 h / 7 días | Resumen, Problemas, Rendimiento, Dependencias |

Todos aparecen en el widget **Red Las Lagunitas**, en el mapa, en el reporte **Disponibilidad de la
red** (con su *Detalle técnico*) y en el SLA.

---

## 3. Relevamiento y convenciones

Para cada sitio (torre, nodo, hogar) completar una planilla con **todos los equipos que tienen IP**:

| Campo | Ejemplo | Notas |
|---|---|---|
| Sitio | Mesada | Elemento del mapa |
| Nombre técnico (`host`) | `Mesada_AP_Escuela` | Sin espacios ni tildes; formato `Sitio_Función`. No se cambia después (es la clave en Zabbix) |
| Nombre visible | Mesada · AP a Escuela | Se ve en dashboards y reportes |
| IP de gestión | 192.168.88.51 | Fija (estática o reserva DHCP) |
| Función | ap / sm / ptp / router | |
| Modelo | Ubiquiti LiteBeam 5AC Gen2 | airOS → *System* → *Device Model* |
| Depende de | Mesada | Equipo del que recibe conectividad |
| Firmware | airOS 8.7.11 | |
| Alimentación | Solar 12 V / red eléctrica | Para interpretar alertas de energía |

Las contraseñas de los equipos **no** se cargan en el inventario ni en Zabbix: el monitoreo solo usa
SNMP de lectura. La comunidad SNMP se define una vez en `.env` (`SNMP_COMMUNITY`) y se guarda en
Zabbix como macro secreta.

---

## 4. Ubiquiti airMAX (airOS 6 / airOS 8)

### 4.1 Habilitar SNMP en el equipo

1. Entrar a la interfaz web del equipo: `https://<IP del equipo>`.
2. Ir a la pestaña **Services** (ícono de engranaje en airOS 8).
3. En **SNMP Agent**: activar **Enable**, completar **SNMP Community** (la misma que
   `SNMP_COMMUNITY`; **no usar** `public`), **Contact** (ej. `Red Las Lagunitas`) y
   **Location** (nombre del sitio).
4. Recomendado en la misma pestaña:
   - **NTP Client**: habilitado (hora correcta en los registros).
   - **Ping Watchdog**: habilitado, apuntando a la IP del equipo padre, para que la radio se
     reinicie sola si pierde el enlace durante varios minutos.
5. **System** → **Device Name**: usar el nombre técnico (ej. `Mesada_AP_Escuela`).
6. **Save Changes** y luego **Apply**.

> airOS no permite limitar SNMP por IP de origen en todas las versiones: restringir el acceso a
> UDP/161 desde el firewall del Mikrotik y usar una comunidad no trivial.

### 4.2 Probar desde el servidor

```bash
bin/lagunitas probar-snmp 192.168.88.51
```

Salida esperada (resumida): `✔` en nombre, uptime, modelo, firmware, modo, frecuencia, SSID,
señal, ruido, CCQ, calidad y capacidad airMAX, y la línea
`Resultado: equipo compatible. Usar perfiles: [icmp, airos_snmp]`.

- En equipos con **airOS 6** (serie M, por ejemplo NanoStation Loco M5) la **CPU** y la
  **temperatura** (`ubntHost*`) pueden aparecer con `✘`: el resto de las métricas funciona. En Zabbix
  esos dos ítems quedarán como *no soportados*; se pueden deshabilitar en ese host.
- Si todo sale con `✘` o `Timeout`: ver §13.

### 4.3 Cargar en el inventario

Equipo principal del sitio:

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

Si la Escuela recibe la señal del AP de Mesada, su `padre` debe ser `Mesada_AP_Escuela` (así, si
cae ese AP, la Escuela queda "Sin servicio" y la alerta es una sola).

### 4.4 Qué datos se obtienen y cómo leerlos

| Métrica | Buena | Aceptable | Mala | Qué indica |
|---|---|---|---|---|
| Señal | -50 a -65 dBm | -65 a -75 dBm | < -75 dBm | Potencia recibida del otro extremo |
| Piso de ruido | -90 a -100 dBm | -85 a -90 dBm | > -85 dBm | Interferencia en el canal |
| SNR (señal − ruido) | > 30 dB | 20–30 dB | < 15–20 dB | Margen para modulaciones altas |
| CCQ | > 90 % | 75–90 % | < 75 % | % de transmisiones exitosas |
| Calidad airMAX | > 80 % | 60–80 % | < 60 % | Estabilidad del enlace TDMA |
| Capacidad airMAX | > 60 % | 40–60 % | < 40 % | Fracción de la capacidad teórica |
| Tasas TX/RX | según modelo | | | Modulación negociada (no es tráfico real) |
| Estaciones asociadas | ≥ 1 en un AP | | 0 en un AP | Clientes conectados al AP |

### 4.5 Alertas y umbrales (macros)

| Alerta | Condición por defecto | Severidad | Macro para ajustar |
|---|---|---|---|
| Señal débil / crítica | Promedio 10 min < -75 / -82 dBm | Warning / Average | `{$AIRMAX.SENAL.WARN}`, `{$AIRMAX.SENAL.CRIT}` |
| Ruido alto en el canal | Promedio 15 min > -85 dBm | Warning | `{$AIRMAX.RUIDO.WARN}` |
| SNR bajo | Promedio 15 min < 20 dB | Warning | `{$AIRMAX.SNR.WARN}` |
| CCQ bajo | Promedio 15 min < 75 % | Warning | `{$AIRMAX.CCQ.WARN}` |
| Calidad / capacidad airMAX baja | < 60 % / < 40 % | Warning / Info | `{$AIRMAX.CALIDAD.WARN}`, `{$AIRMAX.CAPACIDAD.WARN}` |
| Radio AP sin estaciones asociadas | 0 estaciones durante 5 min en modo AP | Average | — |
| Señal débil de una estación | Promedio 10 min < `{$AIRMAX.SENAL.WARN}` | Warning | — |
| Interfaz sin enlace / con errores | Paso de up a down / errores > 2/s | Average / Warning | `{$IF.ERRORES.WARN}` |
| Sin datos SNMP | 5 min sin respuesta (depende de la caída ICMP) | Average | `{$SNMP.SIN.DATOS}` |
| CPU, memoria, temperatura altas | > 90 %, > 90 %, > 75 °C | Warning | `{$AIRMAX.CPU.WARN}`, etc. |
| Reinicio, cambio de firmware o de frecuencia | — | Info | — |

**Enlaces largos**: si un enlace es naturalmente débil (por ejemplo -74 dBm estable), ajustar el
umbral **solo para ese equipo** en el inventario, sin tocar el template:

```yaml
    macros:
      "{$AIRMAX.SENAL.WARN}": "-78"
      "{$AIRMAX.SENAL.CRIT}": "-84"
```

---

## 5. Router Mikrotik (RouterOS 6 / 7)

### 5.1 Habilitar SNMP (terminal / Winbox → New Terminal)

```
/system identity set name=Gateway_Mikrotik
/snmp community add name=<COMUNIDAD> addresses=<IP_SERVIDOR_ZABBIX>/32 read-access=yes write-access=no
/snmp community set [find default=yes] disabled=yes
/snmp set enabled=yes contact="Red Las Lagunitas" location="Torre Walter"
/ip firewall filter add chain=input protocol=udp dst-port=161 src-address=<IP_SERVIDOR_ZABBIX> action=accept place-before=0 comment="Zabbix SNMP"
/ip firewall filter add chain=input protocol=icmp src-address=<IP_SERVIDOR_ZABBIX> action=accept place-before=0 comment="Zabbix ICMP"
```

En Winbox: **IP → SNMP** (habilitar, *Communities* → agregar) y **IP → Firewall** (reglas).
La comunidad por defecto `public` queda deshabilitada.

### 5.2 Probar y cargar

```bash
bin/lagunitas probar-snmp 192.168.88.1
```

Debe reconocerlo como Mikrotik (RouterOS, serie, voltaje, temperatura, leases DHCP). En el
inventario usar `perfiles: [icmp, mikrotik_snmp]`, `funcion: router` y el modelo exacto.

- **Voltaje y temperatura** dependen del modelo: RB750Gr3/hEX y RB950 los informan; modelos sin
  sensor dejan esos ítems como no soportados.
- **Enlace a Internet**: se detecta la interfaz cuyo nombre coincide con `{$MIKROTIK.WAN.IFNAME}`
  (por defecto `^pppoe-out[0-9]+$`). Si la salida es otra (por ejemplo `ether1` con IP fija),
  ajustar la macro en el inventario del gateway:

```yaml
    macros:
      "{$MIKROTIK.WAN.IFNAME}": "^ether1$"
```

### 5.3 Alertas y umbrales

| Alerta | Condición por defecto | Severidad | Macro |
|---|---|---|---|
| **Sin enlace a Internet (PPPoE)** | Interfaz WAN distinta de up o sin datos 5 min | **Disaster** | `{$MIKROTIK.WAN.IFNAME}` |
| Voltaje bajo / crítico | Promedio < 12,0 V (10 min) / < 11,6 V (5 min) | Warning / High | `{$MIKROTIK.VOLTAJE.WARN}`, `{$MIKROTIK.VOLTAJE.CRIT}` |
| Voltaje excesivo | > 14,8 V | Average | `{$MIKROTIK.VOLTAJE.MAX}` |
| Sin clientes DHCP | 0 leases durante 30 min | Warning | — |
| CPU / memoria / temperatura altas | > 85 % / > 90 % / > 65 °C | Warning | `{$MIKROTIK.CPU.WARN}`, etc. |
| Interfaz sin enlace / con errores, sin datos SNMP, reinicio, cambio de RouterOS | | | |

Referencia de batería VRLA 12 V (en reposo): 12,7 V ≈ 100 %, 12,4 V ≈ 75 %, 12,2 V ≈ 50 %,
12,0 V ≈ 25 %, < 11,8 V descarga profunda (acorta la vida útil de la batería).

---

## 6. Routers airCube (hogares)

El airCube no ofrece SNMP ni una API documentada: se monitorea solo por **ICMP**.

1. Asignarle una IP de gestión fija (reserva DHCP en el Mikrotik por su MAC).
2. Verificar ping desde el servidor: `docker compose exec zabbix-server fping -c3 <IP>`.
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

Si el router del hogar está caído pero la radio responde, el problema es del lado del hogar
(energía, router apagado); si cae la radio, el router queda "Sin servicio".

---

## 7. Access points UniFi (API de UniFi Network)

1. En **UniFi Network**: *Settings → Control Plane → Integrations → Create API Key*. Guardarla en
   `.env` como `UNIFI_API_KEY` (se carga en Zabbix como macro secreta).
2. Averiguar IP y puerto del controlador. En **UniFi OS Server** sobre macOS el puerto HTTPS puede
   no ser 443 y **cambiar al reiniciar** (lo expone `gvproxy`):

   ```bash
   lsof -nP -iTCP -sTCP:LISTEN | grep -iE "gvproxy|unifi"
   ```

3. Obtener los IDs de site y dispositivo:

   ```bash
   bin/lagunitas unifi-ids <IP_CONTROLADOR> <PUERTO>
   ```

   Ejemplo real del laboratorio (controlador en la Mac, AP en la 192.168.1.113):

   ```
   Site: Default   {$UNIFI.SITE.ID} = 88f7af54-98f8-306a-a1c7-c9349722b1f6
     - U7-Pro-Wall  modelo=U7-Pro-Wall  ip=192.168.1.113  estado=ONLINE  {$UNIFI.DEVICE.ID} = afd2ff68-...
   ```

4. Cargar en el inventario con esas macros:

```yaml
  - host: AP-U7-Pro-Wall
    nombre: AP U7 Pro Wall
    rol: ap
    ip: 192.168.1.113
    perfiles: [icmp, unifi_api]      # en el LAB sobre Colima: solo [unifi_api] (ver guía de implementación)
    funcion: ap
    modelo: Ubiquiti UniFi U7 Pro Wall
    macros:
      "{$UNIFI.HOST}": 192.168.1.81
      "{$UNIFI.PORT}": "11443"
      "{$UNIFI.SITE.ID}": 88f7af54-98f8-306a-a1c7-c9349722b1f6
      "{$UNIFI.DEVICE.ID}": afd2ff68-17b3-3b64-8473-8eebfbe60d12
```

Alertas: controlador no accesible, sin datos de la API, AP fuera de línea según UniFi (High), CPU
y memoria altas, reintentos altos por banda, reinicio y cambio de firmware.

---

## 8. Otros equipos

- **Switches, cámaras, servidores, sensores con IP**: agregarlos con `perfiles: [icmp]`.
- **Equipos con SNMP estándar** (switches administrables, UPS): se puede vincular a mano un template
  oficial de Zabbix (por ejemplo *Generic by SNMP*) desde *Data collection → Hosts*, o sumar un
  perfil nuevo en `lagunitas/model.py` (`PERFILES`) para que lo gestione el provisionador.

---

## 9. Energía de los nodos solares

Los controladores de carga **Epever LS-E** instalados no tienen puerto de comunicación, por lo que
Zabbix no puede leer la batería directamente. Alternativas, en orden de costo:

1. **Voltaje del Mikrotik** (ya soportado): si el router se alimenta de la batería del nodo,
   `mtxrHlVoltage` refleja su estado de carga y dispara las alertas de voltaje bajo/crítico.
2. **Ping Watchdog y reinicios**: la alerta "el equipo se reinició" en horarios nocturnos es un
   indicador indirecto de batería insuficiente.
3. **Reemplazo por controladores con RS-485/Modbus** (por ejemplo Epever Tracer) más un pequeño
   gateway Modbus-TCP, o un sensor de tensión en la red LoRaWAN existente: se integrarían con un
   template adicional (voltaje de batería, corriente de panel, energía generada).

---

## 10. Verificación después de integrar

- [ ] `bin/lagunitas verificar`: el equipo figura y no tiene ítems no soportados inesperados.
- [ ] *Monitoring → Latest data* (filtrar por el equipo): los ítems tienen valores recientes.
- [ ] A los 10–15 minutos el descubrimiento creó interfaces (y estaciones, en airMAX).
- [ ] En el widget **Red Las Lagunitas** aparece "En línea" y la columna *Enlace / energía* muestra
      señal/CCQ o voltaje/DHCP.
- [ ] El modal del equipo muestra las pestañas propias de su tipo y *Depende de* es correcto.
- [ ] En el mapa aparece en su sitio con el enlace correcto.
- [ ] **Prueba de alerta controlada** (en una ventana acordada): desconectar el equipo o bloquear el
      ping y confirmar que llega **una sola** alerta y que los equipos que dependen de él quedan
      "Sin servicio".

---

## 11. Validar antes en el laboratorio

El laboratorio simula agentes SNMP con los OIDs reales de Ubiquiti y Mikrotik
(`lab/snmpsim/`). Cada equipo del inventario con `airos_snmp` o `mikrotik_snmp` corre un agente
simulado (radio AP, radio estación o router) y responde como el equipo real.

Escenarios de falla para ver cómo reacciona el sistema:

| Comando | Aplica a | Alertas que produce |
|---|---|---|
| `bin/lagunitas lab escenario <equipo> senal-debil` | radios | Señal débil, SNR bajo, señal débil de la estación |
| `... senal-critica` | radios | Señal crítica, CCQ y calidad bajos |
| `... interferencia` | radios | Ruido alto, CCQ bajo, calidad/capacidad airMAX bajas |
| `... sin-estaciones` | radio AP | Radio AP sin estaciones asociadas |
| `... bateria-baja` / `bateria-critica` | Mikrotik | Voltaje bajo / crítico |
| `... sin-internet` | Mikrotik | Sin enlace a Internet (Disaster) + interfaz sin enlace |
| `... sin-clientes` | Mikrotik | Sin clientes DHCP (a los 30 min) |
| `... normal` | todos | Restaura los valores normales |
| `bin/lagunitas lab caida <equipo>` | todos | Caída del equipo; sus dependientes quedan "Sin servicio" |

`bin/lagunitas probar-snmp <ip>` funciona igual contra los agentes simulados (IPs 10.50.0.x).

---

## 12. Referencia de OIDs utilizados

| Dato | OID | MIB |
|---|---|---|
| Modelo / firmware airOS | 1.2.840.10036.3.1.2.1.3.5 / .4.5 | IEEE802dot11-MIB |
| Modo, frecuencia, potencia, distancia, antena | 1.3.6.1.4.1.41112.1.4.1.1.{2,4,6,7,9}.1 | UBNT-AirMAX-MIB (ubntRadioTable) |
| SSID, señal, RSSI, CCQ, ruido, tasas, ancho de canal, estaciones | 1.3.6.1.4.1.41112.1.4.5.1.{2,5,6,7,8,9,10,14,15}.1 | UBNT-AirMAX-MIB (ubntWlStatTable) |
| Calidad / capacidad airMAX | 1.3.6.1.4.1.41112.1.4.6.1.{3,4}.1 | UBNT-AirMAX-MIB (ubntAirMaxTable) |
| Estaciones asociadas | 1.3.6.1.4.1.41112.1.4.7.1.* | UBNT-AirMAX-MIB (ubntStaTable) |
| CPU / temperatura airOS 8 | 1.3.6.1.4.1.41112.1.4.8.{3,4}.0 | UBNT-AirMAX-MIB (ubntHost) |
| Memoria airOS | 1.3.6.1.4.1.10002.1.1.1.1.{1,2}.0 | FROGFOOT-RESOURCES-MIB |
| Voltaje / temperatura Mikrotik | 1.3.6.1.4.1.14988.1.1.3.{8,10,11}.0 | MIKROTIK-MIB (décimas) |
| Leases DHCP / RouterOS / serie | 1.3.6.1.4.1.14988.1.1.6.1.0 / .4.4.0 / .7.3.0 | MIKROTIK-MIB |
| CPU / memoria Mikrotik | 1.3.6.1.2.1.25.3.3.1.2 / 1.3.6.1.2.1.25.2.3.1.{5,6}.65536 | HOST-RESOURCES-MIB |
| Interfaces | 1.3.6.1.2.1.2.2.1.* y 1.3.6.1.2.1.31.1.1.1.* | IF-MIB |

---

## 13. Problemas frecuentes al integrar

| Síntoma | Causa probable | Solución |
|---|---|---|
| `probar-snmp`: *Timeout* | SNMP deshabilitado, comunidad distinta, firewall o ruta | Revisar §4.1/§5.1; probar ping; revisar reglas UDP/161 del Mikrotik y de la VPN |
| Solo `sysName`/`uptime` responden | El equipo no es airMAX ni Mikrotik | Integrarlo solo con `[icmp]` |
| CPU/temperatura airMAX *no soportados* | airOS 6 (serie M) no expone `ubntHost` | Normal: deshabilitar esos dos ítems en el host |
| Voltaje Mikrotik *no soportado* | Modelo sin sensor | Normal; considerar §9 |
| Sin "enlace a Internet" descubierto | La WAN no se llama `pppoe-outN` | Ajustar `{$MIKROTIK.WAN.IFNAME}` |
| Estaciones no aparecen | El descubrimiento corre cada 10 min | Esperar o *Execute now* en la regla de descubrimiento |
| UniFi: *controlador no accesible* | IP o puerto del controlador cambiaron | `lsof` en el controlador (§7) y corregir `{$UNIFI.HOST}` / `{$UNIFI.PORT}` |
| UniFi: HTTP 401 | API key inválida o revocada | Crear una nueva y actualizar `UNIFI_API_KEY`; `aprovisionar --solo hosts` |
| UniFi: HTTP 404 | Site o device ID incorrectos | `bin/lagunitas unifi-ids` |
| Alerta duplicada "sin datos SNMP" + "sin respuesta" | — | No ocurre: "sin datos SNMP" depende de la caída ICMP del mismo equipo |
