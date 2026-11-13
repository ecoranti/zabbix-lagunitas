# Guía del laboratorio

**Versión 2.4** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas (Alpa Corral, Córdoba)

Esta guía explica cómo **levantar, usar y mantener el laboratorio** del sistema de monitoreo de
la Red Las Lagunitas sobre una Mac. Describe los componentes, la instalación desde cero, el uso
diario, las pruebas de alertas, el trabajo con el código y la resolución de los problemas que
aparecieron durante el desarrollo.

> El laboratorio **no es producción**. Es el entorno en el que se desarrolló y validó el sistema,
> con la topología de la red reproducida mediante equipos simulados. Para el servidor real están
> la [Guía de implementación](guia-implementacion.md), la
> [Guía de integración de equipos](guia-integracion-equipos.md) y el
> [Manual de administración](manual-administracion.md). Qué reemplaza en la red real a cada pieza
> del laboratorio está en la sección *Del laboratorio a la red real* de la Guía de implementación.

---

## Resumen de un vistazo

| Qué | Dónde / cómo |
|---|---|
| Carpeta del proyecto | `~/zabbix-lab` |
| Arrancar todo | `./start.sh` |
| Apagar todo (conserva datos) | `./start.sh down` |
| Aplicar la configuración en Zabbix | `bin/lagunitas aprovisionar` |
| Chequeo de salud | `bin/lagunitas verificar` |
| Frontend | <http://localhost:8090> (usuario `Admin`, clave en `.env` → `ZABBIX_PASSWORD`) |
| Dashboard principal | *Dashboards → Las Lagunitas - Centro de monitoreo* |
| Reporte | *Reports → Disponibilidad de la red* |
| Estado de los equipos simulados | `bin/lagunitas lab estado` |
| Simular una caída | `bin/lagunitas lab caida Nodo_Kika` / `bin/lagunitas lab recuperar Nodo_Kika` |
| Ping real al AP | `bin/lagunitas lab sonda` (o el agente launchd) |
| Secretos | `.env` (nunca se sube a git) |
| Alertas por Telegram | Grupo *Operadores Las Lagunitas* (bot `@lagunitasBot`); prueba: `bin/lagunitas probar-telegram` |
| Repositorio | `https://github.com/ecoranti/zabbix-lagunitas` (rama estable `main`, rama de trabajo `feature/produccion-v2`) |

---

## Qué hay en el laboratorio

```
Mac (Apple Silicon)
 ├─ Colima (máquina virtual Linux donde corre Docker)
 │   ├─ Stack Zabbix 7.0.30 (docker-compose.yml)
 │   │   ├─ mysql-server      base de datos MySQL 8.0 (datos en ./mysql_data)
 │   │   ├─ zabbix-server     recolecta y evalúa alertas (puerto 10051)
 │   │   ├─ zabbix-web        frontend (http://localhost:8090) + módulos propios
 │   │   └─ zabbix-agent      auto-monitoreo del servidor
 │   └─ Red lagunitas_net (10.50.0.0/24): un contenedor por equipo operativo del inventario
 │       ├─ equipos solo-ping (Alpine mínimo)
 │       └─ equipos SNMP simulados (radios airMAX AP/estación y router Mikrotik)
 ├─ UniFi OS Server (192.168.1.81, HTTPS en el puerto 11443)
 ├─ Sonda ICMP (bin/lagunitas lab sonda): ping real al AP y envío a Zabbix
 └─ AP UniFi U7 Pro Wall real → 192.168.1.113
```

| Componente | Detalle |
|---|---|
| Inventario | `config/inventory.lab.yaml`: misma topología que producción (gateway, 4 torres, 9 nodos, 13 hogares e instituciones), con IPs 10.50.0.x, más el AP real. En total 33 equipos, de los cuales 21 están en estado `operativo` |
| Equipos simulados | Cada equipo operativo del inventario con IP en `10.50.0.0/24` es un contenedor con esa IP fija (20 contenedores). Los de perfil `airos_snmp` / `mikrotik_snmp` responden SNMP v2c con los OIDs reales del fabricante (`lab/snmpsim/`, comunidad `public`) |
| AP real | U7 Pro Wall en `192.168.1.113`, monitoreado por la **API de UniFi** y por la **sonda ICMP** |
| Módulos propios | `zabbix/modules/lagunitas-red` (widget *Red Las Lagunitas*) y `zabbix/modules/lagunitas-reportes` (*Reports*). Están montados en el contenedor web: los cambios se ven al recargar |
| Provisionador | `bin/lagunitas` (Python). Crea todo en Zabbix desde el inventario; se puede correr las veces que haga falta |

Las direcciones `192.168.1.x` corresponden a la red doméstica en la que se montó el laboratorio.
En otra red hay que reemplazarlas en el inventario por las del AP y del controlador propios.

Diferencias del stack respecto de producción (`deploy/produccion/`):

| Aspecto | Laboratorio | Producción |
|---|---|---|
| Acceso al frontend | HTTP en el puerto 8090 de la Mac | HTTPS con Caddy |
| Datos de MySQL | Carpeta `./mysql_data` | Volumen con nombre |
| Registro binario de MySQL | Deshabilitado (`--skip-log-bin`): no hay replicación y solo ocupaba disco | Habilitado, con vencimiento a las 24 h |
| Historial | 7 días (`retencion_historial: 7d` en el inventario) | 90 días (valor de los templates) |
| Logs de los contenedores | Rotados (20 MB × 3 en el stack, 5 MB × 2 en los equipos simulados); los agentes SNMP simulados solo registran errores | Rotados (20 MB × 5) |
| Equipos | Contenedores en `lagunitas_net` y un AP real | Equipos reales |

### Por qué el AP usa una sonda (limitación de Colima)

Zabbix corre dentro de la máquina virtual de Colima, y la red de esa máquina **contesta sola los
pings dirigidos a IPs de afuera**. Comprobado:

| Ping a | Desde el contenedor de Zabbix | Desde la Mac |
|---|---|---|
| AP `192.168.1.113` | responde, ~0,8 ms | responde, ~4 ms (real) |
| `192.168.1.250` (no existe) | **responde** | no responde (real) |

Por eso el AP no usa el ping del Zabbix server. Usa el perfil `icmp_sonda`: la Mac hace el
ping y envía disponibilidad, pérdida y latencia a Zabbix cada 10 s. El template
*Lagunitas - Disponibilidad ICMP - sonda externa* tiene las mismas mediciones y alertas que el de
producción, así que dashboard, widget, reporte y dependencias lo tratan igual.

Los contenedores de `lagunitas_net` sí son reales (se apagan de verdad). **En producción (Linux)
esto no pasa** y el AP usa el perfil `icmp` normal.

---

## Requisitos

| Recurso | Detalle |
|---|---|
| Equipo | Mac con procesador Apple Silicon y macOS |
| Software | [Homebrew](https://brew.sh), Colima, cliente Docker con el plugin Compose, Git y Python 3 |
| Máquina virtual de Colima | 4 CPU, 6 GB de RAM y 40 GB de disco (configuración con la que se validó el laboratorio) |
| Red | Salida a Internet para descargar imágenes y dependencias. Para el AP real, la Mac debe estar en la misma red que el AP y el controlador UniFi |
| Puertos locales | 8090/TCP (frontend) y 10051/TCP (Zabbix server) libres en la Mac |

El AP real y UniFi OS Server son opcionales. Sin ellos, el laboratorio funciona con los 20
equipos simulados, y el host `AP-U7-Pro-Wall` puede pasarse a `sin_configurar` en el inventario.

---

## Instalación desde cero

Solo hace falta si la Mac es nueva o se borró el proyecto.

### Herramientas

```bash
brew install colima docker docker-compose git
colima start --cpu 4 --memory 6 --disk 40
docker compose version
```

Los recursos de la máquina virtual se indican solo la primera vez. Después alcanza con
`colima start` (o `./start.sh`), que conserva esa configuración. Si `docker compose version`
falla, seguir la indicación que muestra Homebrew al instalar `docker-compose` para registrar el
plugin en `~/.docker/config.json`.

### Repositorio

```bash
git clone https://github.com/ecoranti/zabbix-lagunitas.git ~/zabbix-lab
cd ~/zabbix-lab
```

La rama `main` contiene la versión estable. El desarrollo se hace en `feature/produccion-v2`
(`git checkout feature/produccion-v2`) y se integra a `main` mediante pull requests.

### Secretos

Copiar la plantilla y completar **todas** las claves:

```bash
cp .env.example .env && chmod 600 .env
```

| Variable | Qué poner en el laboratorio |
|---|---|
| `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | Claves propias (no las de ejemplo) |
| `ZABBIX_WEB_PORT` | `8090` |
| `ZABBIX_URL` | `http://localhost:8090/api_jsonrpc.php` |
| `ZABBIX_USER` / `ZABBIX_PASSWORD` | `Admin` y su clave (o `ZABBIX_API_TOKEN`) |
| `LAGUNITAS_INVENTORY` | `config/inventory.lab.yaml` |
| `UNIFI_API_KEY` | API key de UniFi Network (*Settings → Control Plane → Integrations → Create API Key*) |
| `SNMP_COMMUNITY` | `public` (la de los agentes simulados) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Opcional |

Conviene mantener el puerto `8090`. `start.sh` espera el frontend y abre el navegador en ese
puerto, salvo que `ZABBIX_WEB_PORT` esté exportada en la terminal.

### Primer arranque

```bash
./start.sh
```

La primera vez descarga las imágenes, crea la base (MySQL tarda 1–2 minutos) y construye la
imagen del agente SNMP simulado.

Entrar a <http://localhost:8090> con `Admin` / `zabbix` (clave de fábrica de una base nueva) y
cambiarla en *User settings → Profile → Change password* por la misma que se puso en
`ZABBIX_PASSWORD` de `.env`. El provisionador entra con esa clave.

### Aprovisionar y verificar

```bash
bin/lagunitas aprovisionar
bin/lagunitas verificar
```

La primera vez `bin/lagunitas` crea solo el entorno Python (`.venv`). Resultado esperado de
`verificar`: 33 hosts en Zabbix y 33 en el inventario, sin hosts faltantes. A los pocos minutos,
en *Dashboards → Las Lagunitas - Centro de monitoreo*, los equipos operativos figuran "En línea".

El arranque automático al iniciar sesión es opcional (sección *Arranque automático*).

---

## Uso diario

### Arrancar

```bash
cd ~/zabbix-lab
./start.sh
```

Hace, en orden: inicia Colima si está apagada, crea la red `lagunitas_net` si falta, levanta el
stack Zabbix, espera el frontend, levanta los equipos simulados y abre el navegador.

Después, si la sonda no está instalada como agente launchd:

```bash
nohup bin/lagunitas lab sonda > /tmp/lagunitas-sonda.log 2>&1 &
```

Controles rápidos:

```bash
docker compose ps                   # los 4 servicios del stack en ejecución
bin/lagunitas verificar             # hosts faltantes, ítems no soportados, problemas abiertos
bin/lagunitas lab estado            # contenedor y perfil de cada equipo simulado
bin/lagunitas lab sonda --una-vez   # ping real al AP (debe decir "responde")
```

### Apagar

```bash
./start.sh down
```

Detiene los equipos simulados y el stack. **Los datos se conservan** (`./mysql_data`). Para apagar
también la máquina virtual: `colima stop`.

### Después de cambiar el inventario o el código

```bash
bin/lagunitas validar                         # revisa el YAML sin tocar Zabbix
bin/lagunitas aprovisionar                    # aplica todo
bin/lagunitas aprovisionar --solo dashboard   # solo un paso
bin/lagunitas lab levantar                    # crea/recrea contenedores si cambiaron equipos
```

Pasos disponibles para `--solo`: `templates`, `hosts`, `dependencias`, `servidor`, `mapa`,
`servicios`, `modulos`, `dashboard`, `alertas`.

| Si se cambió… | Ejecutar |
|---|---|
| Un equipo en el inventario (alta, baja, IP, padre, estado) | `aprovisionar` y `lab levantar` |
| Un template (ítems, triggers, umbrales) | `aprovisionar --solo templates` |
| El dashboard | `aprovisionar --solo dashboard` |
| La clave `retencion_historial` del inventario | `aprovisionar --solo servidor` |
| CSS / PHP / JS de un módulo | Nada: recargar el navegador con **Cmd + Shift + R** |
| `docker-compose.yml` o `.env` del stack | `docker compose up -d` |

### Subcomandos del simulador

| Comando | Qué hace |
|---|---|
| `bin/lagunitas lab levantar` | Crea o inicia un contenedor por equipo operativo y elimina los de equipos que dejaron de estarlo |
| `bin/lagunitas lab apagar` | Detiene todos los contenedores simulados |
| `bin/lagunitas lab estado` | Lista IP, perfil simulado, estado en el inventario y estado del contenedor |
| `bin/lagunitas lab caida <equipo> [--solo]` | Detiene el equipo y sus dependientes (con `--solo`, únicamente ese equipo) |
| `bin/lagunitas lab recuperar <equipo> [--solo]` | Vuelve a iniciarlos |
| `bin/lagunitas lab latencia <equipo> [ms\|normal]` | Agrega un retardo a las respuestas del equipo con `tc netem` (por defecto 300 ms) o lo quita |
| `bin/lagunitas lab pruebas [1-4]` | Menú interactivo (con flechas) para disparar y deshacer todas las fallas simuladas; con un número, corre la prueba de validación guiada |
| `bin/lagunitas lab escenario <equipo> <escenario>` | Aplica una falla de radio o energía al agente SNMP simulado |
| `bin/lagunitas lab sonda [--intervalo N] [--una-vez]` | Sonda ICMP desde la Mac para los equipos con perfil `icmp_sonda` |

El `<equipo>` es el nombre técnico (`host`) del inventario. El resto de los subcomandos de
`bin/lagunitas` figura en la Guía de implementación, sección *Referencia del CLI*.

---

## Recorrido por el frontend

| Lugar | Para qué |
|---|---|
| *Dashboards → Las Lagunitas - Centro de monitoreo* | Páginas **Estado de la red** (panal, mapa, alertas), **Equipos** (widget propio: clic en un equipo abre el detalle con pestañas), **Detalle por equipo** (elegir un equipo a la izquierda), **AP UniFi**, **SLA** |
| *Reports → Disponibilidad de la red* | Reporte con filtros, CSV y PDF; botón **Ver detalle** para el detalle técnico de un equipo |
| *Monitoring → Problems* | Alertas activas e historial |
| *Monitoring → Latest data* | Últimos valores de cada medición |
| *Monitoring → Maps* | Topología |
| *Services → SLA report* | Cumplimiento mensual |
| *Data collection → Hosts* | Hosts, templates, macros de cada equipo |
| *Administration → Macros* | `{$LAGUNITAS.INTERVALO}` (frecuencia de medición, hoy `10s`) |
| *Administration → Housekeeping* | Retención global del historial (la fija el aprovisionamiento) |
| *Administration → General → Modules* | Módulos propios (**Scan directory** para ver la versión nueva) |

**Selector de tiempo:** los gráficos usan el rango de arriba a la derecha. Si se arrastra el mouse
sobre un gráfico, queda fijo en ese rango (y se guarda en el usuario). Si los gráficos aparecen
vacíos o con fechas viejas, elegir *Last 6 hours* (u otro rango relativo).

**PDF de los reportes:** usar el botón *Imprimir / PDF*. En Chrome sale con pie propio
("Página X de Y"); en Safari, desmarcar *Imprimir encabezados y pies de página*.

---

## Frecuencia de actualización y retención

| Qué | Frecuencia |
|---|---|
| Mediciones de todos los equipos (ICMP, SNMP, API UniFi, sonda) | 10 s (macro `{$LAGUNITAS.INTERVALO}`) |
| Disponibilidad 24 h / 7 días | 1 min |
| Datos estáticos (modelo, firmware, SSID, serie) | 1 h |
| Descubrimiento de interfaces y estaciones | 10 min / 1 h |
| Widgets de dashboards y pantallas del frontend | 10 s |

Para medir más lento (por ejemplo si la Mac va cargada): *Administration → Macros* →
`{$LAGUNITAS.INTERVALO}` = `30s`. No hace falta reaprovisionar, y el aprovisionamiento respeta el
valor ajustado a mano. La sonda tiene su propio intervalo: `bin/lagunitas lab sonda --intervalo 30`.

**Retención del historial.** Con mediciones cada 10 s, los 90 días de historial que definen los
templates ocupan varios GB. Por eso el inventario del laboratorio fija `retencion_historial: 7d`.
El paso `servidor` del aprovisionamiento aplica ese valor como retención global en
*Administration → Housekeeping*, en reemplazo del período de cada ítem. Las tendencias horarias
no cambian y se conservan 365 días. El inventario de producción no define la clave, de modo que
allí rigen los 90 días.

---

## Pruebas de alertas

### Caídas (contenedores reales)

```bash
bin/lagunitas lab caida Nodo_Kika            # cae el nodo y su hogar queda "Sin servicio": 1 alerta
bin/lagunitas lab recuperar Nodo_Kika
bin/lagunitas lab caida Union_de_los_Rios    # caída troncal: 1 alerta, el resto "Sin servicio"
bin/lagunitas lab recuperar Union_de_los_Rios
bin/lagunitas lab caida Kika --solo          # solo ese equipo, sin sus dependientes
```

Todas las fallas se pueden disparar y deshacer desde un menú interactivo
(`scripts/pruebas-validacion.sh` o `bin/lagunitas lab pruebas`). El menú lista los equipos
simulados con su estado, la falla simulada que tienen activa y cuántos equipos arrastra cada uno,
y marca con `↳` los que caerían junto con el seleccionado. Se navega con las flechas:

| Tecla | Acción |
|---|---|
| `Enter` | Tira abajo el equipo (con sus dependientes) si está en línea, o lo levanta si está caído |
| `s` | Lo mismo, solo con ese equipo |
| `e` | Aplica al equipo un escenario SNMP (`normal` lo restaura); solo los que corresponden a su perfil |
| `l` | Agrega o quita 300 ms de latencia («latencia alta», Warning, en ~3 min) |
| `1` a `4` | Activa o deshace la prueba documentada completa (ver la tabla siguiente) |
| `t` | Restaura todo: levanta los equipos y quita escenarios y latencia |
| `q` | Sale; si quedó algo caído o con falla, ofrece restaurarlo |

El panel inferior muestra los problemas abiertos en Zabbix y los avisos de Telegram de la última
media hora (enviado o falló), y se actualiza cada 10 s. Así se ve cada alerta abrirse y cerrarse,
y su notificación, sin salir del menú.

### Pruebas de validación guiadas

Las pruebas de la etapa de validación se corren de punta a punta con
`scripts/pruebas-validacion.sh N` (o `bin/lagunitas lab pruebas N`). Cada una aplica la falla,
muestra en vivo los problemas que abre Zabbix y el estado de cada aviso de Telegram (leídos de la
API), restaura el equipo, espera el cierre y el aviso de resuelto, y termina con un resumen de
tiempos:

| N | Prueba | Qué hace | Qué se espera |
|---|---|---|---|
| 1 | Degradación por SNMP | `senal-debil` en Walter, `interferencia` en Mesada y `bateria-baja` en el Gateway. Restaura con Enter o a los 15 min | 6 o 7 alertas Warning entre los 6 y 11 min (SNR y calidad dependen de la oscilación simulada) y cierre automático en menos de 10 min |
| 2 | Caída troncal | Detiene Unión de los Ríos y sus 18 dependientes; restaura 60 s después del aviso | Una única alerta High en ~90 s y un único aviso por Telegram |
| 3 | Telegram | Detiene el Nodo Kika (y el hogar Kika); restaura 60 s después del aviso | Un aviso al grupo de operadores y, como respuesta a ese mensaje, «Nodo Kika volvió a estar en línea» con el enlace restablecido (Kika) |
| 4 | Latencia alta | 300 ms de retardo en las respuestas de Mesada (`tc netem`); lo quita cuando sale el aviso | «Mesada: latencia alta» (Warning) en ~3 min con su aviso, y cierre ~3 min después de quitarla |

Ctrl+C interrumpe la prueba y restaura los equipos. Las cuatro pruebas notifican por Telegram
porque la acción avisa desde Warning.

`caida` detiene también a los equipos aguas abajo, porque en la red real pierden el camino. Así
se ve el efecto de las dependencias: **una sola alerta** por la caída troncal. La alerta aparece
a los ~2 min: cada nivel de la topología espera 15 s más que su padre (90 s el gateway,
105 s las torres, 120 s el nivel siguiente…), así el padre siempre se detecta primero. Al
recuperar, el problema se cierra solo en menos de un minuto.

Qué mirar: *Estado de la red* (panal y mapa en rojo), *Equipos* (el equipo "Caído" y sus
dependientes "Sin servicio"), *Monitoring → Problems* y, después, el reporte.

### Fallas de radio y energía (SNMP simulado)

| Comando | Aplica a | Alertas que produce |
|---|---|---|
| `bin/lagunitas lab escenario <equipo> senal-debil` | radios | Señal débil, SNR bajo, señal débil de la estación |
| `... senal-critica` | radios | Señal crítica, SNR bajo, CCQ bajo, calidad y capacidad airMAX bajas |
| `... interferencia` | radios | Ruido alto en el canal, SNR bajo, CCQ bajo, calidad y capacidad airMAX bajas |
| `... sin-estaciones` | radio AP | Radio AP sin estaciones asociadas |
| `... bateria-baja` / `bateria-critica` | Mikrotik | Voltaje bajo / crítico |
| `... sin-internet` | Mikrotik | Sin enlace a Internet (Disaster) + interfaz sin enlace |
| `... sin-clientes` | Mikrotik | Sin clientes DHCP (a los 30 min) |
| `... normal` | todos | Restaura los valores normales |

Ejemplos: `bin/lagunitas lab escenario Walter senal-debil`,
`bin/lagunitas lab escenario Gateway_Mikrotik sin-internet`. Las alertas de la tabla surgen de
comparar los valores de cada escenario con los umbrales por defecto de los templates. Las que se
basan en promedios de 5 a 15 minutos aparecen entre 1 y 15 minutos después. Al terminar, **volver siempre** al escenario
`normal`.

Los valores simulados están en `lab/snmpsim/data/*.snmprec` (formato `OID|tipo|valor`; los
valores numéricos oscilan para que los gráficos se vean realistas).

### AP real

- Apagar el AP (o desenchufarlo): a los ~90 s (es raíz, nivel 0) aparece *sin respuesta (ICMP)*.
  Cuando el controlador lo informa desconectado se suma *AP fuera de línea según UniFi*.
- Apagar UniFi OS Server: aparece *controlador UniFi no accesible* a los 3 min.
- Detener la sonda: aparece *la sonda ICMP no envía datos* a los 3 min.

---

## AP UniFi real

| Dato | Valor |
|---|---|
| AP | U7 Pro Wall, `192.168.1.113` |
| Controlador | UniFi OS Server en la misma Mac, `192.168.1.81`, puerto HTTPS `11443` |
| API key | `.env` → `UNIFI_API_KEY` (se carga en Zabbix como macro secreta; nunca en git) |
| IDs de site y dispositivo | En `config/inventory.lab.yaml` (macros del host `AP-U7-Pro-Wall`) |

El puerto del controlador lo expone `gvproxy` y **puede cambiar al reiniciar** UniFi OS Server:

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep -iE "gvproxy|unifi"
```

Si cambió, actualizar `{$UNIFI.PORT}` en el inventario y correr
`bin/lagunitas aprovisionar --solo hosts`. Para ver los IDs:

```bash
bin/lagunitas unifi-ids 192.168.1.81 11443
```

---

## Sonda ICMP

```bash
bin/lagunitas lab sonda --una-vez      # una medición, muestra el resultado
bin/lagunitas lab sonda                # continuo cada 10 s (Ctrl+C para detener)
pkill -f "lagunitas lab sonda"         # detener la que corre en segundo plano
tail -f /tmp/lagunitas-sonda.log       # log
```

Mide los equipos del inventario con perfil `icmp_sonda` y estado `operativo` (hoy, solo el AP).
Cada ciclo envía tres pings por equipo con el comando `ping` de macOS y carga en Zabbix, por la
API, la disponibilidad, la pérdida y la latencia. Usa las credenciales de `.env`, igual que el
provisionador.

---

## Arranque automático

Dos agentes launchd opcionales, en `scripts/launchd/`:

| Agente | Qué hace |
|---|---|
| `ar.lagunitas.zabbix-lab.plist` | Corre `./start.sh` al iniciar sesión (sin abrir el navegador) |
| `ar.lagunitas.sonda-icmp.plist` | Mantiene la sonda ICMP corriendo (la reinicia si se cae) |

Instalar (desde `~/zabbix-lab`):

```bash
for a in zabbix-lab sonda-icmp; do sed "s#RUTA_DEL_REPO#$PWD#g" scripts/launchd/ar.lagunitas.$a.plist > ~/Library/LaunchAgents/ar.lagunitas.$a.plist; done
```

```bash
pkill -f "lagunitas lab sonda"; launchctl load ~/Library/LaunchAgents/ar.lagunitas.zabbix-lab.plist ~/Library/LaunchAgents/ar.lagunitas.sonda-icmp.plist
```

Desinstalar: `launchctl unload ~/Library/LaunchAgents/ar.lagunitas.<agente>.plist`.
Logs: `/tmp/zabbix-lab.log` y `/tmp/lagunitas-sonda.log`.

---

## Backups del laboratorio

Ejecutar los scripts desde la carpeta del proyecto:

```bash
scripts/backup.sh                                        # a ./backups (base comprimida + export YAML)
scripts/restore.sh backups/zabbix_AAAAMMDD_HHMM.sql.gz   # ¡reemplaza TODO lo actual!
bin/lagunitas exportar                                   # templates y mapa a zabbix/export/
```

`backup.sh` genera `zabbix_AAAAMMDD_HHMM.sql.gz` (volcado de la base) y
`config_AAAAMMDD_HHMM.tar.gz` (templates, mapa e inventarios), y borra los respaldos de más de
14 días. `restore.sh` primero comprueba que el volcado esté íntegro y completo, pide escribir
`RESTAURAR` para confirmar, detiene `zabbix-server` y `zabbix-web`, importa el volcado y los vuelve
a iniciar (también si la importación falla).

Conviene un backup antes de cambios grandes (migraciones, pruebas destructivas).

---

## Trabajo con el código y la documentación

| Carpeta / archivo | Qué es |
|---|---|
| `config/inventory.lab.yaml` | Inventario del laboratorio |
| `config/inventory.produccion.yaml` | Inventario de producción (IPs `# COMPLETAR`) |
| `lagunitas/` | Provisionador: `templates.py`, `templates_snmp.py`, `hosts.py`, `dashboards.py`, `widgets.py`, `lab.py`, `cli.py`, `model.py` |
| `zabbix/modules/` | Widget y reporte (PHP/JS/CSS) |
| `lab/snmpsim/` | Agentes SNMP simulados |
| `deploy/produccion/` | Stack productivo (Caddy + HTTPS) |
| `legacy/` | Scripts de la primera versión del laboratorio (histórico, no usar) |
| `docs/*.md` | Documentación (fuente); `docs/*.docx` se generan desde acá |

Si la base todavía tiene los hosts, el mapa y el dashboard de la primera versión del laboratorio,
`bin/lagunitas aprovisionar --migrar-v1` los elimina antes de aprovisionar. Es una operación
destructiva (se pierde el historial de esos hosts), por lo que conviene hacer un backup antes.

### Git

```bash
git status                     # revisar SIEMPRE qué se va a subir
git add <archivos concretos>   # nunca "git add -A" a ciegas
git commit -m "mensaje"
git push                       # rama feature/produccion-v2; se integra a main por pull request
```

- `.env`, `mysql_data/` y `backups/` están en `.gitignore`: nunca subir secretos.
- Si GitGuardian avisa de un secreto: rotar la clave en el servicio y en `.env`; borrar el commit
  no alcanza.

### Regenerar los Word

```bash
cd docs
../.venv/bin/pip install -r ../requirements-docs.txt     # solo la primera vez
../.venv/bin/python ../scripts/md2docx.py --portada plantilla/portada-unrc.docx laboratorio.md "Guia del laboratorio - Red Las Lagunitas.docx"
```

Lo mismo para `guia-implementacion.md`, `guia-integracion-equipos.md` y
`manual-administracion.md`. Al abrir el Word, aceptar **actualizar campos** para que se genere
el índice.

---

## Resolución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `failed to connect to the docker API ... colima` | Colima detenida | `colima start` o `./start.sh` |
| `docker compose` no se reconoce como comando | Plugin Compose sin registrar | Seguir la indicación de Homebrew para `docker-compose` (sección *Herramientas*) |
| El frontend no abre en <http://localhost:8090> | Stack caído o arrancando | `docker compose ps`; `docker compose logs --tail 50 zabbix-web zabbix-server`; `./start.sh` |
| Chrome: `ERR_ADDRESS_UNREACHABLE` al entrar por el nombre `.local` de la Mac | macOS bloquea a Chrome la red local | Usar `http://localhost:8090`, o *Ajustes del Sistema → Privacidad y seguridad → Red local* → activar Chrome y reiniciarlo |
| Gráficos vacíos o con fechas viejas | Selector de tiempo fijado en un rango absoluto | Elegir *Last 6 hours* arriba a la derecha |
| Un cambio en un módulo no se ve | Caché del navegador | **Cmd + Shift + R**; la versión nueva en *Modules* aparece con **Scan directory** |
| Zabbix muestra *Cannot load modules at: modules/lagunitas-…* | Git reescribió las carpetas de los módulos (cambio de rama, merge) y el contenedor web quedó apuntando a las viejas | `docker compose up -d --force-recreate zabbix-web` (no pierde datos) |
| Un equipo simulado figura caído | Contenedor detenido | `bin/lagunitas lab estado`; `bin/lagunitas lab recuperar <equipo>` o `bin/lagunitas lab levantar` |
| Alertas de radio/energía que no se van | Quedó un escenario activo | `bin/lagunitas lab escenario <equipo> normal` |
| *controlador UniFi no accesible* | UniFi OS Server apagado o cambió el puerto | Abrir UniFi OS Server; ver el puerto con `lsof` (sección *AP UniFi real*) y reaprovisionar hosts |
| *la sonda ICMP no envía datos* | Sonda detenida (por ejemplo, tras reiniciar la Mac) | `nohup bin/lagunitas lab sonda > /tmp/lagunitas-sonda.log 2>&1 &` o instalar el agente launchd |
| El AP "responde" aunque esté apagado | Se está usando el ping del server (Colima) | Verificar que el AP tenga el perfil `icmp_sonda` en el inventario |
| Ítems "no soportados" | Error de SNMP/API o de configuración | `bin/lagunitas verificar`; *Data collection → Hosts → Items* (columna *Info*) |
| `bin/lagunitas` falla con "Definí ZABBIX_API_TOKEN…" | `.env` incompleto | Completar `ZABBIX_USER`/`ZABBIX_PASSWORD` o `ZABBIX_API_TOKEN` |
| Error de YAML al aprovisionar | Sintaxis del inventario (dos puntos sin comillas, sangría) | `bin/lagunitas validar` muestra el detalle del error |
| El disco de la VM de Colima se llena (`colima ssh -- df -h /var/lib/docker`) | Logs de contenedores creados con una versión anterior, sin rotación (los agentes simulados registraban cada consulta SNMP) | `bin/lagunitas lab levantar` recrea los equipos simulados con logs rotados y `docker compose up -d` aplica la rotación al stack |
| El disco de la Mac se llena | Historial acumulado en `mysql_data` | Verificar `retencion_historial` en el inventario y ejecutar `bin/lagunitas aprovisionar --solo servidor`; subir el intervalo de medición |
| La Mac va lenta | Más de 20 contenedores y mediciones cada 10 s | Subir `{$LAGUNITAS.INTERVALO}` a `30s`; `./start.sh down` cuando no se use |

### Empezar de cero (borra la configuración y el historial)

Solo si la base quedó inservible y no hay backup que sirva:

```bash
./start.sh down
mv mysql_data mysql_data.viejo        # en lugar de borrar, por las dudas
./start.sh
```

Luego repetir el cambio de la clave de fábrica de `Admin` (*Primer arranque*) y los pasos de
*Aprovisionar y verificar*. Los datos viejos quedan en `mysql_data.viejo` hasta que se borren a
mano.

---

## Control de versiones del documento

| Versión | Cambios |
|---|---|
| 2.4 | Menú interactivo de pruebas (`lab pruebas`) con caídas, escenarios SNMP y latencia simulada (`lab latencia`, con `tc netem`); pruebas guiadas 1 a 4 con seguimiento de las alertas y de los avisos de Telegram; uptime y contadores del simulador SNMP al ritmo real. |
| 2.3 | Redacción impersonal y línea de versión; requisitos y recursos de Colima; diferencias con producción (`--skip-log-bin`, `retencion_historial`); subcomandos del simulador; alertas de cada escenario revisadas contra los umbrales; datos del repositorio y de la cantidad de equipos corregidos. |
| Anterior | Guía sin número de versión, contemporánea de la versión 2.2 de las demás guías (puesta en marcha, uso, sonda ICMP y problemas frecuentes). |
