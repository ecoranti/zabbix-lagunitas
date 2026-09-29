<?php declare(strict_types = 0);

namespace Modules\LagunitasRed\Includes;

/**
 * Generación de HTML del widget y del detalle de equipo (con escape de todo dato dinámico).
 */
class Html {

	public static function e($v): string {
		return htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');
	}

	public static function estado(string $estado, ?string $extra = null): string {
		$txt = RedService::ESTADOS[$estado]['texto'] ?? $estado;

		return '<span class="lg-estado lg-e-'.self::e($estado).'"><i></i>'.self::e($txt).'</span>'
			.($extra !== null ? '<small class="lg-sub">'.self::e($extra).'</small>' : '');
	}

	public static function num(?float $v, int $dec = 1, string $unidad = ''): string {
		if ($v === null) {
			return '—';
		}

		return number_format($v, $dec, ',', '.').($unidad !== '' ? ' '.$unidad : '');
	}

	/** Barra horizontal con nivel de severidad (ok / warn / bad). */
	public static function barra(?float $valor, float $max, string $nivel, string $texto): string {
		if ($valor === null) {
			return '<div class="lg-bar-wrap"><div class="lg-bar lg-bar-vacia"></div><span class="lg-bar-val">—</span></div>';
		}
		$pct = max(2, min(100, $valor / $max * 100));

		return '<div class="lg-bar-wrap"><div class="lg-bar"><span class="lg-n-'.$nivel.'" style="width:'
			.number_format($pct, 1, '.', '').'%"></span></div><span class="lg-bar-val">'.self::e($texto).'</span></div>';
	}

	public static function nivelLatencia(?float $ms): string {
		return $ms === null ? 'na' : ($ms >= 150 ? 'bad' : ($ms >= 100 ? 'warn' : 'ok'));
	}

	public static function nivelPerdida(?float $p): string {
		return $p === null ? 'na' : ($p >= 20 ? 'bad' : ($p >= 5 ? 'warn' : 'ok'));
	}

	public static function nivelDisp(?float $d): string {
		return $d === null ? 'na' : ($d < 95 ? 'bad' : ($d < 99.5 ? 'warn' : 'ok'));
	}

	public static function nivelPct(?float $v): string {
		return $v === null ? 'na' : ($v >= 85 ? 'bad' : ($v >= 60 ? 'warn' : 'ok'));
	}

	public static function problemasBadge(array $problemas): string {
		if (!$problemas) {
			return '<span class="lg-muted">—</span>';
		}
		$criticos = count(array_filter($problemas, static fn($p) => $p['severity'] >= TRIGGER_SEVERITY_HIGH));
		$resto = count($problemas) - $criticos;
		$out = '';
		if ($criticos) {
			$out .= '<span class="lg-badge lg-badge-bad">'.$criticos.' '.($criticos == 1 ? 'crítico' : 'críticos').'</span>';
		}
		if ($resto) {
			$out .= '<span class="lg-badge lg-badge-warn">'.$resto.' '.($resto == 1 ? 'advertencia' : 'advertencias')
				.'</span>';
		}

		return $out;
	}

	public static function duracion(int $seg): string {
		if ($seg < 60) {
			return $seg.' s';
		}
		$d = intdiv($seg, 86400);
		$h = intdiv($seg % 86400, 3600);
		$m = intdiv($seg % 3600, 60);
		if ($d) {
			return $d.' d '.$h.' h';
		}

		return $h ? $h.' h '.$m.' min' : $m.' min';
	}

	public static function tarjetas(array $r): string {
		$tarjetas = [
			['todos', $r['total'], 'Total', 'tot'],
			['ok', $r['ok'], 'En línea', 'ok'],
			['advertencia', $r['advertencia'], 'Advertencias', 'warn'],
			['caido', $r['caido'], 'Caídos', 'bad'],
			['afectado', $r['afectado'], 'Sin servicio', 'aff'],
			['sindatos', $r['sindatos'], 'Sin datos', 'na'],
			['nomon', $r['nomon'] + $r['mantenimiento'], 'No monitoreados', 'off']
		];
		$out = '<div class="lg-cards">';
		foreach ($tarjetas as [$filtro, $n, $txt, $cls]) {
			$out .= '<button type="button" class="lg-card lg-c-'.$cls.($filtro === 'todos' ? ' is-active' : '')
				.'" data-lg-filter="'.$filtro.'"><b>'.(int) $n.'</b><span>'.self::e($txt).'</span></button>';
		}

		return $out.'</div>';
	}

	public static function barraFiltros(int $total): string {
		$chips = [
			'todos' => 'Todos', 'caido' => 'Caídos', 'afectado' => 'Sin servicio', 'advertencia' => 'Advertencias',
			'sindatos' => 'Sin datos', 'nomon' => 'No monitoreados', 'rol:Torre' => 'Torres',
			'rol:Nodo intermedio' => 'Nodos', 'rol:Hogar' => 'Hogares', 'rol:Institución' => 'Instituciones'
		];
		$out = '<div class="lg-toolbar"><div class="lg-search"><input type="search" class="lg-q" '
			.'placeholder="Buscar equipo, IP o rol…" aria-label="Buscar equipo"><span class="lg-count">'
			.$total.' equipos</span></div><div class="lg-chips">';
		foreach ($chips as $k => $v) {
			$out .= '<button type="button" class="lg-chip'.($k === 'todos' ? ' is-active' : '').'" data-lg-filter="'
				.self::e($k).'">'.self::e($v).'</button>';
		}

		return $out.'</div></div>';
	}

	public static function seccion(string $titulo, array $ids, array $equipos): string {
		$es_ap = $ids && $equipos[$ids[0]]['es_ap'];
		$icono = 'N';
		foreach (RedService::SECCIONES as $s) {
			if ($s['titulo'] === $titulo) {
				$icono = $s['icono'];
				break;
			}
		}
		$out = '<section class="lg-sec"><div class="lg-sec-head"><span class="lg-sec-ico">'.self::e($icono).'</span><h4>'
			.self::e($titulo).'</h4><span class="lg-pill">'.count($ids).'</span></div>'
			.'<div class="lg-table-wrap"><table class="lg-table lg-table-red"><colgroup><col style="width:13%">'
			.'<col style="width:21%"><col style="width:13%"><col style="width:11%"><col style="width:10%">'
			.'<col style="width:13%"><col style="width:10%"><col style="width:9%"></colgroup>'
			.'<thead><tr><th>Estado</th><th>Equipo</th>';
		$out .= $es_ap
			? '<th>CPU</th><th>Memoria</th><th>Clientes</th><th>Uptime</th><th>Controlador</th><th></th>'
			: '<th>Disponibilidad 24 h</th><th>Latencia</th><th>Pérdida</th><th>Enlace / energía</th>'
				.'<th>Depende de</th>';
		$out .= '<th>Problemas</th></tr></thead><tbody>';

		foreach ($ids as $hid) {
			$e = $equipos[$hid];
			$busqueda = mb_strtolower($e['nombre'].' '.$e['host'].' '.$e['ip'].' '.$e['rol'].' '.$e['equipo'].' '
				.$e['modelo'].' '.$e['funcion']);
			$extra = null;
			if ($e['estado'] === 'afectado' && $e['causa']) {
				$extra = 'por '.$equipos[$e['causa']]['nombre'];
			}
			elseif ($e['estado'] === 'nomon' && $e['tramo'] !== '') {
				$extra = $e['tramo'];
			}
			elseif ($e['estado'] === 'caido' && $e['caida_desde']) {
				$extra = 'hace '.self::duracion(time() - $e['caida_desde']);
			}

			$out .= '<tr class="lg-row lg-r-'.self::e($e['estado']).'" tabindex="0" data-hostid="'.self::e($hid)
				.'" data-estado="'.self::e($e['estado']).'" data-rol="'.self::e($e['rol']).'" data-q="'.self::e($busqueda)
				.'">';
			$out .= '<td>'.self::estado($e['estado'], $extra).'</td>';
			$detalle = $e['modelo'] !== '' ? $e['modelo'] : ($e['equipo'] !== 'A relevar' ? $e['equipo'] : '');
			$out .= '<td><div class="lg-host"><b>'.self::e($e['nombre']).'</b><small>'.self::e($e['ip'])
				.($detalle !== '' ? ' · '.self::e($detalle) : '').'</small></div></td>';

			if ($es_ap) {
				$it = $e['items'];
				$cpu = self::valorItem($it, 'ap.cpu.util');
				$mem = self::valorItem($it, 'ap.mem.util');
				$cli = self::valorItem($it, 'ap.clients.count');
				$up = self::valorItem($it, 'ap.uptime');
				$out .= '<td>'.self::barra($cpu, 100, self::nivelPct($cpu), self::num($cpu, 1, '%')).'</td>';
				$out .= '<td>'.self::barra($mem, 100, self::nivelPct($mem), self::num($mem, 1, '%')).'</td>';
				$out .= '<td class="lg-big">'.self::num($cli, 0).'</td>';
				$out .= '<td>'.($up !== null ? self::e(self::duracion((int) $up)) : '—').'</td>';
				$ctrl = self::valorItem($it, 'net.tcp.service[https,{$UNIFI.HOST},{$UNIFI.PORT}]');
				$out .= '<td>'.($ctrl === null ? '—' : ($ctrl ? '<span class="lg-badge lg-badge-ok">Accesible</span>'
					: '<span class="lg-badge lg-badge-bad">No accesible</span>')).'</td><td></td>';
			}
			else {
				$out .= '<td>'.self::barra($e['disp24'], 100, self::nivelDisp($e['disp24']),
					self::num($e['disp24'], 2, '%')).'</td>';
				$out .= '<td>'.self::barra($e['latencia_ms'] !== null ? min($e['latencia_ms'], 200) : null, 200,
					self::nivelLatencia($e['latencia_ms']), self::num($e['latencia_ms'], 1, 'ms')).'</td>';
				$out .= '<td>'.self::barra($e['perdida'] !== null ? max($e['perdida'], 0.0) : null, 100,
					self::nivelPerdida($e['perdida']), self::num($e['perdida'], 0, '%')).'</td>';
				$out .= '<td>'.self::enlace($e).'</td>';
				$padre = $e['padre'] !== null && isset($equipos[$e['padre']]) ? $equipos[$e['padre']]['nombre'] : '—';
				$out .= '<td class="lg-muted">'.self::e($padre).'</td>';
			}
			$out .= '<td>'.self::problemasBadge($e['problemas']).'</td></tr>';
		}

		return $out.'</tbody></table></div></section>';
	}

	/** Métrica clave según el tipo de equipo: señal/CCQ (airMAX) o voltaje/DHCP (Mikrotik). */
	public static function enlace(array $e): string {
		$it = $e['items'];
		if ($e['tipo'] === 'airmax') {
			$senal = self::valorItem($it, 'airmax.wl.senal');
			$ccq = self::valorItem($it, 'airmax.wl.ccq');
			if ($senal === null) {
				return '<span class="lg-muted">—</span>';
			}

			return '<div class="lg-metric"><b class="lg-t-'.self::nivelSenal($senal).'">'.self::num($senal, 0, 'dBm')
				.'</b><small>CCQ '.self::num($ccq, 0, '%').'</small></div>';
		}
		if ($e['tipo'] === 'mikrotik') {
			$v = self::valorItem($it, 'mikrotik.voltaje');
			$dhcp = self::valorItem($it, 'mikrotik.dhcp.clientes');

			return '<div class="lg-metric"><b class="lg-t-'.self::nivelVoltaje($v).'">'.self::num($v, 1, 'V')
				.'</b><small>'.self::num($dhcp, 0).' clientes DHCP</small></div>';
		}

		return '<span class="lg-muted">—</span>';
	}

	public static function nivelSenal(?float $dbm): string {
		return $dbm === null ? 'na' : ($dbm < -80 ? 'bad' : ($dbm < -72 ? 'warn' : 'ok'));
	}

	public static function nivelVoltaje(?float $v): string {
		return $v === null ? 'na' : (($v < 11.6 || $v > 14.8) ? 'bad' : ($v < 12.0 ? 'warn' : 'ok'));
	}

	public static function nivelMin(?float $v, float $warn, float $bad): string {
		return $v === null ? 'na' : ($v < $bad ? 'bad' : ($v < $warn ? 'warn' : 'ok'));
	}

	/** Bits por segundo en formato legible. */
	public static function bps(?float $v): string {
		if ($v === null) {
			return '—';
		}
		foreach ([[1e9, 'Gbps'], [1e6, 'Mbps'], [1e3, 'Kbps']] as [$div, $u]) {
			if (abs($v) >= $div) {
				return number_format($v / $div, $v / $div >= 100 ? 0 : 1, ',', '.').' '.$u;
			}
		}

		return number_format($v, 0, ',', '.').' bps';
	}

	public static function valorItem(array $items, string $key): ?float {
		$i = $items[$key] ?? null;
		if ($i === null || $i['lastclock'] == 0 || !is_numeric($i['lastvalue'])) {
			return null;
		}

		return (float) $i['lastvalue'];
	}

	public static function textoItem(array $items, string $key): string {
		$i = $items[$key] ?? null;

		return ($i === null || $i['lastclock'] == 0 || $i['lastvalue'] === '') ? '—' : (string) $i['lastvalue'];
	}
}
