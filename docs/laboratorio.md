# Guía del laboratorio

Guía personal para **levantar, usar y mantener el laboratorio** del monitoreo de la Red Las
Lagunitas en la Mac. Reúne todo en un solo lugar: qué es cada parte, cómo arrancar y apagar,
cómo probar alertas, cómo trabajar el código y cómo resolver los problemas que ya aparecieron.

> El laboratorio **no es producción**. Para el servidor real están la
> [Guía de implementación](guia-implementacion.md), la
> [Guía de integración de equipos](guia-integracion-equipos.md) y el
> [Manual de administración](manual-administracion.md).

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
| Rama de trabajo | `feature/produccion-v2` (PR #1 hacia `main`) |

---

## Qué hay en el laboratorio

```
Mac (Apple Silicon)
 ├─ Colima (máquina virtual Linux donde corre Docker)
 │   ├─ Stack Zabbix 7.0.30 (docker-compose.yml)
 │   │   ├─ mysql-server      base de datos (datos en ./mysql_data)
 │   │   ├─ zabbix-server     recolecta y evalúa alertas (puerto 10051)
 │   │   ├─ zabbix-web        frontend (http://localhost:8090) + módulos propios
 │   │   └─ zabbix-agent      automonitoreo del servidor
 │   └─ Red lagunitas_net (10.50.0.0/24): un contenedor por equipo del inventario
 │       ├─ equipos solo-ping (Alpine mínimo)
 │       └─ equipos SNMP simulados (radios airMAX AP/estación y router Mikrotik)
 ├─ UniFi OS Server (192.168.1.81, HTTPS en el puerto 11443)
 ├─ Sonda ICMP (bin/lagunitas lab sonda): ping real al AP y envío a Zabbix
 └─ AP UniFi U7 Pro Wall real → 192.168.1.113
```

| Componente | Detalle |
|---|---|
| Inventario | `config/inventory.lab.yaml`: misma topología que producción (gateway, 4 torres, 9 nodos, hogares e instituciones), con IPs 10.50.0.x, más el AP real |
| Equipos simulados | Cada equipo operativo del inventario es un contenedor con IP fija. Los de perfil `airos_snmp` / `mikrotik_snmp` responden SNMP con los OIDs reales (`lab/snmpsim/`) |
| AP real | U7 Pro Wall en `192.168.1.113`, monitoreado por la **API de UniFi** y por la **sonda ICMP** |
| Módulos propios | `zabbix/modules/lagunitas-red` (widget *Equipos*) y `zabbix/modules/lagunitas-reportes` (*Reports*). Están montados en el contenedor web: los cambios se ven al recargar |
| Provisionador | `bin/lagunitas` (Python). Crea todo en Zabbix desde el inventario; se puede correr las veces que haga falta |

### Por qué el AP usa una sonda (limitación de Colima)

Zabbix corre dentro de la máquina virtual de Colima, y la red de esa máquina **contesta sola los
pings dirigidos a IPs de afuera**. Comprobado:

| Ping a | Desde el contenedor de Zabbix | Desde la Mac |
|---|---|---|
| AP `192.168.1.113` | responde, ~0,8 ms | responde, ~4 ms (real) |
| `192.168.1.250` (no existe) | **responde** | no responde (real) |

Por eso el AP no usa el ping del Zabbix server. Usa el perfil **`icmp_sonda`**: la Mac hace el
ping y envía disponibilidad, pérdida y latencia a Zabbix cada 10 s. El template
*Lagunitas - Disponibilidad ICMP - sonda externa* tiene las mismas mediciones y alertas que el de
producción, así que dashboard, widget, reporte y dependencias lo tratan igual.

Los contenedores de `lagunitas_net` sí son reales (se apagan de verdad). **En producción (Linux)
esto no pasa** y el AP usa el perfil `icmp` normal.

---

## Instalación desde cero

Solo si la Mac es nueva o se borró el proyecto.

1. Herramientas:

   ```bash
   brew install colima docker docker-compose git
   ```

2. Clonar el repositorio (privado, `ecoranti/zabbix-lagunitas`) y pararse en la rama de trabajo:

   ```bash
   git clone https://github.com/ecoranti/zabbix-lagunitas.git ~/zabbix-lab
   cd ~/zabbix-lab && git checkout feature/produccion-v2
   ```

3. Secretos: copiar la plantilla y completar **todas** las claves.

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

4. Arrancar:

   ```bash
   ./start.sh
   ```

5. Primer ingreso a <http://localhost:8090> con `Admin` / `zabbix` (clave de fábrica de una base
   nueva): cambiarla en *User settings → Profile → Change password* por la misma que se puso en
   `ZABBIX_PASSWORD` de `.env`. El provisionador entra con esa clave.

6. Aprovisionar y verificar:

   ```bash
   bin/lagunitas aprovisionar
   bin/lagunitas verificar
   ```

   La primera vez `bin/lagunitas` crea solo el entorno Python (`.venv`).

7. Opcional: arranque automático al iniciar sesión (sección *Arranque automático*).

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
bin/lagunitas verificar             # hosts, ítems no soportados, dashboard, etc.
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

| Si cambié… | Correr |
|---|---|
| Un equipo en el inventario (alta, baja, IP, padre, estado) | `aprovisionar` y `lab levantar` |
| Un template (ítems, triggers, umbrales) | `aprovisionar --solo templates` |
| El dashboard | `aprovisionar --solo dashboard` |
| CSS / PHP / JS de un módulo | Nada: recargar el navegador con **Cmd + Shift + R** |
| `docker-compose.yml` o `.env` del stack | `docker compose up -d` |

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
| *Administration → General → Modules* | Módulos propios (**Scan directory** para ver la versión nueva) |

**Selector de tiempo:** los gráficos usan el rango de arriba a la derecha. Si se arrastra el mouse
sobre un gráfico, queda fijo en ese rango (y se guarda en el usuario). Si los gráficos aparecen
vacíos o con fechas viejas, elegir *Last 6 hours* (u otro rango relativo).

**PDF de los reportes:** usar el botón *Imprimir / PDF*. En Chrome sale con pie propio
("Página X de Y"); en Safari, desmarcar *Imprimir encabezados y pies de página*.

---

## Frecuencia de actualización

| Qué | Frecuencia |
|---|---|
| Mediciones de todos los equipos (ICMP, SNMP, API UniFi, sonda) | 10 s (macro `{$LAGUNITAS.INTERVALO}`) |
| Disponibilidad 24 h / 7 días | 1 min |
| Datos estáticos (modelo, firmware, SSID, serie) | 1 h |
| Descubrimiento de interfaces y estaciones | 10 min / 1 h |
| Widgets de dashboards y pantallas del frontend | 10 s |

Para medir más lento (por ejemplo si la Mac va cargada): *Administration → Macros* →
`{$LAGUNITAS.INTERVALO}` = `30s`. No hace falta reaprovisionar. La sonda tiene su propio
intervalo: `bin/lagunitas lab sonda --intervalo 30`.

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

`caida` detiene también a los equipos aguas abajo, porque en la red real pierden el camino. Así
se ve el efecto de las dependencias: **una sola alerta** por la caída troncal. La alerta aparece
a los ~90 s (`{$ICMP.CAIDA.PERIODO}`).

Qué mirar: *Estado de la red* (panal y mapa en rojo), *Equipos* (el equipo "Caído" y sus
dependientes "Sin servicio"), *Monitoring → Problems* y, después, el reporte.

### Fallas de radio y energía (SNMP simulado)

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

Ejemplos: `bin/lagunitas lab escenario Walter senal-debil`,
`bin/lagunitas lab escenario Gateway_Mikrotik sin-internet`. Las alertas basadas en promedios
aparecen entre 1 y 15 minutos después. **Siempre volver a `normal` al terminar.**

Los valores simulados están en `lab/snmpsim/data/*.snmprec` (formato `OID|tipo|valor`; los
valores numéricos oscilan para que los gráficos se vean realistas).

### AP real

- Apagar el AP (o desenchufarlo): a los ~90 s aparece *sin respuesta (ICMP)*; la de UniFi queda
  suprimida por dependencia.
- Apagar UniFi OS Server: aparece *controlador UniFi no accesible* a los 3 min.
- Detener la sonda: aparece *la sonda ICMP no envía datos* a los 3 min.

---

## AP UniFi real

| Dato | Valor |
|---|---|
| AP | U7 Pro Wall, `192.168.1.113` |
| Controlador | UniFi OS Server en esta Mac, `192.168.1.81`, puerto HTTPS `11443` |
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

```bash
scripts/backup.sh                                        # a ./backups (base comprimida + export YAML)
scripts/restore.sh backups/zabbix_AAAAMMDD_HHMM.sql.gz   # ¡reemplaza TODO lo actual!
bin/lagunitas exportar                                   # templates y mapa a zabbix/export/
```

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
| `docs/*.md` | Documentación (fuente); `docs/*.docx` se generan desde acá |

### Git

```bash
git status                     # revisar SIEMPRE qué se va a subir
git add <archivos concretos>   # nunca "git add -A" a ciegas
git commit -m "mensaje"
git push                       # rama feature/produccion-v2 → PR #1
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
| El frontend no abre en <http://localhost:8090> | Stack caído o arrancando | `docker compose ps`; `docker compose logs --tail 50 zabbix-web zabbix-server`; `./start.sh` |
| Chrome: `ERR_ADDRESS_UNREACHABLE` con `gala.local` | macOS bloquea a Chrome la red local | Usar `http://localhost:8090`, o *Ajustes del Sistema → Privacidad y seguridad → Red local* → activar Chrome y reiniciarlo |
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
| Error de YAML al aprovisionar | Sintaxis del inventario (dos puntos sin comillas, sangría) | `bin/lagunitas validar` indica la línea |
| La Mac va lenta | 30+ contenedores y mediciones cada 10 s | Subir `{$LAGUNITAS.INTERVALO}` a `30s`; `./start.sh down` cuando no se use |

### Empezar de cero (borra la configuración y el historial)

Solo si la base quedó inservible y no hay backup que sirva:

```bash
./start.sh down
mv mysql_data mysql_data.viejo        # en lugar de borrar, por las dudas
./start.sh
```

Luego seguir los pasos 5 y 6 de *Instalación desde cero* (cambiar la clave de fábrica de `Admin`
y aprovisionar). Los datos viejos quedan en `mysql_data.viejo` hasta que se borren a mano.
