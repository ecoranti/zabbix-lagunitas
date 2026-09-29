# Guía de implementación — Monitoreo de la Red Las Lagunitas

**Versión 2.0** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas (Alpa Corral, Córdoba)

Esta guía explica cómo poner en marcha el sistema de monitoreo desde cero, tanto en el
**laboratorio** (Mac con Docker/Colima y la red simulada) como en el **servidor de producción**
que monitoreará la red real. Reemplaza a la *Guía de despliegue* v1 (`docs/referencia/`), que
documentaba la construcción paso a paso con scripts sueltos; en la v2 toda la configuración se
genera automáticamente desde el inventario de la red.

---

## 1. Arquitectura

```
                         ┌──────────────── Servidor de monitoreo ────────────────┐
  Operadores ── HTTPS ──▶│ Caddy ──▶ zabbix-web (frontend + módulos Lagunitas)    │
  (navegador)            │                     │                                   │
                         │               zabbix-server ──▶ MySQL                   │
                         │                 │   │   └── zabbix-agent (auto-monitoreo)│
                         └─────────────────┼───┼───────────────────────────────────┘
                              ICMP (fping)│   │SNMP v2c / HTTPS API
                                          ▼   ▼
             Mikrotik (gateway) ── torres ── nodos ── hogares / escuela  (red WISP)
```

| Capa | Laboratorio | Producción |
|---|---|---|
| Host | Mac M3 con Colima | Servidor Linux (Ubuntu LTS) en el nodo UNRC |
| Stack | `docker-compose.yml` (raíz) | `deploy/produccion/docker-compose.yml` |
| Equipos | Contenedores Alpine en `lagunitas_net` (10.50.0.0/24) | Equipos reales alcanzados por ruteo/VPN |
| Acceso web | `http://localhost:8090` | `https://<ZBX_DOMAIN>` (Caddy) |
| Inventario | `config/inventory.lab.yaml` | `config/inventory.produccion.yaml` |

**Métodos de recolección**

- **ICMP** (template *Lagunitas - Disponibilidad ICMP*): el Zabbix server hace ping a cada
  equipo cada 30 s. Funciona con cualquier equipo con IP, incluidos los routers AirCube de los
  hogares, que no tienen SNMP ni API documentada.
- **SNMP v2c** (templates oficiales *Ubiquiti AirOS by SNMP* y *Mikrotik by SNMP*): para los
  equipos airMAX (PowerBeam, LiteBeam, NanoLoco) y el router Mikrotik. Aporta señal, ruido,
  CCQ, tráfico por interfaz, CPU y memoria.
- **API REST de UniFi** (template *Lagunitas - AP UniFi por API*): para access points UniFi
  administrados por UniFi Network (caso del AP real del laboratorio).

**Topología y dependencias.** Cada equipo declara en el inventario su *padre* (el equipo del que
depende su conectividad). El provisionador convierte esa relación en **dependencias entre
triggers**: si cae una torre, Zabbix alerta solo por la torre y suprime las alertas de todos los
nodos y hogares aguas abajo. El widget los muestra como **"Sin servicio"** y el reporte los
contabiliza en la *disponibilidad del servicio*.

---

## 2. Requisitos

### Servidor de producción

| Recurso | Mínimo | Recomendado |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disco | 40 GB SSD | 80 GB SSD (historial 90 días, tendencias 1 año) |
| SO | Ubuntu Server 22.04/24.04 LTS | |
| Energía | Con UPS | UPS + auto-arranque de servicios |

Software: Docker Engine 24+ con el plugin Compose v2, Git, Python 3.10+ (`python3-venv`).

### Red

- Desde el servidor debe poder hacerse **ping** a la IP de gestión de cada equipo
  (verificar reglas del firewall del Mikrotik y de la VPN).
- **SNMP v2c (UDP/161)** permitido desde la IP del servidor hacia los equipos airMAX y Mikrotik.
- Para el AP UniFi: acceso HTTPS al controlador UniFi (puerto de la API de integración).
- Puertos entrantes al servidor: **443/TCP** (frontend). **10051/TCP** solo si se usan agentes
  activos o un Zabbix proxy remoto.

### Laboratorio

macOS con [Colima](https://github.com/abiosoft/colima) (`brew install colima docker docker-compose`),
Python 3.10+ y al menos 3 GB de RAM libres.

> **Limitación conocida del laboratorio:** la red de Colima responde ICMP por *cualquier* IP
> externa (incluso inexistentes). Por eso en el LAB el AP real **no** usa el perfil `icmp`: su
> disponibilidad se toma del estado que informa la API de UniFi. Los contenedores de
> `lagunitas_net` sí son reales. En producción (Linux) el ICMP es fiel.

---

## 3. Instalación del laboratorio (Mac)

```bash
git clone https://github.com/ecoranti/zabbix-lagunitas.git ~/zabbix-lab
cd ~/zabbix-lab
cp .env.example .env
```

Editar `.env`: contraseñas de MySQL, y `UNIFI_API_KEY` si se va a monitorear el AP real
(UniFi Network → *Integrations* → *Create API Key*).

```bash
./start.sh                   # inicia Colima, crea lagunitas_net, levanta el stack y la red simulada
bin/lagunitas aprovisionar   # la primera vez crea el entorno virtual de Python automáticamente
bin/lagunitas verificar
```

Si el laboratorio venía de la **versión 1** (scripts sueltos), la primera vez usar:

```bash
scripts/backup.sh                          # respaldo previo
bin/lagunitas aprovisionar --migrar-v1     # borra hosts/mapa/dashboard v1 y recrea todo
```

Abrir <http://localhost:8090> (usuario `Admin`) → *Dashboards → Las Lagunitas - Centro de monitoreo*.

Opcional: arranque automático al iniciar sesión (ver `scripts/launchd/ar.lagunitas.zabbix-lab.plist`).

---

## 4. Instalación en producción

### 4.1 Preparar el servidor

```bash
sudo apt update && sudo apt install -y ca-certificates curl git python3-venv
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER        # cerrar sesión y volver a entrar
sudo timedatectl set-timezone America/Argentina/Cordoba
sudo ufw allow OpenSSH && sudo ufw allow 443/tcp && sudo ufw allow 80/tcp && sudo ufw enable
```

### 4.2 Obtener el proyecto y configurar secretos

```bash
sudo mkdir -p /opt/zabbix-lagunitas && sudo chown $USER /opt/zabbix-lagunitas
git clone https://github.com/ecoranti/zabbix-lagunitas.git /opt/zabbix-lagunitas
cd /opt/zabbix-lagunitas
cp deploy/produccion/.env.example deploy/produccion/.env
cp .env.example .env
```

- `deploy/produccion/.env`: contraseñas de MySQL (generarlas con `openssl rand -base64 24`),
  `ZBX_DOMAIN` (nombre o IP con que se accederá) y `CADDY_TLS` (`internal` para uso en LAN/VPN,
  o un email para certificado Let's Encrypt si hay dominio público).
- `.env` (usado por el provisionador): `ZABBIX_URL=https://<ZBX_DOMAIN>/api_jsonrpc.php`,
  `LAGUNITAS_INVENTORY=config/inventory.produccion.yaml`, `SNMP_COMMUNITY`, y opcionalmente
  `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`. Con `CADDY_TLS=internal` agregar
  `ZABBIX_VERIFY_TLS=false` (certificado propio).

```bash
chmod 600 .env deploy/produccion/.env
```

### 4.3 Levantar el stack

```bash
cd deploy/produccion
docker compose up -d
docker compose ps          # los 5 servicios en "running" / "healthy"
```

La primera vez MySQL tarda 1–2 minutos en crear el esquema.

### 4.4 Primer acceso y endurecimiento

1. Entrar a `https://<ZBX_DOMAIN>` con `Admin` / `zabbix` y **cambiar la contraseña** de inmediato
   (*User settings → Profile → Change password*).
2. Crear un usuario de servicio para el provisionador (*Users → Users → Create user*), rol
   *Super admin role*, y generarle un **API token** (*Users → API tokens*). Guardarlo en `.env`
   como `ZABBIX_API_TOKEN` y borrar `ZABBIX_USER`/`ZABBIX_PASSWORD`.
3. *Administration → General → GUI*: zona horaria por defecto `America/Argentina/Cordoba`.

### 4.5 Preparar los equipos de la red

**Ubiquiti airMAX (PowerBeam, LiteBeam, NanoLoco):** en la interfaz de airOS → *Services* →
*SNMP Agent*: habilitar, definir *SNMP Community* (la misma que `SNMP_COMMUNITY`) y el contacto /
ubicación. Guardar y aplicar.

**Mikrotik RB750/RB950:**

```
/snmp community add name=<COMUNIDAD> addresses=<IP_SERVIDOR>/32 read-access=yes write-access=no
/snmp set enabled=yes contact="Red Las Lagunitas" location="Torre Walter"
/ip firewall filter add chain=input protocol=udp dst-port=161 src-address=<IP_SERVIDOR> action=accept place-before=0 comment="Zabbix SNMP"
/ip firewall filter add chain=input protocol=icmp src-address=<IP_SERVIDOR> action=accept place-before=0 comment="Zabbix ICMP"
```

**Routers AirCube:** solo requieren responder ping en su IP de gestión.

Comprobar desde el servidor:

```bash
docker compose exec zabbix-server fping -c3 <IP_EQUIPO>
docker compose exec zabbix-server snmpget -v2c -c <COMUNIDAD> <IP_EQUIPO> 1.3.6.1.2.1.1.5.0
```

### 4.6 Completar el inventario de producción

`config/inventory.produccion.yaml` parte de la misma topología que el laboratorio. Para cada
elemento completar:

| Campo | Qué poner |
|---|---|
| `ip` | IP de gestión real del equipo (reemplazar las marcadas `COMPLETAR`). |
| `estado` | `operativo` si el tramo está en servicio; `en_proceso` / `sin_configurar` si no (se crea deshabilitado y se ve en gris en el mapa). |
| `perfiles` | `[icmp]` para todos; agregar `airos_snmp` en equipos airMAX y `mikrotik_snmp` en el Mikrotik. |
| `padre` | Equipo del que depende (define dependencias de alertas y el camino en el mapa). |
| `equipo` | Hardware instalado (se guarda en el inventario de Zabbix). |

Validar el archivo sin tocar Zabbix:

```bash
bin/lagunitas -i config/inventory.produccion.yaml validar
```

### 4.7 Aprovisionar

```bash
bin/lagunitas aprovisionar
```

Pasos que ejecuta (se pueden correr por separado con `--solo <paso>`):

| Paso | Qué crea/actualiza |
|---|---|
| `templates` | Templates propios, valuemaps, triggers y dashboards de detalle |
| `hosts` | Grupos por rol, hosts, interfaces, tags, inventario y macros (secretas) |
| `dependencias` | Dependencias padre → hijo de los triggers de caída |
| `servidor` | Auto-monitoreo del Zabbix server vía el contenedor `zabbix-agent` |
| `mapa` | Mapa *Las Lagunitas - Topología* con leyenda y enlaces por estado |
| `servicios` | Árbol de servicios y SLA mensual (objetivo 99,5 %) |
| `modulos` | Registra y habilita los módulos del frontend |
| `dashboard` | Dashboard *Las Lagunitas - Centro de monitoreo* |
| `alertas` | Grupo de operadores, acción de notificación y Telegram (si está configurado) |

El proceso es **idempotente**: puede ejecutarse las veces que haga falta; actualiza lo existente
sin duplicar.

### 4.8 Verificar

```bash
bin/lagunitas verificar
```

Lista hosts faltantes, items no soportados y problemas abiertos. En el frontend comprobar:

- [ ] *Dashboards → Las Lagunitas - Centro de monitoreo* → página **Equipos**: todos los equipos
      operativos "En línea" y los tramos no habilitados como "No monitoreado".
- [ ] Mapa de topología con enlaces verdes (operativos), discontinuos (en proceso) y punteados
      (sin configurar).
- [ ] *Reports → Disponibilidad de la red* genera el reporte.
- [ ] *Services → SLA report* muestra el SLA *Las Lagunitas - Disponibilidad mensual*.
- [ ] Prueba de alarma: desconectar (o bloquear el ping de) un equipo de borde y confirmar la
      alerta y su recuperación.

### 4.9 Notificaciones por Telegram

1. Crear un bot con **@BotFather** (`/newbot`) y copiar el token.
2. Agregar el bot a un grupo de operadores y obtener el `chat_id` (por ejemplo con
   `https://api.telegram.org/bot<TOKEN>/getUpdates` después de escribir en el grupo).
3. Completar `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env` y ejecutar
   `bin/lagunitas aprovisionar --solo alertas`.
4. Probar desde *Alerts → Media types → Telegram → Test*.

La acción *Las Lagunitas - Notificar caídas* avisa problemas de severidad **Average o mayor**,
envía un recordatorio a los 30 minutos si siguen abiertos y avisa la recuperación.

### 4.10 Backups

```bash
COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion /opt/zabbix-lagunitas/scripts/backup.sh /var/backups/zabbix
```

Programarlo diariamente con `crontab -e`:

```
0 3 * * * COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion /opt/zabbix-lagunitas/scripts/backup.sh /var/backups/zabbix >> /var/log/zabbix-backup.log 2>&1
```

Copiar periódicamente `/var/backups/zabbix` fuera del servidor. Restauración: `scripts/restore.sh`.

### 4.11 (Opcional) Zabbix proxy en Las Lagunitas

Si el enlace entre el servidor (UNRC) y la red comunitaria es inestable, instalar un **Zabbix
proxy** dentro de la red (por ejemplo en una Raspberry Pi junto al Mikrotik). El proxy hace los
chequeos localmente y guarda los datos si se corta el enlace, reenviándolos al volver. En ese
caso los hosts se asignan al proxy (*Monitored by proxy*) y el servidor debe aceptar conexiones
en 10051/TCP.

---

## 5. Checklist de puesta en producción

- [ ] Contraseña de `Admin` cambiada; provisionador con API token.
- [ ] `.env` con permisos 600; secretos fuera del repositorio.
- [ ] HTTPS operativo (Caddy) y HTTP redirigido.
- [ ] Inventario de producción con IPs, padres y perfiles verificados.
- [ ] Todos los equipos operativos "En línea"; sin items no soportados inesperados.
- [ ] Prueba de caída y recuperación realizada y documentada.
- [ ] Notificaciones probadas (Telegram o email).
- [ ] Backup diario programado y **una restauración de prueba** realizada.
- [ ] Servidor con UPS y Docker habilitado al arranque (`sudo systemctl enable docker`).

---

## 6. Decisiones de diseño

- **Configuración como código.** Evita configuraciones manuales imposibles de reproducir: el
  inventario YAML describe la red y el provisionador la refleja en Zabbix.
- **ICMP como base universal + SNMP donde el equipo lo permite.** Los AirCube y los controladores
  de carga Epever LS-E no exponen métricas, pero todo equipo con IP puede responder ping.
- **Dependencias entre triggers.** En una red en árbol, una caída troncal dispara decenas de
  alertas; las dependencias reducen el ruido a la causa raíz.
- **Dos disponibilidades.** La *propia* mide al equipo; la *de servicio* mide lo que vivió el
  hogar. Ambas son necesarias para gestionar la red y para rendir cuentas a la comunidad.
- **Módulos propios del frontend.** Presentan la información con el lenguaje de la red
  (torres, nodos, hogares) para operadores sin formación específica en Zabbix.

---

## 7. Referencia del CLI

```
bin/lagunitas [-i INVENTARIO] aprovisionar [--solo PASO ...] [--migrar-v1]
bin/lagunitas validar                   # valida el inventario sin tocar Zabbix
bin/lagunitas verificar
bin/lagunitas exportar                  # templates y mapa en zabbix/export/*.yaml
bin/lagunitas lab levantar|apagar|estado
bin/lagunitas lab caida <equipo>        # simula la caída (docker stop)
bin/lagunitas lab recuperar <equipo>    # docker start
```
