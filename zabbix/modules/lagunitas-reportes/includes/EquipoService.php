<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes\Includes;

use API;

/**
 * Detalle técnico de un equipo para el período del reporte: comportamiento de sus
 * métricas (según el tipo de equipo), interfaces, estaciones asociadas, problemas
 * agrupados y conclusiones/recomendaciones automáticas.
 */
class EquipoService {

	/**
	 * Métricas por clave: título, factor, unidad, decimales, sentido ('alto' = peor cuanto más alto,
	 * 'bajo' = peor cuanto más bajo, null = informativa), umbral de advertencia, umbral crítico.
	 */
	public const METRICAS = [
		// Disponibilidad y calidad (todos los equipos ICMP)
		'icmppingsec' => ['Latencia ICMP', 1000, 'ms', 1, 'alto', 100, 150],
		'icmppingloss' => ['Pérdida ICMP', 1, '%', 1, 'alto', 5, 20],
		// Radios airMAX
		'airmax.wl.senal' => ['Señal', 1, 'dBm', 0, 'bajo', -72, -80],
		'airmax.wl.snr' => ['SNR', 1, 'dB', 0, 'bajo', 25, 15],
		'airmax.wl.ccq' => ['CCQ', 1, '%', 0, 'bajo', 85, 70],
		'airmax.wl.ruido' => ['Piso de ruido', 1, 'dBm', 0, 'alto', -85, -80],
		'airmax.airmax.calidad' => ['Calidad airMAX', 1, '%', 0, 'bajo', 75, 60],
		'airmax.airmax.capacidad' => ['Capacidad airMAX', 1, '%', 0, 'bajo', 60, 40],
		'airmax.cpu' => ['CPU', 1, '%', 1, 'alto', 80, 90],
		'airmax.memoria.uso' => ['Memoria', 1, '%', 1, 'alto', 80, 90],
		'airmax.temperatura' => ['Temperatura', 1, '°C', 0, 'alto', 65, 75],
		// Routers Mikrotik
		'mikrotik.voltaje' => ['Voltaje (batería)', 1, 'V', 2, 'bajo', 12.0, 11.6],
		'mikrotik.cpu' => ['CPU', 1, '%', 1, 'alto', 70, 85],
		'mikrotik.memoria.uso' => ['Memoria', 1, '%', 1, 'alto', 80, 90],
		'mikrotik.temperatura' => ['Temperatura', 1, '°C', 1, 'alto', 55, 65],
		'mikrotik.dhcp.clientes' => ['Clientes DHCP', 1, '', 0, null, null, null],
		// AP UniFi
		'ap.cpu.util' => ['CPU', 1, '%', 1, 'alto', 60, 85],
		'ap.mem.util' => ['Memoria', 1, '%', 1, 'alto', 60, 85],
		'ap.clients.count' => ['Clientes Wi-Fi', 1, '', 0, null, null, null],
		'ap.radio.5ghz.retries' => ['Reintentos 5 GHz', 1, '%', 1, 'alto', 15, 25],
		'ap.radio.24ghz.retries' => ['Reintentos 2.4 GHz', 1, '%', 1, 'alto', 15, 25]
	];

	/** Categoría del problema según el tag "alcance" de los triggers del proyecto. */
	public const CATEGORIAS = [
		'disponibilidad' => 'Disponibilidad', 'calidad' => 'Calidad de enlace', 'radio' => 'Radio',
		'energia' => 'Energía', 'rendimiento' => 'Recursos', 'red' => 'Interfaces', 'internet' => 'Internet',
		'snmp' => 'Monitoreo', 'api' => 'Monitoreo', 'sistema' => 'Sistema', 'clientes' => 'Clientes'
	];

	public static function construir(string $hostid, array $f): ?array {
		$host = API::Host()->get([
			'output' => ['hostid', 'host', 'name', 'maintenance_status', 'description'],
			'hostids' => [$hostid],
			'selectTags' => ['tag', 'value'],
			'selectInterfaces' => ['ip', 'dns', 'useip', 'main', 'type'],
			'selectHostGroups' => ['name'],
			'selectInventory' => ['type', 'type_full', 'hardware', 'model', 'notes']
		]);
		if (!$host) {
			return null;
		}
		$host = $host[0];
		$from = $f['from'];
		$to = $f['to'];

		// Fila del reporte general para este equipo (disponibilidad propia y de servicio).
		$rep = ReporteService::construir(['hostid' => $hostid, 'grupo' => '', 'tipo' => ''] + $f);
		$fila = $rep['filas'][$hostid] ?? null;

		$items = API::Item()->get([
			'output' => ['itemid', 'key_', 'name', 'lastvalue', 'lastclock', 'units', 'value_type', 'state', 'flags'],
			'hostids' => [$hostid],
			'preservekeys' => true
		]);
		$por_key = array_column($items, null, 'key_');

		$metricas = [];
		foreach (self::METRICAS as $key => [$titulo, $factor, $unidad, $dec, $sentido, $warn, $crit]) {
			if (!isset($por_key[$key])) {
				continue;
			}
			$metricas[$key] = self::metrica($por_key[$key], $from, $to) + [
				'titulo' => $titulo, 'factor' => $factor, 'unidad' => $unidad, 'decimales' => $dec,
				'sentido' => $sentido, 'warn' => $warn, 'crit' => $crit, 'key' => $key
			];
			$m = &$metricas[$key];
			foreach (['actual', 'promedio', 'minimo', 'maximo'] as $k) {
				if ($m[$k] !== null) {
					$m[$k] *= $factor;
				}
			}
			foreach ($m['serie'] as &$p) {
				$p[1] *= $factor;
			}
			unset($p);
			$extremo = $sentido === 'bajo' ? $m['minimo'] : $m['maximo'];
			$m['nivel_actual'] = self::nivel($m['actual'], $sentido, $warn, $crit);
			$m['nivel_pico'] = self::nivel($extremo, $sentido, $warn, $crit);
			[$m['horas_warn'], $m['horas_crit']] = self::horasFueraDeUmbral($m['serie'], $sentido, $warn, $crit);
			unset($m);
		}

		$problemas = self::problemas($hostid, $f);

		return [
			'host' => $host,
			'fila' => $fila,
			'tipo' => ReporteService::tipoEquipo(array_keys($por_key)),
			'metricas' => $metricas,
			'interfaces' => self::interfaces($items, $from, $to),
			'estaciones' => self::estaciones($items, $from, $to),
			'problemas' => $problemas,
			'conclusiones' => self::conclusiones($metricas, $fila, $problemas),
			'textos' => self::textos($por_key)
		];
	}

	/** Actual, promedio, mínimo, máximo y serie (tendencias horarias o historia si el período es corto). */
	private static function metrica(array $item, int $from, int $to): array {
		$serie = [];
		$suma = 0;
		$n = 0;
		$min = null;
		$max = null;
		$tendencias = API::Trend()->get([
			'output' => ['clock', 'num', 'value_min', 'value_avg', 'value_max'],
			'itemids' => [$item['itemid']], 'time_from' => $from, 'time_till' => $to
		]);
		if (count($tendencias) >= 6) {
			foreach ($tendencias as $t) {
				$serie[] = [(int) $t['clock'], (float) $t['value_avg']];
				$suma += $t['value_avg'] * $t['num'];
				$n += $t['num'];
				$min = $min === null ? (float) $t['value_min'] : min($min, (float) $t['value_min']);
				$max = $max === null ? (float) $t['value_max'] : max($max, (float) $t['value_max']);
			}
		}
		else {
			$historia = API::History()->get([
				'output' => ['clock', 'value'], 'history' => (int) $item['value_type'], 'itemids' => [$item['itemid']],
				'time_from' => $from, 'time_till' => $to, 'sortfield' => 'clock', 'sortorder' => ZBX_SORT_UP,
				'limit' => 5000
			]);
			foreach ($historia as $h) {
				$v = (float) $h['value'];
				$serie[] = [(int) $h['clock'], $v];
				$suma += $v;
				$n++;
				$min = $min === null ? $v : min($min, $v);
				$max = $max === null ? $v : max($max, $v);
			}
		}
		// La serie se reduce a ~60 puntos para el sparkline.
		if (count($serie) > 60) {
			$paso = count($serie) / 60;
			$reducida = [];
			for ($i = 0; $i < 60; $i++) {
				$tramo = array_slice($serie, (int) floor($i * $paso), max(1, (int) floor($paso)));
				$reducida[] = [$tramo[0][0], array_sum(array_column($tramo, 1)) / count($tramo)];
			}
			$serie = $reducida;
		}

		return [
			'itemid' => $item['itemid'],
			'actual' => ($item['lastclock'] != 0 && is_numeric($item['lastvalue'])) ? (float) $item['lastvalue'] : null,
			'promedio' => $n ? $suma / $n : null,
			'minimo' => $min,
			'maximo' => $max,
			'serie' => $serie,
			'muestras' => $n,
			'fuente' => count($tendencias) >= 6 ? 'tendencias' : 'historia'
		];
	}

	public static function nivel(?float $v, ?string $sentido, $warn, $crit): string {
		if ($v === null || $sentido === null) {
			return 'na';
		}
		if ($sentido === 'alto') {
			return $v >= $crit ? 'crit' : ($v >= $warn ? 'warn' : 'ok');
		}

		return $v <= $crit ? 'crit' : ($v <= $warn ? 'warn' : 'ok');
	}

	/** Horas aproximadas fuera de umbral a partir de la serie (cada punto pesa su intervalo). */
	private static function horasFueraDeUmbral(array $serie, ?string $sentido, $warn, $crit): array {
		if ($sentido === null || count($serie) < 2) {
			return [0.0, 0.0];
		}
		$w = 0;
		$c = 0;
		for ($i = 0; $i < count($serie) - 1; $i++) {
			$dt = $serie[$i + 1][0] - $serie[$i][0];
			$nivel = self::nivel($serie[$i][1], $sentido, $warn, $crit);
			if ($nivel === 'crit') {
				$c += $dt;
			}
			elseif ($nivel === 'warn') {
				$w += $dt;
			}
		}

		return [round($w / 3600, 1), round($c / 3600, 1)];
	}

	/** Interfaces descubiertas (airMAX / Mikrotik) con cambios de estado y errores del período. */
	private static function interfaces(array $items, int $from, int $to): array {
		$out = [];
		foreach ($items as $i) {
			if (!preg_match('/^(airmax|mikrotik)\.if\.([a-z]+)\[(.*)\]$/', $i['key_'], $m)) {
				continue;
			}
			[, , $metrica, $nombre] = $m;
			$out[$nombre]['nombre'] = $nombre;
			$out[$nombre][$metrica] = ($i['lastclock'] != 0 && is_numeric($i['lastvalue'])) ? (float) $i['lastvalue'] : null;
			$out[$nombre]['itemids'][$metrica] = $i['itemid'];
		}
		foreach ($out as $nombre => &$if) {
			$if['cambios'] = 0;
			$if['errores_max'] = 0.0;
			if (isset($if['itemids']['estado'])) {
				$hist = API::History()->get([
					'output' => ['value'], 'history' => ITEM_VALUE_TYPE_UINT64, 'itemids' => [$if['itemids']['estado']],
					'time_from' => $from, 'time_till' => $to, 'sortfield' => 'clock', 'sortorder' => ZBX_SORT_UP,
					'limit' => 5000
				]);
				$prev = null;
				foreach ($hist as $h) {
					if ($prev !== null && $h['value'] !== $prev) {
						$if['cambios']++;
					}
					$prev = $h['value'];
				}
			}
			foreach (['errin', 'errout'] as $k) {
				if (isset($if['itemids'][$k])) {
					$t = API::Trend()->get(['output' => ['value_max'], 'itemids' => [$if['itemids'][$k]],
						'time_from' => $from, 'time_till' => $to]);
					$vals = array_map('floatval', array_column($t, 'value_max'));
					if (isset($if[$k])) {
						$vals[] = (float) $if[$k];
					}
					$if['errores_max'] = max($if['errores_max'], $vals ? max($vals) : 0.0);
				}
			}
			$down = isset($if['estado']) && (int) $if['estado'] !== 1;
			$if['diagnostico'] = $down ? ['crit', 'Sin enlace: crítico']
				: ($if['cambios'] >= 3 ? ['warn', 'Inestable ('.$if['cambios'].' cambios)']
				: ($if['errores_max'] > 0 ? ['warn', 'Con errores'] : ['ok', 'Estable: normal']));
		}
		unset($if);
		ksort($out, SORT_NATURAL);

		return $out;
	}

	/** Estaciones asociadas (airMAX) con señal actual y mínima del período. */
	private static function estaciones(array $items, int $from, int $to): array {
		$out = [];
		foreach ($items as $i) {
			if (!preg_match('/^airmax\.sta\.([a-z]+)\[(.*)\]$/', $i['key_'], $m)) {
				continue;
			}
			[, $metrica, $idx] = $m;
			if (preg_match('/^Estación (.*): /u', $i['name'], $n)) {
				$out[$idx]['nombre'] = $n[1];
			}
			$out[$idx][$metrica] = ($i['lastclock'] != 0 && is_numeric($i['lastvalue'])) ? (float) $i['lastvalue'] : null;
			if ($metrica === 'senal') {
				$t = API::Trend()->get(['output' => ['value_min'], 'itemids' => [$i['itemid']],
					'time_from' => $from, 'time_till' => $to]);
				$out[$idx]['senal_min'] = $t ? min(array_map('floatval', array_column($t, 'value_min'))) : null;
			}
		}

		return $out;
	}

	/** Problemas del período agrupados por trigger, con flapping (3 o más apariciones). */
	private static function problemas(string $hostid, array $f): array {
		$sup = $f['mantenimiento'] === 'excluir' ? ['suppressed' => false] : [];
		$eventos = API::Event()->get([
			'output' => ['eventid', 'objectid', 'clock', 'r_eventid', 'name', 'severity', 'acknowledged'],
			'hostids' => [$hostid], 'source' => EVENT_SOURCE_TRIGGERS, 'object' => EVENT_OBJECT_TRIGGER,
			'value' => TRIGGER_VALUE_TRUE, 'time_from' => $f['from'] - 30 * 86400, 'time_till' => $f['to'],
			'selectTags' => ['tag', 'value'], 'sortfield' => ['clock'], 'sortorder' => ZBX_SORT_UP
		] + $sup);
		$r_ids = array_values(array_filter(array_column($eventos, 'r_eventid')));
		$r_clock = $r_ids ? array_column(API::Event()->get([
			'output' => ['eventid', 'clock'], 'eventids' => $r_ids
		]), 'clock', 'eventid') : [];

		$grupos = [];
		$individuales = [];
		$intervalos = [];
		foreach ($eventos as $ev) {
			$ini = (int) $ev['clock'];
			$fin = $ev['r_eventid'] != 0 ? (int) ($r_clock[$ev['r_eventid']] ?? $f['to']) : null;
			if (($fin ?? PHP_INT_MAX) <= $f['from']) {
				continue;
			}
			$dur = min($fin ?? $f['to'], $f['to']) - max($ini, $f['from']);
			$alcance = array_column($ev['tags'], 'value', 'tag')['alcance'] ?? '';
			$g = &$grupos[$ev['objectid']];
			$g['nombre'] = $ev['name'];
			$g['severidad'] = max($g['severidad'] ?? 0, (int) $ev['severity']);
			$g['categoria'] = self::CATEGORIAS[$alcance] ?? 'Otros';
			$g['veces'] = ($g['veces'] ?? 0) + 1;
			$g['segundos'] = ($g['segundos'] ?? 0) + $dur;
			$g['primero'] = min($g['primero'] ?? PHP_INT_MAX, $ini);
			$g['ultimo'] = max($g['ultimo'] ?? 0, $ini);
			$g['activo'] = ($g['activo'] ?? false) || $fin === null;
			$g['reconocido'] = ($g['reconocido'] ?? true) && $ev['acknowledged'] == 1;
			unset($g);
			$individuales[] = ['inicio' => $ini, 'fin' => $fin, 'nombre' => $ev['name'], 'severidad' => (int) $ev['severity'],
				'duracion' => ($fin ?? time()) - $ini];
			$intervalos[] = [max($ini, $f['from']), min($fin ?? $f['to'], $f['to'])];
		}
		foreach ($grupos as &$g) {
			$g['flapping'] = $g['veces'] >= 3;
			$dias = max(1, ($f['to'] - $f['from']) / 86400);
			$g['por_dia'] = $g['veces'] / $dias;
			$g['duracion_media'] = (int) round($g['segundos'] / $g['veces']);
		}
		unset($g);
		uasort($grupos, static fn($a, $b) => [$b['activo'], $b['severidad'], $b['veces']] <=> [$a['activo'], $a['severidad'], $a['veces']]);
		usort($individuales, static fn($a, $b) => $b['inicio'] <=> $a['inicio']);

		return [
			'grupos' => $grupos,
			'individuales' => array_slice($individuales, 0, 200),
			'total' => count($individuales),
			'activos' => count(array_filter($grupos, static fn($g) => $g['activo'])),
			'horas_evento' => array_sum(array_column($grupos, 'segundos')),
			'tiempo_afectado' => ReporteService::suma(ReporteService::unir($intervalos))
		];
	}

	private static function textos(array $por_key): array {
		$out = [];
		foreach (['airmax.sistema.modelo' => 'Modelo', 'airmax.sistema.firmware' => 'Firmware',
				'airmax.wl.ssid' => 'SSID', 'airmax.radio.frecuencia' => 'Frecuencia (MHz)',
				'airmax.wl.canal' => 'Ancho de canal (MHz)', 'mikrotik.sistema.modelo' => 'Modelo',
				'mikrotik.sistema.routeros' => 'RouterOS', 'mikrotik.sistema.serie' => 'Número de serie',
				'ap.modelo' => 'Modelo', 'ap.firmware' => 'Firmware'] as $k => $t) {
			if (isset($por_key[$k]) && $por_key[$k]['lastvalue'] !== '') {
				$out[$t] = $por_key[$k]['lastvalue'];
			}
		}

		return $out;
	}

	/** Conclusiones y recomendaciones según el comportamiento del período. */
	private static function conclusiones(array $m, ?array $fila, array $problemas): array {
		$out = [];
		$v = static fn(string $k, string $campo) => $m[$k][$campo] ?? null;
		$fmt = static fn(?float $x, int $d = 0) => $x === null ? '—' : number_format($x, $d, ',', '.');

		if ($fila && $fila['caida_propia'] > 0) {
			$out[] = ['crit', sprintf('El equipo estuvo caído %s en %d ocasión(es). Revisar alimentación '
				.'(batería/panel solar), el equipo y el enlace hacia %s.', ReporteService::duracion($fila['caida_propia']),
				$fila['incidentes'], $fila['padre'] ?: 'su equipo padre')];
		}
		if ($fila && $fila['caida_servicio'] > $fila['caida_propia']) {
			$out[] = ['warn', sprintf('Estuvo %s sin servicio por caídas de equipos aguas arriba (no es falla '
				.'propia): priorizar la robustez de %s.', ReporteService::duracion($fila['caida_servicio'] - $fila['caida_propia']),
				$fila['padre'] ?: 'la troncal')];
		}
		if (isset($m['airmax.wl.senal'])) {
			$prom = $v('airmax.wl.senal', 'promedio');
			if ($m['airmax.wl.senal']['nivel_pico'] !== 'ok') {
				$out[] = [$m['airmax.wl.senal']['nivel_pico'] === 'crit' ? 'crit' : 'warn', sprintf(
					'La señal llegó a %s dBm (promedio %s dBm). Revisar alineación de la antena, obstrucciones '
					.'(vegetación, construcciones) y la potencia de transmisión del otro extremo.',
					$fmt($v('airmax.wl.senal', 'minimo')), $fmt($prom))];
			}
			if (($m['airmax.wl.ruido']['nivel_pico'] ?? 'ok') !== 'ok') {
				$out[] = ['warn', sprintf('Se detectó interferencia: el piso de ruido llegó a %s dBm. Evaluar un '
					.'cambio de frecuencia o de ancho de canal con airView.', $fmt($v('airmax.wl.ruido', 'maximo')))];
			}
			if (($m['airmax.wl.ccq']['nivel_pico'] ?? 'ok') !== 'ok') {
				$out[] = ['warn', sprintf('CCQ mínimo de %s %%: hubo retransmisiones elevadas (interferencia o '
					.'señal marginal).', $fmt($v('airmax.wl.ccq', 'minimo')))];
			}
			if (($m['airmax.airmax.capacidad']['nivel_pico'] ?? 'ok') === 'crit') {
				$out[] = ['warn', sprintf('La capacidad airMAX bajó a %s %%: el enlace entregó una fracción baja '
					.'de su velocidad teórica.', $fmt($v('airmax.airmax.capacidad', 'minimo')))];
			}
		}
		if (isset($m['mikrotik.voltaje'])) {
			$min = $v('mikrotik.voltaje', 'minimo');
			if ($m['mikrotik.voltaje']['nivel_pico'] !== 'ok') {
				$out[] = [$m['mikrotik.voltaje']['nivel_pico'] === 'crit' ? 'crit' : 'warn', sprintf(
					'El voltaje de alimentación bajó a %s V: la batería entró en %s. Revisar panel solar '
					.'(suciedad, sombra), regulador de carga y estado de la batería.', $fmt($min, 2),
					$min !== null && $min <= 11.6 ? 'descarga profunda' : 'descarga moderada')];
			}
		}
		foreach (['airmax.cpu', 'mikrotik.cpu', 'ap.cpu.util'] as $k) {
			if (($m[$k]['nivel_pico'] ?? 'ok') === 'crit') {
				$out[] = ['warn', sprintf('Pico crítico de CPU (%s %%): correlacionar con picos de tráfico o '
					.'escaneos.', $fmt($v($k, 'maximo')))];
			}
		}
		foreach (['airmax.memoria.uso', 'mikrotik.memoria.uso', 'ap.mem.util'] as $k) {
			if (($m[$k]['nivel_pico'] ?? 'ok') === 'crit') {
				$out[] = ['warn', sprintf('Pico crítico de memoria (%s %%): considerar reiniciar o actualizar el '
					.'firmware.', $fmt($v($k, 'maximo')))];
			}
		}
		if (($m['icmppingloss']['nivel_pico'] ?? 'ok') !== 'ok') {
			$out[] = ['warn', sprintf('Pérdida de paquetes de hasta %s %%: posible saturación o enlace inestable.',
				$fmt($v('icmppingloss', 'maximo')))];
		}
		foreach ($problemas['grupos'] as $g) {
			if ($g['flapping']) {
				$out[] = ['warn', sprintf('Flapping: "%s" se repitió %d veces. Revisar la causa de fondo (umbral, '
					.'enlace intermitente o alimentación inestable).', $g['nombre'], $g['veces'])];
			}
		}
		if (!$out) {
			$out[] = ['ok', 'Sin observaciones: el equipo operó dentro de parámetros normales durante el período.'];
		}

		return $out;
	}
}
