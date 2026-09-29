<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes\Includes;

use API;

/**
 * Cálculo del reporte de disponibilidad de la Red Las Lagunitas.
 *
 * - Disponibilidad propia: tiempo en que el trigger de caída del propio equipo estuvo en
 *   PROBLEM (se unen intervalos superpuestos antes de sumar).
 * - Disponibilidad del servicio: además se descuentan las caídas de todos sus ancestros
 *   (torre/nodo del que depende). Es lo que efectivamente vivió el hogar o la institución.
 *   Gracias a las dependencias de triggers, la caída de un ancestro no genera alertas en
 *   los hijos, así que sin este cálculo sus horas sin servicio quedarían ocultas.
 */
class ReporteService {

	public const GRUPO = 'Las Lagunitas';
	public const TRIGGERS_CAIDA = [
		'{HOST.NAME}: sin respuesta (ICMP)',
		'{HOST.NAME}: AP fuera de línea según UniFi'
	];
	public const ORDEN_ROLES = ['Torre', 'Nodo intermedio', 'Hogar', 'Institución', 'Access point'];
	public const PERIODOS = [
		'hoy' => 'Hoy',
		'24h' => 'Últimas 24 horas',
		'7d' => 'Últimos 7 días',
		'30d' => 'Últimos 30 días',
		'mes' => 'Mes actual',
		'mes_anterior' => 'Mes anterior',
		'personalizado' => 'Personalizado'
	];

	public static function normalizar(array $in): array {
		$f = [
			'periodo' => array_key_exists($in['periodo'] ?? '', self::PERIODOS) ? $in['periodo'] : '7d',
			'desde' => (string) ($in['desde'] ?? ''),
			'hasta' => (string) ($in['hasta'] ?? ''),
			'rol' => (string) ($in['rol'] ?? ''),
			'slo' => is_numeric($in['slo'] ?? null) ? max(0.0, min(100.0, (float) $in['slo'])) : 99.5,
			'vista' => ($in['vista'] ?? '') === 'gerencial' ? 'gerencial' : 'tecnica'
		];
		[$f['from'], $f['to']] = self::rango($f);

		return $f;
	}

	/** @return int[] [desde, hasta] como timestamps (hasta nunca es futuro). */
	public static function rango(array $f): array {
		$ahora = time();
		switch ($f['periodo']) {
			case 'hoy':
				return [strtotime('today'), $ahora];
			case '24h':
				return [$ahora - 86400, $ahora];
			case '30d':
				return [$ahora - 30 * 86400, $ahora];
			case 'mes':
				return [strtotime('first day of this month 00:00'), $ahora];
			case 'mes_anterior':
				return [strtotime('first day of last month 00:00'), strtotime('first day of this month 00:00')];
			case 'personalizado':
				$d = strtotime($f['desde'].' 00:00');
				$h = strtotime($f['hasta'].' 23:59:59');
				if ($d !== false && $h !== false && $d < $h) {
					return [$d, min($h + 1, $ahora)];
				}
				// fecha inválida: cae en 7 días
			default:
				return [$ahora - 7 * 86400, $ahora];
		}
	}

	public static function construir(array $f): array {
		$from = $f['from'];
		$to = $f['to'];
		$total = max(1, $to - $from);

		$grupos = array_keys(API::HostGroup()->get([
			'output' => [], 'filter' => ['name' => self::GRUPO], 'preservekeys' => true
		]));
		$vacio = ['filas' => [], 'resumen' => null, 'conclusiones' => [], 'roles' => []];
		if (!$grupos) {
			return $vacio;
		}

		$subgrupos = getSubGroups($grupos);
		$hosts = API::Host()->get([
			'output' => ['hostid', 'host', 'name', 'maintenance_status'],
			'groupids' => $subgrupos,
			'filter' => ['status' => HOST_STATUS_MONITORED],
			'selectTags' => ['tag', 'value'],
			'selectInterfaces' => ['ip', 'dns', 'useip', 'main'],
			'preservekeys' => true
		]);
		if (!$hosts) {
			return $vacio;
		}

		$roles = [];
		foreach ($hosts as $hid => $h) {
			$rol = array_column($h['tags'], 'value', 'tag')['rol'] ?? 'Otro';
			$hosts[$hid]['rol'] = $rol;
			$roles[$rol] = true;
		}
		$roles = array_keys($roles);
		usort($roles, static fn($a, $b) => self::ordenRol($a) <=> self::ordenRol($b));

		// Triggers de caída + dependencias (topología).
		$trig = API::Trigger()->get([
			'output' => ['triggerid', 'value'],
			'hostids' => array_keys($hosts),
			'filter' => ['description' => self::TRIGGERS_CAIDA],
			'selectHosts' => ['hostid'],
			'selectDependencies' => ['triggerid']
		]);
		$trigger_de = [];
		$host_de = [];
		foreach ($trig as $t) {
			$trigger_de[$t['hosts'][0]['hostid']] = $t;
			$host_de[$t['triggerid']] = $t['hosts'][0]['hostid'];
		}
		$padre = [];
		foreach ($trigger_de as $hid => $t) {
			$dep = $t['dependencies'][0]['triggerid'] ?? null;
			$padre[$hid] = $dep !== null ? ($host_de[$dep] ?? null) : null;
		}

		// Eventos de caída que se superponen con el período (se buscan hasta 90 días antes).
		$eventos = $trig ? API::Event()->get([
			'output' => ['eventid', 'objectid', 'clock', 'r_eventid'],
			'objectids' => array_column($trig, 'triggerid'),
			'source' => EVENT_SOURCE_TRIGGERS,
			'object' => EVENT_OBJECT_TRIGGER,
			'value' => TRIGGER_VALUE_TRUE,
			'time_from' => $from - 90 * 86400,
			'time_till' => $to,
			'sortfield' => ['clock'],
			'sortorder' => ZBX_SORT_UP
		]) : [];
		$r_ids = array_values(array_filter(array_column($eventos, 'r_eventid')));
		$r_clock = $r_ids ? array_column(API::Event()->get([
			'output' => ['eventid', 'clock'], 'eventids' => $r_ids
		]), 'clock', 'eventid') : [];

		$incidentes = [];
		foreach ($eventos as $ev) {
			$ini = (int) $ev['clock'];
			$fin = $ev['r_eventid'] != 0 ? (int) ($r_clock[$ev['r_eventid']] ?? $to) : null;
			if (($fin ?? PHP_INT_MAX) <= $from) {
				continue; // terminó antes del período
			}
			$hid = $host_de[$ev['objectid']] ?? null;
			if ($hid !== null) {
				$incidentes[$hid][] = ['inicio' => $ini, 'fin' => $fin];
			}
		}

		// Otros problemas (advertencias de calidad) que comenzaron en el período.
		$avisos = [];
		foreach (API::Event()->get([
			'output' => ['objectid', 'severity'],
			'hostids' => array_keys($hosts),
			'source' => EVENT_SOURCE_TRIGGERS,
			'object' => EVENT_OBJECT_TRIGGER,
			'value' => TRIGGER_VALUE_TRUE,
			'time_from' => $from,
			'time_till' => $to,
			'selectHosts' => ['hostid']
		]) as $ev) {
			if (array_key_exists($ev['objectid'], $host_de)) {
				continue;
			}
			foreach ($ev['hosts'] as $h) {
				$avisos[$h['hostid']] = ($avisos[$h['hostid']] ?? 0) + 1;
			}
		}

		// Latencia y pérdida medias del período (tendencias horarias).
		$medias = self::medias(array_keys($hosts), $from, $to);

		$propios = [];
		foreach ($hosts as $hid => $h) {
			$propios[$hid] = self::unir(array_map(
				static fn($i) => [max($i['inicio'], $from), min($i['fin'] ?? $to, $to)],
				$incidentes[$hid] ?? []
			));
		}

		$filas = [];
		foreach ($hosts as $hid => $h) {
			$ancestros = [];
			$a = $padre[$hid] ?? null;
			while ($a !== null && !in_array($a, $ancestros) && array_key_exists($a, $hosts)) {
				$ancestros[] = $a;
				$a = $padre[$a] ?? null;
			}
			$servicio = $propios[$hid];
			foreach ($ancestros as $a) {
				$servicio = array_merge($servicio, $propios[$a]);
			}
			$servicio = self::unir($servicio);

			$caida_propia = self::suma($propios[$hid]);
			$caida_servicio = self::suma($servicio);
			$lista = $incidentes[$hid] ?? [];
			$resueltos = array_filter($lista, static fn($i) => $i['fin'] !== null);
			$duraciones = array_map(static fn($i) => ($i['fin'] ?? $to) - $i['inicio'], $lista);

			$iface = null;
			foreach ($h['interfaces'] as $i) {
				if ($i['main'] == 1) {
					$iface = $i;
				}
			}

			$descendientes = 0;
			foreach ($hosts as $otro => $_) {
				$x = $padre[$otro] ?? null;
				$vistos = [];
				while ($x !== null && !isset($vistos[$x])) {
					if ($x == $hid) {
						$descendientes++;
						break;
					}
					$vistos[$x] = true;
					$x = $padre[$x] ?? null;
				}
			}

			// Detalle de incidentes (propios y heredados de ancestros).
			$detalle = [];
			foreach ($lista as $i) {
				$detalle[] = $i + ['causa' => null];
			}
			foreach ($ancestros as $a) {
				foreach ($incidentes[$a] ?? [] as $i) {
					$detalle[] = $i + ['causa' => $hosts[$a]['name']];
				}
			}
			usort($detalle, static fn($x, $y) => $y['inicio'] <=> $x['inicio']);

			$filas[$hid] = [
				'hostid' => $hid,
				'nombre' => $h['name'],
				'host' => $h['host'],
				'ip' => $iface ? ($iface['useip'] == 1 ? $iface['ip'] : $iface['dns']) : '',
				'rol' => $h['rol'],
				'padre' => isset($padre[$hid]) && isset($hosts[$padre[$hid]]) ? $hosts[$padre[$hid]]['name'] : '',
				'caido_ahora' => isset($trigger_de[$hid]) && $trigger_de[$hid]['value'] == TRIGGER_VALUE_TRUE,
				'disp_propia' => 100 * (1 - $caida_propia / $total),
				'disp_servicio' => 100 * (1 - $caida_servicio / $total),
				'caida_propia' => $caida_propia,
				'caida_servicio' => $caida_servicio,
				'incidentes' => count($lista),
				'mttr' => $resueltos ? (int) round(array_sum(array_map(
					static fn($i) => $i['fin'] - $i['inicio'], $resueltos)) / count($resueltos)) : null,
				'mayor' => $duraciones ? max($duraciones) : 0,
				'latencia_ms' => isset($medias[$hid]['icmppingsec']) ? $medias[$hid]['icmppingsec'] * 1000 : null,
				'perdida' => $medias[$hid]['icmppingloss'] ?? null,
				'avisos' => $avisos[$hid] ?? 0,
				'dependientes' => $descendientes,
				'cumple' => 100 * (1 - $caida_servicio / $total) >= $f['slo'],
				'detalle' => array_slice($detalle, 0, 30)
			];
		}

		if ($f['rol'] !== '') {
			$filas = array_filter($filas, static fn($r) => $r['rol'] === $f['rol']);
		}
		uasort($filas, static fn($a, $b) => self::ordenRol($a['rol']) <=> self::ordenRol($b['rol'])
			?: $a['disp_servicio'] <=> $b['disp_servicio'] ?: strnatcasecmp($a['nombre'], $b['nombre']));

		$resumen = self::resumen($filas, $total);

		return [
			'filas' => $filas,
			'resumen' => $resumen,
			'conclusiones' => self::conclusiones($filas, $resumen, $f),
			'roles' => $roles
		];
	}

	private static function ordenRol(string $rol): int {
		$i = array_search($rol, self::ORDEN_ROLES);

		return $i === false ? 99 : $i;
	}

	/** Une intervalos [a, b] superpuestos o contiguos. */
	public static function unir(array $intervalos): array {
		$intervalos = array_filter($intervalos, static fn($i) => $i[1] > $i[0]);
		usort($intervalos, static fn($a, $b) => $a[0] <=> $b[0]);
		$out = [];
		foreach ($intervalos as [$a, $b]) {
			if ($out && $a <= $out[count($out) - 1][1]) {
				$out[count($out) - 1][1] = max($out[count($out) - 1][1], $b);
			}
			else {
				$out[] = [$a, $b];
			}
		}

		return $out;
	}

	private static function suma(array $intervalos): int {
		return array_sum(array_map(static fn($i) => $i[1] - $i[0], $intervalos));
	}

	private static function medias(array $hostids, int $from, int $to): array {
		$items = API::Item()->get([
			'output' => ['itemid', 'hostid', 'key_', 'value_type'],
			'hostids' => $hostids,
			'filter' => ['key_' => ['icmppingsec', 'icmppingloss']]
		]);
		if (!$items) {
			return [];
		}
		$por_item = array_column($items, null, 'itemid');
		$acum = [];
		foreach (API::Trend()->get([
			'output' => ['itemid', 'value_avg', 'num'],
			'itemids' => array_keys($por_item),
			'time_from' => $from,
			'time_till' => $to
		]) as $t) {
			$acum[$t['itemid']][0] = ($acum[$t['itemid']][0] ?? 0) + $t['value_avg'] * $t['num'];
			$acum[$t['itemid']][1] = ($acum[$t['itemid']][1] ?? 0) + $t['num'];
		}
		$out = [];
		foreach ($acum as $itemid => [$suma, $n]) {
			if ($n > 0) {
				$it = $por_item[$itemid];
				$out[$it['hostid']][$it['key_']] = $suma / $n;
			}
		}

		return $out;
	}

	private static function resumen(array $filas, int $total): ?array {
		if (!$filas) {
			return null;
		}
		$n = count($filas);
		$resueltos = array_filter(array_column($filas, 'mttr'), static fn($v) => $v !== null);

		return [
			'equipos' => $n,
			'disp_media' => array_sum(array_column($filas, 'disp_servicio')) / $n,
			'cumplen' => count(array_filter($filas, static fn($r) => $r['cumple'])),
			'no_cumplen' => count(array_filter($filas, static fn($r) => !$r['cumple'])),
			'incidentes' => array_sum(array_column($filas, 'incidentes')),
			'caida_total' => array_sum(array_column($filas, 'caida_propia')),
			'sin_servicio_total' => array_sum(array_column($filas, 'caida_servicio')),
			'mttr' => $resueltos ? (int) round(array_sum($resueltos) / count($resueltos)) : null,
			'caidos_ahora' => count(array_filter($filas, static fn($r) => $r['caido_ahora'])),
			'periodo_seg' => $total
		];
	}

	private static function conclusiones(array $filas, ?array $r, array $f): array {
		if ($r === null) {
			return [];
		}
		$out = [];
		$out[] = sprintf('La disponibilidad promedio del servicio fue de %s %% sobre %d equipos monitoreados.',
			number_format($r['disp_media'], 3, ',', '.'), $r['equipos']);
		$out[] = $r['no_cumplen']
			? sprintf('%d de %d equipos no alcanzaron el objetivo de %s %%: %s.', $r['no_cumplen'], $r['equipos'],
				number_format($f['slo'], 2, ',', '.'), implode(', ', array_column(
					array_filter($filas, static fn($x) => !$x['cumple']), 'nombre')))
			: sprintf('Todos los equipos cumplieron el objetivo de %s %%.', number_format($f['slo'], 2, ',', '.'));
		if ($r['incidentes']) {
			$peor = null;
			foreach ($filas as $x) {
				if ($peor === null || $x['mayor'] > $peor['mayor']) {
					$peor = $x;
				}
			}
			$out[] = sprintf('Se registraron %d caídas propias; la más larga fue en %s (%s).', $r['incidentes'],
				$peor['nombre'], self::duracion($peor['mayor']));
			$impacto = null;
			foreach ($filas as $x) {
				if ($x['dependientes'] && $x['caida_propia'] && ($impacto === null
						|| $x['caida_propia'] * $x['dependientes'] > $impacto['caida_propia'] * $impacto['dependientes'])) {
					$impacto = $x;
				}
			}
			if ($impacto !== null) {
				$out[] = sprintf('Mayor impacto: la caída de %s (%s) dejó sin servicio a %d equipos que dependen de él.',
					$impacto['nombre'], self::duracion($impacto['caida_propia']), $impacto['dependientes']);
			}
		}
		else {
			$out[] = 'No se registraron caídas de equipos en el período.';
		}
		if ($r['caidos_ahora']) {
			$out[] = sprintf('Al momento de generar el reporte hay %d equipo(s) caído(s).', $r['caidos_ahora']);
		}

		return $out;
	}

	public static function duracion(int $seg): string {
		if ($seg <= 0) {
			return '0 min';
		}
		if ($seg < 60) {
			return $seg.' s';
		}
		$d = intdiv($seg, 86400);
		$h = intdiv($seg % 86400, 3600);
		$m = intdiv($seg % 3600, 60);

		return $d ? "$d d $h h" : ($h ? "$h h $m min" : "$m min");
	}
}
