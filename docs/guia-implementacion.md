# Guía de implementación — Monitoreo de la Red Las Lagunitas

**Versión 2.2** · Zabbix 7.0 LTS · Red Comunitaria y Científica Las Lagunitas (Alpa Corral, Córdoba)

Esta guía explica cómo instalar y poner en marcha el sistema de monitoreo en el **servidor de
producción** que supervisa la red real. La incorporación de cada equipo (radios, routers, access
points) se detalla en la [Guía de integración de equipos](guia-integracion-equipos.md) y la
operación diaria en el [Manual de administración](manual-administracion.md).

Toda la configuración de Zabbix se genera automáticamente desde el **inventario de la red**
(`config/inventory.produccion.yaml`) con la herramienta `bin/lagunitas`.

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

| Componente | Descripción |
|---|---|
| Servidor | Linux (Ubuntu Server LTS) en el nodo UNRC, con alimentación estable |
| Stack | `deploy/produccion/docker-compose.yml`: MySQL, Zabbix server, frontend, agente y Caddy (HTTPS) |
| Acceso web | `https://<ZBX_DOMAIN>` |
| Equipos | Equipos reales de la red, alcanzados por ruteo o VPN desde el servidor |
| Configuración | `config/inventory.produccion.yaml` + `bin/lagunitas aprovisionar` |

**Métodos de recolección**

- **ICMP** (template *Lagunitas - Disponibilidad ICMP*): el Zabbix server hace ping a cada
  equipo cada 30 s. Funciona con cualquier equipo con IP, incluidos los routers airCube de los
  hogares, que no tienen SNMP ni API documentada.
- **SNMP v2c** (templates *Lagunitas - Ubiquiti airMAX por SNMP* y *Lagunitas - Mikrotik por
  SNMP*): radios airMAX (PowerBeam, LiteBeam, NanoStation, NanoLoco) y el router Mikrotik. Aportan
  señal, ruido, SNR, CCQ, capacidad airMAX, estaciones asociadas, interfaces, voltaje de batería,
  clientes DHCP, estado del enlace a Internet, CPU y memoria.
- **API REST de UniFi** (template *Lagunitas - AP UniFi por API*): access points UniFi
  administrados por UniFi Network.

**Topología y dependencias.** Cada equipo declara en el inventario su *padre* (el equipo del que
depende su conectividad). El provisionador convierte esa relación en **dependencias entre
triggers**: si cae una torre, Zabbix alerta solo por la torre y suprime las alertas de todos los
nodos y hogares aguas abajo. El widget los muestra como **"Sin servicio"** y el reporte los
contabiliza en la *disponibilidad del servicio*.

---

## 2. Requisitos

### Servidor

| Recurso | Mínimo | Recomendado |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disco | 40 GB SSD | 80 GB SSD (historial 90 días, tendencias 1 año) |
| SO | Ubuntu Server 22.04/24.04 LTS | |
| Energía | Con UPS | UPS + arranque automático de servicios |

Software: Docker Engine 24+ con el plugin Compose v2, Git y Python 3.10+ (`python3-venv`).

### Red

- Desde el servidor debe poder hacerse **ping** a la IP de gestión de cada equipo (verificar las
  reglas del firewall del Mikrotik y de la VPN).
- **SNMP v2c (UDP/161)** permitido desde la IP del servidor hacia los equipos airMAX y Mikrotik.
- Para APs UniFi: acceso HTTPS al controlador UniFi (puerto de la API de integración).
- Puertos entrantes al servidor: **443/TCP** y **80/TCP** (frontend y certificado).
  **10051/TCP** solo si se usa un Zabbix proxy remoto (§3.11).

---

## 3. Instalación

### 3.1 Preparar el servidor

```bash
sudo apt update && sudo apt install -y ca-certificates curl git python3-venv
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER        # cerrar sesión y volver a entrar
sudo systemctl enable docker
sudo timedatectl set-timezone America/Argentina/Cordoba
sudo ufw allow OpenSSH && sudo ufw allow 443/tcp && sudo ufw allow 80/tcp && sudo ufw enable
```

### 3.2 Obtener el proyecto y configurar secretos

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
- `.env` (usado por `bin/lagunitas`):
  - `ZABBIX_URL=https://<ZBX_DOMAIN>/api_jsonrpc.php`
  - `LAGUNITAS_INVENTORY=config/inventory.produccion.yaml`
  - `SNMP_COMMUNITY` (comunidad SNMP de los equipos; no usar `public`)
  - `UNIFI_API_KEY` si hay APs UniFi
  - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` para notificaciones (§3.9)
  - con `CADDY_TLS=internal`, agregar `ZABBIX_VERIFY_TLS=false` (certificado propio)

```bash
chmod 600 .env deploy/produccion/.env
```

### 3.3 Levantar el stack

```bash
cd /opt/zabbix-lagunitas/deploy/produccion
docker compose up -d
docker compose ps          # los 5 servicios en "running" / "healthy"
```

La primera vez MySQL tarda 1–2 minutos en crear el esquema.

### 3.4 Primer acceso y endurecimiento

1. Entrar a `https://<ZBX_DOMAIN>` con el usuario `Admin` y la contraseña por defecto de Zabbix
   (`zabbix`) y **cambiarla de inmediato** (*User settings → Profile → Change password*).
2. Crear un usuario de servicio para el provisionador (*Users → Users → Create user*), rol
   *Super admin role*, y generarle un **API token** (*Users → API tokens*). Guardarlo en `.env`
   como `ZABBIX_API_TOKEN` y dejar vacíos `ZABBIX_USER` y `ZABBIX_PASSWORD`.
3. *Administration → General → GUI*: zona horaria por defecto `America/Argentina/Cordoba`.

### 3.5 Preparar los equipos de la red

Cada equipo debe responder ping desde el servidor y, según su tipo, tener SNMP habilitado o una
API key creada. El paso a paso por tipo de equipo (radios airMAX, Mikrotik, airCube, UniFi) está
en la [Guía de integración de equipos](guia-integracion-equipos.md). Antes de cargar cada equipo,
comprobarlo desde el servidor:

```bash
cd /opt/zabbix-lagunitas
bin/lagunitas probar-snmp <IP_EQUIPO>          # radios airMAX y Mikrotik
bin/lagunitas unifi-ids <IP_CONTROLADOR> <PUERTO>   # APs UniFi
```

### 3.6 Completar el inventario

`config/inventory.produccion.yaml` contiene la topología relevada en campo (gateway, 4 torres,
9 nodos, hogares e instituciones). Para cada elemento completar:

| Campo | Qué poner |
|---|---|
| `ip` | IP de gestión real del equipo (reemplazar las marcadas `COMPLETAR`). |
| `estado` | `operativo` si el tramo está en servicio; `en_proceso` / `sin_configurar` si no (se crea deshabilitado y se ve en gris en el mapa). |
| `perfiles` | `[icmp]` para todos; agregar `airos_snmp` en radios airMAX con SNMP habilitado y `mikrotik_snmp` en el Mikrotik. |
| `funcion` | `ap`, `sm`, `ptp` o `router`. |
| `modelo` | Modelo exacto (se guarda en el inventario de Zabbix). |
| `padre` | Equipo del que depende (define dependencias de alertas y el camino en el mapa). |
| `dispositivos` | Los demás equipos con IP del sitio (AP que retransmite, router del hogar), cada uno con su host, IP, función, modelo y perfiles. |
| `equipo` | Descripción del hardware del sitio (se guarda en el inventario de Zabbix). |
| `macros` | (opcional) Umbrales propios del equipo, por ejemplo para enlaces largos. |

Validar el archivo sin tocar Zabbix:

```bash
bin/lagunitas validar
```

### 3.7 Aprovisionar

```bash
bin/lagunitas aprovisionar
```

Pasos que ejecuta (se pueden correr por separado con `--solo <paso>`):

| Paso | Qué crea/actualiza |
|---|---|
| `templates` | Templates propios (ICMP, airMAX por SNMP, Mikrotik por SNMP, UniFi por API), valuemaps, triggers, descubrimientos y dashboards de detalle |
| `hosts` | Grupos por rol, hosts, interfaces, tags, inventario y macros (secretas) |
| `dependencias` | Dependencias padre → hijo de los triggers de caída; las alertas "sin datos SNMP/API" dependen de la caída del propio equipo |
| `servidor` | Auto-monitoreo del Zabbix server vía el contenedor `zabbix-agent` |
| `mapa` | Mapa *Las Lagunitas - Topología* con leyenda y enlaces por estado |
| `servicios` | Árbol de servicios y SLA mensual (objetivo 99,5 %) |
| `modulos` | Registra y habilita los módulos del frontend (widget y reporte) |
| `dashboard` | Dashboard *Las Lagunitas - Centro de monitoreo* |
| `alertas` | Grupo de operadores, acción de notificación y Telegram (si está configurado) |

El proceso es **idempotente**: puede ejecutarse las veces que haga falta; actualiza lo existente
sin duplicar. Los cambios hechos a mano en Zabbix sobre estos objetos se pisan en el siguiente
aprovisionamiento: toda modificación permanente se hace en el inventario o en el código.

### 3.8 Verificar

```bash
bin/lagunitas verificar
```

Lista hosts faltantes, ítems no soportados y problemas abiertos. En el frontend comprobar:

- [ ] *Dashboards → Las Lagunitas - Centro de monitoreo*: todos los equipos operativos
      "En línea" y los tramos no habilitados como "No monitoreado".
- [ ] Mapa de topología con enlaces verdes (operativos), discontinuos (en proceso) y punteados
      (sin configurar).
- [ ] En el detalle de cada radio y del Mikrotik aparecen sus pestañas específicas con datos.
- [ ] *Reports → Disponibilidad de la red* genera el reporte y el detalle técnico.
- [ ] *Services → SLA report* muestra el SLA *Las Lagunitas - Disponibilidad mensual*.
- [ ] Prueba de alarma controlada: desconectar (o bloquear el ping de) un equipo de borde y
      confirmar la alerta y su recuperación.

### 3.9 Notificaciones por Telegram

1. Crear un bot con **@BotFather** (`/newbot`) y copiar el token.
2. Agregar el bot a un grupo de operadores y obtener el `chat_id` (por ejemplo con
   `https://api.telegram.org/bot<TOKEN>/getUpdates` después de escribir en el grupo).
3. Completar `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env` y ejecutar
   `bin/lagunitas aprovisionar --solo alertas`.
4. Probar desde *Alerts → Media types → Telegram → Test*.

La acción *Las Lagunitas - Notificar caídas* avisa problemas de severidad **Average o mayor**,
envía un recordatorio a los 30 minutos si siguen abiertos y avisa la recuperación.

### 3.10 Backups

```bash
COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion /opt/zabbix-lagunitas/scripts/backup.sh /var/backups/zabbix
```

Programarlo diariamente con `crontab -e`:

```
0 3 * * * COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion /opt/zabbix-lagunitas/scripts/backup.sh /var/backups/zabbix >> /var/log/zabbix-backup.log 2>&1
```

Copiar periódicamente `/var/backups/zabbix` fuera del servidor. Restauración:
`COMPOSE_DIR=/opt/zabbix-lagunitas/deploy/produccion scripts/restore.sh <archivo>`.

### 3.11 (Opcional) Zabbix proxy en Las Lagunitas

Si el enlace entre el servidor (UNRC) y la red comunitaria es inestable, instalar un **Zabbix
proxy** dentro de la red (por ejemplo en una Raspberry Pi junto al Mikrotik). El proxy hace los
chequeos localmente y guarda los datos si se corta el enlace, reenviándolos al volver. En ese
caso los hosts se asignan al proxy (*Monitored by proxy*) y el servidor debe aceptar conexiones
en 10051/TCP.

---

## 4. Checklist de puesta en producción

- [ ] Contraseña de `Admin` cambiada; provisionador con API token.
- [ ] `.env` y `deploy/produccion/.env` con permisos 600; secretos fuera del repositorio.
- [ ] HTTPS operativo (Caddy) y HTTP redirigido.
- [ ] Inventario con IPs, padres, perfiles, modelos y dispositivos verificados (`validar`).
- [ ] Cada equipo SNMP probado con `bin/lagunitas probar-snmp` antes de aprovisionar.
- [ ] Todos los equipos operativos "En línea"; sin ítems no soportados inesperados.
- [ ] Prueba de caída y recuperación realizada y documentada.
- [ ] Notificaciones probadas (Telegram o email).
- [ ] Backup diario programado y **una restauración de prueba** realizada.
- [ ] Servidor con UPS y Docker habilitado al arranque.

---

## 5. Decisiones de diseño

- **Configuración como código.** Evita configuraciones manuales imposibles de reproducir: el
  inventario YAML describe la red y el provisionador la refleja en Zabbix.
- **ICMP como base universal + SNMP donde el equipo lo permite.** Los airCube y los controladores
  de carga Epever LS-E no exponen métricas, pero todo equipo con IP puede responder ping.
- **Templates propios para airMAX y Mikrotik.** Los templates oficiales de Zabbix no incluyen las
  métricas de radio de airMAX (señal, CCQ, capacidad) y duplican los chequeos ICMP.
- **Dependencias entre triggers.** En una red en árbol, una caída troncal dispara decenas de
  alertas; las dependencias reducen el ruido a la causa raíz.
- **Dos disponibilidades.** La *propia* mide al equipo; la *de servicio* mide lo que vivió el
  hogar. Ambas son necesarias para gestionar la red y para rendir cuentas a la comunidad.
- **Módulos propios del frontend.** Presentan la información con el lenguaje de la red (torres,
  nodos, hogares) para operadores sin formación específica en Zabbix.

---

## 6. Referencia del CLI

```
bin/lagunitas aprovisionar [--solo PASO ...]      # crea/actualiza la configuración en Zabbix
bin/lagunitas validar                             # valida el inventario sin tocar Zabbix
bin/lagunitas verificar                           # chequeo de salud
bin/lagunitas probar-snmp <ip> [--comunidad X]    # diagnóstico SNMP antes de integrar
bin/lagunitas unifi-ids <ip> [puerto]             # IDs de site y AP de un controlador UniFi
bin/lagunitas exportar                            # templates y mapa en zabbix/export/*.yaml
```
