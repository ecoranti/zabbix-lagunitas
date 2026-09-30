# Laboratorio de pruebas — Monitoreo de la Red Las Lagunitas

Este documento describe el **entorno de laboratorio** usado durante el desarrollo y la validación
del sistema (Práctica Profesional Supervisada). **No forma parte del despliegue productivo**: las
guías de [implementación](guia-implementacion.md), [integración de equipos](guia-integracion-equipos.md)
y [administración](manual-administracion.md) son exclusivamente para producción.

El laboratorio replica la topología real de la red con contenedores Docker y permite probar
templates, alertas, dependencias, dashboards y reportes sin acceso a los equipos de campo.

---

## 1. Componentes

| Componente | Detalle |
|---|---|
| Host | Mac (Apple Silicon) con [Colima](https://github.com/abiosoft/colima) como motor de Docker |
| Stack | `docker-compose.yml` de la raíz del repositorio (sin Caddy, frontend en `http://localhost:8090`) |
| Red simulada | Red Docker `lagunitas_net` (10.50.0.0/24): un contenedor por equipo operativo del inventario |
| Inventario | `config/inventory.lab.yaml` (misma topología que producción, IPs 10.50.0.x) |
| Agentes SNMP simulados | `lab/snmpsim/`: responden con los OIDs reales de Ubiquiti airMAX (AP y estación) y Mikrotik |
| Equipo real | AP UniFi U7 Pro Wall (192.168.1.113), monitoreado por la API de UniFi OS Server, que corre en la misma Mac (192.168.1.81, puerto HTTPS 11443) |

Cada contenedor simulado responde ICMP en su IP fija. Los equipos con perfil `airos_snmp` o
`mikrotik_snmp` corren un agente SNMP simulado (radio AP, radio estación o router Mikrotik); el
resto, un contenedor Alpine mínimo. Los contenedores tienen `restart: unless-stopped` y no usan
`--rm`, por lo que sobreviven a reinicios.

> **Limitación de Colima:** su red responde ICMP por *cualquier* IP externa (incluso inexistentes):
> desde el contenedor del Zabbix server, `192.168.1.250` "responde" aunque no exista, y la latencia
> al AP da ~0,8 ms cuando la real es ~4 ms. Por eso el AP real usa el perfil **`icmp_sonda`**: el
> ping lo hace la Mac y lo envía a Zabbix (ver "Sonda ICMP"). Los contenedores de `lagunitas_net`
> sí son reales. En producción (Linux) no existe esta limitación y el AP usa el perfil `icmp`.

---

## 2. Instalación

Requisitos: macOS con Colima (`brew install colima docker docker-compose`), Python 3.10+ y al menos
3 GB de RAM libres.

```bash
git clone https://github.com/ecoranti/zabbix-lagunitas.git ~/zabbix-lab
cd ~/zabbix-lab
cp .env.example .env        # completar contraseñas, UNIFI_API_KEY y SNMP_COMMUNITY=public
./start.sh                  # Colima + red lagunitas_net + stack Zabbix + equipos simulados
bin/lagunitas aprovisionar
bin/lagunitas verificar
```

Frontend: <http://localhost:8090> → *Dashboards → Las Lagunitas - Centro de monitoreo*.

- `./start.sh down` apaga los equipos simulados y el stack conservando los datos.
- Arranque automático al iniciar sesión: `scripts/launchd/ar.lagunitas.zabbix-lab.plist`
  (instrucciones dentro del archivo).
- Migración desde la versión 1 (scripts sueltos): `scripts/backup.sh` y luego
  `bin/lagunitas aprovisionar --migrar-v1` (borra hosts, mapa y dashboard v1 y recrea todo).

---

## 3. Simulación de caídas

```bash
bin/lagunitas lab estado                     # contenedor y perfil simulado de cada equipo
bin/lagunitas lab caida Nodo_Kika            # cae el nodo y su hogar queda "Sin servicio": 1 alerta
bin/lagunitas lab recuperar Nodo_Kika
bin/lagunitas lab caida Union_de_los_Rios    # caída troncal: 1 alerta, el resto "Sin servicio"
bin/lagunitas lab recuperar Union_de_los_Rios
bin/lagunitas lab caida Kika --solo          # solo ese equipo, sin sus dependientes
```

`caida` detiene también a los equipos aguas abajo, porque en la red real pierden el camino; así se
ve el efecto de las dependencias entre triggers. Zabbix detecta la caída en ~90 s.

---

## 4. Escenarios de falla (SNMP simulado)

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
aparecen entre 1 y 15 minutos después. `bin/lagunitas probar-snmp 10.50.0.x` funciona igual
contra los agentes simulados.

Los valores simulados están en `lab/snmpsim/data/*.snmprec` (formato `OID|tipo|valor`; los
valores `numeric` oscilan en el tiempo para producir gráficos realistas).

---

## 5. AP UniFi real del laboratorio

- Controlador: UniFi OS Server en la Mac del laboratorio, `192.168.1.81`, puerto `11443`
  (expuesto por `gvproxy`; puede cambiar al reiniciarse: `lsof -nP -iTCP -sTCP:LISTEN | grep gvproxy`).
- AP: U7 Pro Wall en `192.168.1.113`.
- IDs: `bin/lagunitas unifi-ids 192.168.1.81 11443`.

---

## 6. Sonda ICMP (AP real)

`bin/lagunitas lab sonda` hace ping desde la Mac, cada 10 s, a los equipos con perfil `icmp_sonda`
y envía disponibilidad, pérdida y latencia a Zabbix (`history.push`). El template
*Lagunitas - Disponibilidad ICMP - sonda externa* usa las mismas claves y triggers que el de
producción, así que dashboards, reportes, widget y dependencias funcionan igual. Si la sonda se
detiene, aparece la alerta *la sonda ICMP no envía datos*.

```bash
bin/lagunitas lab sonda --una-vez      # una medición, muestra el resultado
bin/lagunitas lab sonda                # continuo (Ctrl+C para detener)
```

Para que arranque sola al iniciar sesión: `scripts/launchd/ar.lagunitas.sonda-icmp.plist`
(instrucciones dentro del archivo). Log: `/tmp/lagunitas-sonda.log`.

---

## 7. Problemas frecuentes del laboratorio

| Síntoma | Solución |
|---|---|
| `failed to connect to the docker API ... colima` | Colima detenida: `colima start` o `./start.sh` |
| Un equipo simulado figura caído | `bin/lagunitas lab estado`; `bin/lagunitas lab recuperar <equipo>` o `bin/lagunitas lab levantar` |
| El AP "responde ping" aunque esté apagado | Limitación de Colima (§1): el AP usa la sonda ICMP (§6), no el fping del server |
| Alerta *la sonda ICMP no envía datos* | Sonda detenida: `bin/lagunitas lab sonda` o cargar el agente launchd (§6) |
| AP UniFi: *controlador UniFi no accesible* | Verificar que UniFi OS Server esté corriendo y el puerto actual (§5) |
