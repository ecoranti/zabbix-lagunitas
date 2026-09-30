<?php declare(strict_types = 0);

namespace Modules\LagunitasRed\Includes;

use API;

/**
 * Arma el estado de la red a partir de la API de Zabbix: equipos, métricas ICMP/UniFi,
 * problemas activos y relación padre -> hijo (dependencias entre triggers de caída).
 */
class RedService {

	public const GRUPO_POR_DEFECTO = 'Las Lagunitas';

	/** Items que se leen de cada equipo (templates del proyecto). */
	public const KEYS = [
		'icmpping', 'icmppingloss', 'icmppingsec', 'lagunitas.disponibilidad[24h]',
		'lagunitas.disponibilidad[7d]', 'ap.disponible', 'ap.cpu.util', 'ap.mem.util',
		'ap.clients.count', 'ap.uptime', 'ap.firmware', 'ap.modelo', 'ap.estado',
		'ap.uplink.rx', 'ap.uplink.tx', 'ap.radio.24ghz.retries', 'ap.radio.5ghz.retries',
		'ap.radio.6ghz.retries', 'net.tcp.service[https,{$UNIFI.HOST},{$UNIFI.PORT}]',
		// Radios Ubiquiti airMAX (SNMP)
		'airmax.wl.senal', 'airmax.wl.ruido', 'airmax.wl.snr', 'airmax.wl.ccq', 'airmax.wl.rssi',
		'airmax.airmax.calidad', 'airmax.airmax.capacidad', 'airmax.wl.tx', 'airmax.wl.rx',
		'airmax.wl.estaciones', 'airmax.wl.ssid', 'airmax.wl.canal', 'airmax.radio.modo',
		'airmax.radio.frecuencia', 'airmax.radio.potencia', 'airmax.radio.distancia', 'airmax.radio.antena',
		'airmax.radio.dfs', 'airmax.sistema.modelo', 'airmax.sistema.firmware', 'airmax.sistema.uptime',
		'airmax.sistema.nombre', 'airmax.cpu', 'airmax.memoria.uso', 'airmax.temperatura',
		// Routers Mikrotik (SNMP)
		'mikrotik.voltaje', 'mikrotik.dhcp.clientes', 'mikrotik.cpu', 'mikrotik.memoria.uso',
		'mikrotik.temperatura', 'mikrotik.temperatura.cpu', 'mikrotik.sistema.modelo',
		'mikrotik.sistema.routeros', 'mikrotik.sistema.firmware', 'mikrotik.sistema.serie',
		'mikrotik.sistema.uptime', 'mikrotik.sistema.nombre',
		'zabbix[host,snmp,available]'
	];

	/** Trigger de "equipo caído" de cada template de disponibilidad. */
	public const TRIGGERS_CAIDA = [
		'{HOST.NAME}: sin respuesta (ICMP)',
		'{HOST.NAME}: AP fuera de línea según UniFi'
	];

	/** Orden y títulos de las secciones (por tag "rol"). */
	public const SECCIONES = [
		'Gateway' => ['titulo' => 'Gateway (salida a Internet)', 'icono' => 'GW'],
		'Torre' => ['titulo' => 'Torres (backbone)', 'icono' => 'T'],
		'Nodo intermedio' => ['titulo' => 'Nodos intermedios', 'icono' => 'N'],
		'Hogar' => ['titulo' => 'Hogares e instituciones', 'icono' => 'H'],
		'Institución' => ['titulo' => 'Hogares e instituciones', 'icono' => 'H'],
		'Access point' => ['titulo' => 'Access points', 'icono' => 'AP']
	];

	/** Segundos sin valores nuevos para considerar un equipo "sin datos". */
	public const SIN_DATOS_SEG = 300;

	public const ESTADOS = [
		'caido' => ['texto' => 'Caído', 'orden' => 0],
		'afectado' => ['texto' => 'Sin servicio', 'orden' => 1],
		'advertencia' => ['texto' => 'Advertencia', 'orden' => 2],
		'sindatos' => ['texto' => 'Sin datos', 'orden' => 3],
		'mantenimiento' => ['texto' => 'Mantenimiento', 'orden' => 4],
		'ok' => ['texto' => 'En línea', 'orden' => 5],
		'nomon' => ['texto' => 'No monitoreado', 'orden' => 6]
	];

	public static function resolverGrupos(array $groupids): array {
		if (!$groupids) {
			$groupids = array_keys(API::HostGroup()->get([
				'output' => [],
				'filter' => ['name' => self::GRUPO_POR_DEFECTO],
				'preservekeys' => true
			]));
		}

		return $groupids ? getSubGroups($groupids) : [];
	}

	/**
	 * @return array{equipos: array, resumen: array, secciones: array}
	 */
	public static function recolectar(array $groupids, bool $incluir_no_monitoreados = true,
			?array $hostids = null): array {
		$groupids = self::resolverGrupos($groupids);
		$vacio = ['equipos' => [], 'resumen' => self::resumen([]), 'secciones' => []];

		if (!$groupids && $hostids === null) {
			return $vacio;
		}

		$opciones = [
			'output' => ['hostid', 'host', 'name', 'status', 'maintenance_status', 'description'],
			'selectInterfaces' => ['ip', 'dns', 'useip', 'main', 'type'],
			'selectTags' => ['tag', 'value'],
			'selectInventory' => ['type', 'type_full', 'hardware', 'model', 'location', 'notes'],
			'selectHostGroups' => ['name'],
			'preservekeys' => true
		];
		if ($groupids) {
			$opciones['groupids'] = $groupids;
		}
		if ($hostids !== null) {
			$opciones['hostids'] = $hostids;
		}
		if (!$incluir_no_monitoreados) {
			$opciones['filter'] = ['status' => HOST_STATUS_MONITORED];
		}
		$hosts = API::Host()->get($opciones);

		if (!$hosts) {
			return $vacio;
		}

		$ids = array_keys($hosts);

		// Métricas (último valor de cada item de interés).
		$items = [];
		foreach (API::Item()->get([
			'output' => ['itemid', 'hostid', 'key_', 'name', 'lastvalue', 'lastclock', 'state', 'units',
				'value_type', 'error', 'status'],
			'hostids' => $ids,
			'filter' => ['key_' => self::KEYS]
		]) as $item) {
			$items[$item['hostid']][$item['key_']] = $item;
		}

		// Triggers de caída y sus dependencias (definen la topología padre -> hijo).
		$caida_por_host = [];
		$host_por_trigger = [];
		$dependencias = [];
		foreach (API::Trigger()->get([
			'output' => ['triggerid', 'value', 'description', 'lastchange'],
			'hostids' => $ids,
			'filter' => ['description' => self::TRIGGERS_CAIDA],
			'selectHosts' => ['hostid'],
			'selectDependencies' => ['triggerid']
		]) as $t) {
			$hid = $t['hosts'][0]['hostid'];
			$caida_por_host[$hid] = $t;
			$host_por_trigger[$t['triggerid']] = $hid;
			$dependencias[$hid] = array_column($t['dependencies'], 'triggerid');
		}

		// Padres que están fuera del filtro (por ejemplo, otro grupo): se resuelven igual.
		$faltantes = [];
		foreach ($dependencias as $deps) {
			foreach ($deps as $tid) {
				if (!array_key_exists($tid, $host_por_trigger)) {
					$faltantes[] = $tid;
				}
			}
		}
		if ($faltantes) {
			foreach (API::Trigger()->get([
				'output' => ['triggerid'],
				'triggerids' => $faltantes,
				'selectHosts' => ['hostid', 'name']
			]) as $t) {
				$host_por_trigger[$t['triggerid']] = $t['hosts'][0]['hostid'];
			}
		}

		$padre = [];
		foreach ($dependencias as $hid => $deps) {
			if ($deps) {
				$padre[$hid] = $host_por_trigger[$deps[0]] ?? null;
			}
		}

		// Problemas activos (sin síntomas) agrupados por equipo.
		$problemas = [];
		$db_problems = API::Problem()->get([
			'output' => ['eventid', 'objectid', 'name', 'severity', 'clock', 'acknowledged', 'suppressed', 'opdata'],
			'hostids' => $ids,
			'source' => EVENT_SOURCE_TRIGGERS,
			'object' => EVENT_OBJECT_TRIGGER,
			'symptom' => false,
			'recent' => false
		]);
		if ($db_problems) {
			$trigger_host = [];
			foreach (API::Trigger()->get([
				'output' => ['triggerid'],
				'triggerids' => array_unique(array_column($db_problems, 'objectid')),
				'selectHosts' => ['hostid']
			]) as $t) {
				$trigger_host[$t['triggerid']] = array_column($t['hosts'], 'hostid');
			}
			foreach ($db_problems as $p) {
				foreach ($trigger_host[$p['objectid']] ?? [] as $hid) {
					$problemas[$hid][] = $p;
				}
			}
			foreach ($problemas as &$lista) {
				usort($lista, static fn($a, $b) => $b['severity'] <=> $a['severity'] ?: $b['clock'] <=> $a['clock']);
			}
			unset($lista);
		}

		$ahora = time();
		$equipos = [];
		foreach ($hosts as $hid => $h) {
			$tags = array_column($h['tags'], 'value', 'tag');
			$rol = $tags['rol'] ?? ($h['inventory']['type'] ?? '') ?: 'Otro';
			$it = $items[$hid] ?? [];
			// AP UniFi: tiene métricas de la API (puede tener además ping, como en producción).
			$es_ap = array_key_exists('ap.disponible', $it);
			$tipo = array_key_exists('airmax.wl.senal', $it) ? 'airmax'
				: (array_key_exists('mikrotik.voltaje', $it) ? 'mikrotik' : ($es_ap ? 'unifi' : 'icmp'));
			$disp = $it['icmpping'] ?? $it['ap.disponible'] ?? null;

			$iface = null;
			foreach ($h['interfaces'] as $i) {
				if ($i['main'] == 1) {
					$iface = $i;
					break;
				}
			}
			$ip = $iface ? ($iface['useip'] == 1 ? $iface['ip'] : $iface['dns']) : '';

			$probs = $problemas[$hid] ?? [];
			$max_sev = $probs ? (int) max(array_column($probs, 'severity')) : -1;

			$equipos[$hid] = [
				'hostid' => $hid,
				'host' => $h['host'],
				'nombre' => $h['name'],
				'ip' => $ip,
				'rol' => $rol,
				'es_ap' => $es_ap,
				'tipo' => $tipo,
				'funcion' => $tags['funcion'] ?? '',
				'elemento' => $tags['elemento'] ?? $h['host'],
				'tramo' => $tags['estado'] ?? '',
				'equipo' => $h['inventory']['hardware'] ?? '',
				'modelo' => $h['inventory']['model'] ?? '',
				'grupos' => array_column($h['hostgroups'], 'name'),
				'descripcion' => $h['description'],
				'monitoreado' => $h['status'] == HOST_STATUS_MONITORED,
				'mantenimiento' => $h['maintenance_status'] == HOST_MAINTENANCE_STATUS_ON,
				'padre' => $padre[$hid] ?? null,
				'hijos' => [],
				'items' => $it,
				'disp' => self::valor($disp),
				'disp_edad' => $disp && $disp['lastclock'] ? $ahora - (int) $disp['lastclock'] : null,
				'disp_soportado' => $disp && $disp['state'] == ITEM_STATE_NORMAL,
				'latencia_ms' => ($v = self::valor($it['icmppingsec'] ?? null)) !== null ? $v * 1000 : null,
				'perdida' => self::valor($it['icmppingloss'] ?? null),
				'disp24' => self::valor($it['lagunitas.disponibilidad[24h]'] ?? null),
				'disp7d' => self::valor($it['lagunitas.disponibilidad[7d]'] ?? null),
				'caida_activa' => isset($caida_por_host[$hid]) && $caida_por_host[$hid]['value'] == TRIGGER_VALUE_TRUE,
				'caida_desde' => isset($caida_por_host[$hid]) && $caida_por_host[$hid]['value'] == TRIGGER_VALUE_TRUE
					? (int) $caida_por_host[$hid]['lastchange'] : null,
				'problemas' => $probs,
				'max_severidad' => $max_sev,
				'estado' => null,
				'causa' => null
			];
		}

		// Sin respuesta al ping, fping informa latencia 0: no es un valor real.
		foreach ($equipos as &$e) {
			if ($e['disp'] !== null && (int) $e['disp'] === 0) {
				$e['latencia_ms'] = null;
			}
		}
		unset($e);

		foreach ($equipos as $hid => $e) {
			if ($e['padre'] !== null && array_key_exists($e['padre'], $equipos)) {
				$equipos[$e['padre']]['hijos'][] = $hid;
			}
		}

		// Estado base.
		foreach ($equipos as $hid => &$e) {
			if (!$e['monitoreado']) {
				$e['estado'] = 'nomon';
			}
			elseif ($e['mantenimiento']) {
				$e['estado'] = 'mantenimiento';
			}
			elseif ($e['caida_activa']) {
				$e['estado'] = 'caido';
			}
			elseif (!$e['disp_soportado'] || $e['disp'] === null || $e['disp_edad'] > self::SIN_DATOS_SEG) {
				$e['estado'] = 'sindatos';
			}
			elseif ((int) $e['disp'] === 0) {
				$e['estado'] = 'caido'; // se resolverá como "afectado" si un ancestro está caído
			}
			elseif ($e['max_severidad'] >= TRIGGER_SEVERITY_WARNING) {
				$e['estado'] = 'advertencia';
			}
			else {
				$e['estado'] = 'ok';
			}
		}
		unset($e);

		// Equipos sin respuesta cuya caída se explica por un ancestro caído: "sin servicio".
		foreach ($equipos as $hid => &$e) {
			if ($e['estado'] !== 'caido' || $e['caida_activa']) {
				continue;
			}
			$ancestro = self::ancestroCaido($equipos, $hid);
			if ($ancestro !== null) {
				$e['estado'] = 'afectado';
				$e['causa'] = $ancestro;
			}
		}
		unset($e);
		foreach ($equipos as $hid => &$e) {
			if ($e['estado'] === 'sindatos' && $e['monitoreado']) {
				$ancestro = self::ancestroCaido($equipos, $hid);
				if ($ancestro !== null) {
					$e['estado'] = 'afectado';
					$e['causa'] = $ancestro;
				}
			}
		}
		unset($e);

		return [
			'equipos' => $equipos,
			'resumen' => self::resumen($equipos),
			'secciones' => self::secciones($equipos)
		];
	}

	public static function ancestroCaido(array $equipos, string $hid): ?string {
		$visto = [];
		$actual = $equipos[$hid]['padre'] ?? null;
		while ($actual !== null && !isset($visto[$actual]) && array_key_exists($actual, $equipos)) {
			$visto[$actual] = true;
			if ($equipos[$actual]['caida_activa']) {
				return $actual;
			}
			$actual = $equipos[$actual]['padre'];
		}

		return null;
	}

	/** Todos los equipos que dependen (directa o indirectamente) del dado. */
	public static function descendientes(array $equipos, string $hid): array {
		$out = [];
		$pila = $equipos[$hid]['hijos'] ?? [];
		while ($pila) {
			$h = array_shift($pila);
			if (isset($out[$h])) {
				continue;
			}
			$out[$h] = true;
			foreach ($equipos[$h]['hijos'] ?? [] as $n) {
				$pila[] = $n;
			}
		}

		return array_keys($out);
	}

	/**
	 * Items dinámicos (descubiertos) de un equipo: interfaces, estaciones asociadas y WAN.
	 *
	 * @return array{interfaces: array, estaciones: array, wan: array}
	 */
	public static function descubiertos(string $hostid): array {
		$out = ['interfaces' => [], 'estaciones' => [], 'wan' => []];
		$items = API::Item()->get([
			'output' => ['itemid', 'key_', 'name', 'lastvalue', 'lastclock', 'units', 'state'],
			'hostids' => [$hostid],
			'search' => ['key_' => ['airmax.if.', 'mikrotik.if.', 'airmax.sta.', 'mikrotik.wan.']],
			'searchByAny' => true,
			'startSearch' => true,
			'filter' => ['flags' => ZBX_FLAG_DISCOVERY_CREATED]
		]);
		foreach ($items as $i) {
			if (!preg_match('/^(airmax|mikrotik)\.(if|sta|wan)\.([a-z]+)\[(.*)\]$/', $i['key_'], $m)) {
				continue;
			}
			[, , $grupo, $metrica, $indice] = $m;
			$valor = ($i['lastclock'] != 0 && is_numeric($i['lastvalue'])) ? (float) $i['lastvalue'] : null;
			if ($grupo === 'if') {
				$out['interfaces'][$indice]['nombre'] = $indice;
				$out['interfaces'][$indice][$metrica] = $valor;
				$out['interfaces'][$indice]['itemids'][$metrica] = $i['itemid'];
			}
			elseif ($grupo === 'sta') {
				if (preg_match('/^Estación (.*): /u', $i['name'], $n)) {
					$out['estaciones'][$indice]['nombre'] = $n[1];
				}
				$out['estaciones'][$indice][$metrica] = $valor;
				$out['estaciones'][$indice]['itemids'][$metrica] = $i['itemid'];
			}
			else {
				$out['wan'][$indice] = ['nombre' => $indice, 'estado' => $valor, 'itemid' => $i['itemid']];
			}
		}
		ksort($out['interfaces'], SORT_NATURAL);

		return $out;
	}

	/** Camino desde el equipo hasta la raíz (sin incluir al equipo). */
	public static function ancestros(array $equipos, string $hid): array {
		$out = [];
		$actual = $equipos[$hid]['padre'] ?? null;
		while ($actual !== null && !in_array($actual, $out) && array_key_exists($actual, $equipos)) {
			$out[] = $actual;
			$actual = $equipos[$actual]['padre'];
		}

		return $out;
	}

	private static function valor(?array $item): ?float {
		if ($item === null || $item['lastclock'] == 0 || $item['lastvalue'] === '' || !is_numeric($item['lastvalue'])) {
			return null;
		}

		return (float) $item['lastvalue'];
	}

	private static function resumen(array $equipos): array {
		$r = ['total' => count($equipos)];
		foreach (array_keys(self::ESTADOS) as $k) {
			$r[$k] = 0;
		}
		foreach ($equipos as $e) {
			$r[$e['estado']]++;
		}

		return $r;
	}

	private static function secciones(array $equipos): array {
		$out = [];
		foreach ($equipos as $hid => $e) {
			$titulo = self::SECCIONES[$e['rol']]['titulo'] ?? 'Otros equipos';
			$out[$titulo][] = $hid;
		}
		$orden = array_values(array_unique(array_column(self::SECCIONES, 'titulo')));
		uksort($out, static function($a, $b) use ($orden) {
			$ia = array_search($a, $orden);
			$ib = array_search($b, $orden);

			return ($ia === false ? 99 : $ia) <=> ($ib === false ? 99 : $ib);
		});
		foreach ($out as &$ids) {
			usort($ids, static function($a, $b) use ($equipos) {
				return self::ESTADOS[$equipos[$a]['estado']]['orden'] <=> self::ESTADOS[$equipos[$b]['estado']]['orden']
					?: strnatcasecmp($equipos[$a]['nombre'], $equipos[$b]['nombre']);
			});
		}
		unset($ids);

		return $out;
	}
}
