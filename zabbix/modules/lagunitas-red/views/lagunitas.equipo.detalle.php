<?php declare(strict_types = 0);

/**
 * Contenido del modal "Detalle del equipo" (fragmento HTML, se inserta con JS).
 *
 * @var CView $this
 * @var array $data
 */

use Modules\LagunitasRed\Includes\{Html, RedService};

ob_start();
$equipos = $data['red']['equipos'];
$e = $equipos[$data['hostid']] ?? null;

if ($e === null) {
	ob_end_clean();
	echo json_encode(['body' => '<div class="lg-empty">Equipo no encontrado.</div>']);

	return;
}

$h = static fn($v) => Html::e($v);
$hid = $e['hostid'];
$it = $e['items'];
$hijos = RedService::descendientes($equipos, $hid);
$ancestros = RedService::ancestros($equipos, $hid);
$severidades = ['Sin clasificar', 'Información', 'Advertencia', 'Media', 'Alta', 'Desastre'];

$url = [
	'dashboard' => 'zabbix.php?action=host.dashboard.view&hostid='.$hid,
	'datos' => 'zabbix.php?action=latest.view&hostids%5B%5D='.$hid.'&filter_set=1',
	'problemas' => 'zabbix.php?action=problem.view&hostids%5B%5D='.$hid.'&filter_set=1',
	'config' => 'zabbix.php?action=host.edit&hostid='.$hid,
	'tecnico' => 'zabbix.php?action=lagunitas.reporte.equipo&periodo=7d&hostid='.$hid
];

$grafico = static function($items, string $titulo) use ($h): string {
	$items = array_values(array_filter(is_array($items) && array_key_exists('itemid', $items) ? [$items]
		: (array) $items));
	if (!$items) {
		return '';
	}
	$ids = '';
	foreach ($items as $item) {
		$ids .= 'itemids%5B%5D='.$item['itemid'].'&';
	}
	$src = 'chart.php?'.$ids.'type=0&profileIdx=web.item.graph.filter&profileIdx2='
		.$items[0]['itemid'].'&width=860&height=170&legend='.(count($items) > 1 ? 1 : 0);

	return '<figure class="lg-chart"><figcaption>'.$h($titulo).'</figcaption><img loading="lazy" alt="'
		.$h($titulo).'" data-lg-src="'.$h($src).'" src="'.$h($src.'&from=now-24h&to=now').'"></figure>';
};

// ---------------------------------------------------------------- encabezado
$subtitulo = [$e['ip'], $e['rol']];
if ($e['equipo'] !== '' && $e['equipo'] !== 'A relevar') {
	$subtitulo[] = $e['equipo'];
}
echo '<div class="lg-m-head"><div><h3>'.$h($e['nombre']).'</h3><p>'.$h(implode(' · ', $subtitulo))
	.'</p></div><div class="lg-m-head-r">'.Html::estado($e['estado']).'<button type="button" class="lg-m-close" '
	.'aria-label="Cerrar" data-lg-close>×</button></div></div>';

// --------------------------------------------------------------------- tabs
$tabs = ['resumen' => 'Resumen', 'problemas' => 'Problemas ('.count($e['problemas']).')',
	'rendimiento' => 'Rendimiento', 'dependencias' => 'Dependencias ('.count($hijos).')'];
$desc = $data['descubiertos'];
if ($e['tipo'] === 'airmax') {
	$tabs = array_slice($tabs, 0, 1, true) + ['radio' => 'Radio',
		'estaciones' => 'Estaciones ('.count($desc['estaciones']).')'] + array_slice($tabs, 1, null, true);
}
if ($e['tipo'] === 'mikrotik') {
	$tabs = array_slice($tabs, 0, 1, true) + ['router' => 'Router y energía'] + array_slice($tabs, 1, null, true);
}
if ($desc['interfaces']) {
	$tabs['interfaces'] = 'Interfaces ('.count($desc['interfaces']).')';
}
if ($e['es_ap']) {
	$tabs['unifi'] = 'UniFi';
}
echo '<div class="lg-tabs" role="tablist">';
foreach ($tabs as $k => $v) {
	echo '<button type="button" role="tab" data-lg-tab="'.$k.'"'.($k === 'resumen' ? ' class="is-active"' : '').'>'
		.$h($v).'</button>';
}
echo '</div><div class="lg-m-body">';

// ------------------------------------------------------------------ resumen
echo '<div class="lg-pane is-active" data-lg-pane="resumen"><div class="lg-kpis">';
$kpi = static function(string $t, string $v, string $nivel = '') use ($h): string {
	return '<div class="lg-kpi'.($nivel ? ' lg-k-'.$nivel : '').'"><span>'.$h($t).'</span><b>'.$h($v).'</b></div>';
};
if ($e['es_ap']) {
	$cpu = Html::valorItem($it, 'ap.cpu.util');
	$mem = Html::valorItem($it, 'ap.mem.util');
	$up = Html::valorItem($it, 'ap.uptime');
	echo $kpi('Estado UniFi', Html::textoItem($it, 'ap.estado'));
	echo $kpi('CPU', Html::num($cpu, 1, '%'), Html::nivelPct($cpu));
	echo $kpi('Memoria', Html::num($mem, 1, '%'), Html::nivelPct($mem));
	echo $kpi('Clientes', Html::num(Html::valorItem($it, 'ap.clients.count'), 0));
	echo $kpi('Uptime', $up !== null ? Html::duracion((int) $up) : '—');
}
else {
	echo $kpi('Latencia', Html::num($e['latencia_ms'], 1, 'ms'), Html::nivelLatencia($e['latencia_ms']));
	echo $kpi('Pérdida', Html::num($e['perdida'], 0, '%'), Html::nivelPerdida($e['perdida']));
	echo $kpi('Disponibilidad 24 h', Html::num($e['disp24'], 2, '%'), Html::nivelDisp($e['disp24']));
	echo $kpi('Disponibilidad 7 días', Html::num($e['disp7d'], 2, '%'), Html::nivelDisp($e['disp7d']));
	if ($e['tipo'] === 'airmax') {
		$senal = Html::valorItem($it, 'airmax.wl.senal');
		echo $kpi('Señal', Html::num($senal, 0, 'dBm'), Html::nivelSenal($senal));
		$ccq = Html::valorItem($it, 'airmax.wl.ccq');
		echo $kpi('CCQ', Html::num($ccq, 0, '%'), Html::nivelMin($ccq, 85, 70));
	}
	elseif ($e['tipo'] === 'mikrotik') {
		$v = Html::valorItem($it, 'mikrotik.voltaje');
		echo $kpi('Voltaje', Html::num($v, 1, 'V'), Html::nivelVoltaje($v));
		echo $kpi('Clientes DHCP', Html::num(Html::valorItem($it, 'mikrotik.dhcp.clientes'), 0));
	}
}
echo $kpi('Problemas activos', (string) count($e['problemas']), $e['problemas'] ? 'bad' : 'ok');
echo $kpi('Equipos que dependen', (string) count($hijos), count($hijos) ? 'info' : '');
echo '</div>';

$padre = $e['padre'] !== null && isset($equipos[$e['padre']]) ? $equipos[$e['padre']]['nombre'] : '— (raíz)';
$filas = [
	'Nombre técnico' => $e['host'],
	'IP de gestión' => $e['ip'] ?: '—',
	'Rol' => $e['rol'],
	'Función' => ['ap' => 'Punto de acceso (AP)', 'sm' => 'Estación (SM)', 'ptp' => 'Enlace punto a punto',
		'router' => 'Router', 'switch' => 'Switch'][$e['funcion']] ?? '—',
	'Modelo' => $e['modelo'] ?: (Html::textoItem($it, 'airmax.sistema.modelo') !== '—'
		? Html::textoItem($it, 'airmax.sistema.modelo') : Html::textoItem($it, 'mikrotik.sistema.modelo')),
	'Equipo instalado' => $e['equipo'] ?: '—',
	'Depende de' => $padre,
	'Estado del tramo' => $e['tramo'] ?: '—',
	'Grupos' => implode(', ', $e['grupos']),
	'Mantenimiento' => $e['mantenimiento'] ? 'Sí' : 'No'
];
if ($e['elemento'] !== $e['host'] && isset($equipos[$e['elemento']])) {
	$filas = ['Sitio' => $equipos[$e['elemento']]['nombre']] + $filas;
}
foreach (['airmax.sistema.firmware' => 'Firmware', 'mikrotik.sistema.routeros' => 'RouterOS'] as $k => $t) {
	if (Html::textoItem($it, $k) !== '—') {
		$filas[$t] = Html::textoItem($it, $k);
	}
}
if ($e['estado'] === 'afectado' && $e['causa']) {
	$filas['Causa'] = 'Sin servicio por caída de '.$equipos[$e['causa']]['nombre'];
}
echo '<dl class="lg-info">';
foreach ($filas as $k => $v) {
	echo '<div><dt>'.$h($k).'</dt><dd>'.$h($v).'</dd></div>';
}
echo '</dl><div class="lg-actions">'
	.'<a class="lg-btn" href="'.$h($url['tecnico']).'">Detalle técnico (7 días)</a>'
	.'<a class="lg-btn" href="'.$h($url['dashboard']).'">Dashboard del equipo</a>'
	.'<a class="lg-btn" href="'.$h($url['datos']).'">Últimos datos</a>'
	.'<a class="lg-btn" href="'.$h($url['problemas']).'">Problemas en Zabbix</a>'
	.'<a class="lg-btn lg-btn-ghost" href="'.$h($url['config']).'">Configuración</a></div></div>';

// ---------------------------------------------------------------- problemas
echo '<div class="lg-pane" data-lg-pane="problemas">';
if ($e['problemas']) {
	echo '<h5>Activos</h5><table class="lg-table lg-table-sm"><thead><tr><th>Severidad</th><th>Problema</th>'
		.'<th>Desde</th><th>Duración</th><th>Reconocido</th></tr></thead><tbody>';
	foreach ($e['problemas'] as $p) {
		echo '<tr><td><span class="lg-sev lg-sev-'.(int) $p['severity'].'">'.$h($severidades[$p['severity']])
			.'</span></td><td>'.$h($p['name']).'</td><td>'.$h(date('d/m H:i', (int) $p['clock'])).'</td><td>'
			.$h(Html::duracion(time() - (int) $p['clock'])).'</td><td>'.($p['acknowledged'] ? 'Sí' : 'No')
			.'</td></tr>';
	}
	echo '</tbody></table>';
}
else {
	echo '<div class="lg-ok-msg">Sin problemas activos.</div>';
}
echo '<h5>Incidentes de los últimos 30 días</h5>';
if ($data['eventos']) {
	echo '<table class="lg-table lg-table-sm"><thead><tr><th>Severidad</th><th>Problema</th><th>Inicio</th>'
		.'<th>Fin</th><th>Duración</th></tr></thead><tbody>';
	foreach ($data['eventos'] as $ev) {
		$fin = $ev['r_clock'];
		$dur = ($fin ?: time()) - (int) $ev['clock'];
		echo '<tr><td><span class="lg-sev lg-sev-'.(int) $ev['severity'].'">'.$h($severidades[$ev['severity']])
			.'</span></td><td>'.$h($ev['name']).'</td><td>'.$h(date('d/m/Y H:i', (int) $ev['clock'])).'</td><td>'
			.($fin ? $h(date('d/m/Y H:i', $fin)) : '<b>en curso</b>').'</td><td>'.$h(Html::duracion($dur))
			.'</td></tr>';
	}
	echo '</tbody></table>';
}
else {
	echo '<div class="lg-muted">Sin incidentes registrados.</div>';
}
echo '</div>';

// -------------------------------------------------------------- rendimiento
echo '<div class="lg-pane" data-lg-pane="rendimiento"><div class="lg-range" role="group" aria-label="Período">';
foreach (['now-1h' => '1 h', 'now-24h' => '24 h', 'now-7d' => '7 días', 'now-30d' => '30 días'] as $k => $v) {
	echo '<button type="button" data-lg-range="'.$h($k).'"'.($k === 'now-24h' ? ' class="is-active"' : '').'>'
		.$h($v).'</button>';
}
echo '</div>';
if ($e['es_ap']) {
	echo $grafico($it['ap.cpu.util'] ?? null, 'Uso de CPU');
	echo $grafico($it['ap.mem.util'] ?? null, 'Uso de memoria');
	echo $grafico($it['ap.clients.count'] ?? null, 'Clientes conectados');
	echo $grafico($it['ap.uplink.rx'] ?? null, 'Uplink RX');
	echo $grafico($it['ap.radio.5ghz.retries'] ?? null, 'Reintentos TX 5 GHz');
}
else {
	if ($e['tipo'] === 'airmax') {
		echo $grafico([$it['airmax.wl.senal'] ?? null, $it['airmax.wl.ruido'] ?? null], 'Señal y piso de ruido (dBm)');
		echo $grafico([$it['airmax.wl.ccq'] ?? null, $it['airmax.airmax.calidad'] ?? null,
			$it['airmax.airmax.capacidad'] ?? null], 'CCQ, calidad y capacidad airMAX (%)');
		echo $grafico([$it['airmax.wl.tx'] ?? null, $it['airmax.wl.rx'] ?? null], 'Tasas de modulación TX / RX');
	}
	if ($e['tipo'] === 'mikrotik') {
		echo $grafico($it['mikrotik.voltaje'] ?? null, 'Voltaje de alimentación (V)');
		echo $grafico($it['mikrotik.dhcp.clientes'] ?? null, 'Clientes DHCP activos');
		echo $grafico([$it['mikrotik.cpu'] ?? null, $it['mikrotik.memoria.uso'] ?? null], 'CPU y memoria (%)');
	}
	echo $grafico($it['icmppingsec'] ?? null, 'Latencia (ICMP)');
	echo $grafico($it['icmppingloss'] ?? null, 'Pérdida de paquetes (ICMP)');
	echo $grafico($it['icmpping'] ?? null, 'Disponibilidad (1 = activo, 0 = caído)');
}
echo '</div>';

// -------------------------------------------------------------------- radio
if ($e['tipo'] === 'airmax') {
	$v = static fn(string $k) => Html::valorItem($it, $k);
	echo '<div class="lg-pane" data-lg-pane="radio"><div class="lg-kpis">';
	echo $kpi('Señal', Html::num($v('airmax.wl.senal'), 0, 'dBm'), Html::nivelSenal($v('airmax.wl.senal')));
	echo $kpi('Piso de ruido', Html::num($v('airmax.wl.ruido'), 0, 'dBm'),
		$v('airmax.wl.ruido') === null ? '' : ($v('airmax.wl.ruido') > -85 ? 'warn' : 'ok'));
	echo $kpi('SNR', Html::num($v('airmax.wl.snr'), 0, 'dB'), Html::nivelMin($v('airmax.wl.snr'), 25, 15));
	echo $kpi('CCQ', Html::num($v('airmax.wl.ccq'), 0, '%'), Html::nivelMin($v('airmax.wl.ccq'), 85, 70));
	echo $kpi('Calidad airMAX', Html::num($v('airmax.airmax.calidad'), 0, '%'),
		Html::nivelMin($v('airmax.airmax.calidad'), 75, 60));
	echo $kpi('Capacidad airMAX', Html::num($v('airmax.airmax.capacidad'), 0, '%'),
		Html::nivelMin($v('airmax.airmax.capacidad'), 60, 40));
	echo '</div><dl class="lg-info">';
	$modo = [1 => 'Estación (SM)', 2 => 'Punto de acceso (AP)', 3 => 'AP repetidor', 4 => 'AP WDS'];
	foreach ([
		'Modo' => $modo[(int) $v('airmax.radio.modo')] ?? '—',
		'SSID' => Html::textoItem($it, 'airmax.wl.ssid'),
		'Frecuencia' => Html::num($v('airmax.radio.frecuencia'), 0, 'MHz'),
		'Ancho de canal' => Html::num($v('airmax.wl.canal'), 0, 'MHz'),
		'Potencia de transmisión' => Html::num($v('airmax.radio.potencia'), 0, 'dBm'),
		'Distancia configurada' => Html::num($v('airmax.radio.distancia'), 0, 'm'),
		'Antena' => Html::textoItem($it, 'airmax.radio.antena'),
		'DFS' => $v('airmax.radio.dfs') === null ? '—' : ($v('airmax.radio.dfs') ? 'Habilitado' : 'Deshabilitado'),
		'Tasa TX / RX' => Html::bps($v('airmax.wl.tx')).' / '.Html::bps($v('airmax.wl.rx')),
		'Estaciones asociadas' => Html::num($v('airmax.wl.estaciones'), 0),
		'CPU / memoria' => Html::num($v('airmax.cpu'), 0, '%').' / '.Html::num($v('airmax.memoria.uso'), 0, '%'),
		'Temperatura' => Html::num($v('airmax.temperatura'), 0, '°C'),
		'Firmware airOS' => Html::textoItem($it, 'airmax.sistema.firmware'),
		'Uptime' => $v('airmax.sistema.uptime') !== null ? Html::duracion((int) $v('airmax.sistema.uptime')) : '—'
	] as $k => $x) {
		echo '<div><dt>'.$h($k).'</dt><dd>'.$h($x).'</dd></div>';
	}
	echo '</dl><p class="lg-muted lg-nota">Referencia: señal buena entre -50 y -65 dBm (aceptable hasta -75); '
		.'SNR &gt; 25 dB; CCQ &gt; 85 %; ruido normal entre -90 y -100 dBm. Las tasas TX/RX son de modulación, '
		.'no tráfico real.</p></div>';

	// -------------------------------------------------------------- estaciones
	echo '<div class="lg-pane" data-lg-pane="estaciones">';
	if ($desc['estaciones']) {
		echo '<table class="lg-table lg-table-sm"><thead><tr><th>Estación</th><th>Señal</th><th>Ruido</th>'
			.'<th>CCQ</th><th>Calidad</th><th>Capacidad</th><th>TX / RX</th><th>Distancia</th><th>Latencia</th>'
			.'<th>Conectada</th></tr></thead><tbody>';
		foreach ($desc['estaciones'] as $st) {
			echo '<tr><td><b>'.$h($st['nombre'] ?? '—').'</b></td>'
				.'<td class="lg-t-'.Html::nivelSenal($st['senal'] ?? null).'"><b>'.$h(Html::num($st['senal'] ?? null, 0, 'dBm')).'</b></td>'
				.'<td>'.$h(Html::num($st['ruido'] ?? null, 0, 'dBm')).'</td>'
				.'<td class="lg-t-'.Html::nivelMin($st['ccq'] ?? null, 85, 70).'">'.$h(Html::num($st['ccq'] ?? null, 0, '%')).'</td>'
				.'<td>'.$h(Html::num($st['calidad'] ?? null, 0, '%')).'</td>'
				.'<td>'.$h(Html::num($st['capacidad'] ?? null, 0, '%')).'</td>'
				.'<td>'.$h(Html::bps($st['tx'] ?? null).' / '.Html::bps($st['rx'] ?? null)).'</td>'
				.'<td>'.$h(Html::num($st['distancia'] ?? null, 0, 'm')).'</td>'
				.'<td>'.$h(Html::num($st['latencia'] ?? null, 0, 'ms')).'</td>'
				.'<td>'.(isset($st['conexion']) ? $h(Html::duracion((int) $st['conexion'])) : '—').'</td></tr>';
		}
		echo '</tbody></table>';
		$primera = reset($desc['estaciones']);
		if (!empty($primera['itemids']['senal'])) {
			$ids = array_map(static fn($st) => ['itemid' => $st['itemids']['senal'] ?? null],
				array_filter($desc['estaciones'], static fn($st) => !empty($st['itemids']['senal'])));
			echo $grafico(array_values($ids), 'Señal por estación (dBm)');
		}
	}
	else {
		echo '<div class="lg-muted">Todavía no se descubrieron estaciones (el descubrimiento corre cada 10 min).</div>';
	}
	echo '</div>';
}

// ------------------------------------------------------------------- router
if ($e['tipo'] === 'mikrotik') {
	$v = static fn(string $k) => Html::valorItem($it, $k);
	echo '<div class="lg-pane" data-lg-pane="router"><div class="lg-kpis">';
	echo $kpi('Voltaje', Html::num($v('mikrotik.voltaje'), 1, 'V'), Html::nivelVoltaje($v('mikrotik.voltaje')));
	echo $kpi('CPU', Html::num($v('mikrotik.cpu'), 0, '%'), Html::nivelPct($v('mikrotik.cpu')));
	echo $kpi('Memoria', Html::num($v('mikrotik.memoria.uso'), 0, '%'), Html::nivelPct($v('mikrotik.memoria.uso')));
	echo $kpi('Temperatura', Html::num($v('mikrotik.temperatura'), 0, '°C'),
		$v('mikrotik.temperatura') === null ? '' : ($v('mikrotik.temperatura') > 65 ? 'bad' : 'ok'));
	echo $kpi('Clientes DHCP', Html::num($v('mikrotik.dhcp.clientes'), 0));
	foreach ($desc['wan'] as $w) {
		echo $kpi('Internet ('.$w['nombre'].')', $w['estado'] === null ? '—' : ((int) $w['estado'] === 1 ? 'Conectado' : 'Caído'),
			$w['estado'] === null ? '' : ((int) $w['estado'] === 1 ? 'ok' : 'bad'));
	}
	echo '</div><dl class="lg-info">';
	foreach ([
		'Modelo' => Html::textoItem($it, 'mikrotik.sistema.modelo'),
		'RouterOS' => Html::textoItem($it, 'mikrotik.sistema.routeros'),
		'Firmware (RouterBOOT)' => Html::textoItem($it, 'mikrotik.sistema.firmware'),
		'Número de serie' => Html::textoItem($it, 'mikrotik.sistema.serie'),
		'Temperatura de CPU' => Html::num($v('mikrotik.temperatura.cpu'), 0, '°C'),
		'Uptime' => $v('mikrotik.sistema.uptime') !== null ? Html::duracion((int) $v('mikrotik.sistema.uptime')) : '—'
	] as $k => $x) {
		echo '<div><dt>'.$h($k).'</dt><dd>'.$h($x).'</dd></div>';
	}
	echo '</dl><p class="lg-muted lg-nota">Batería VRLA de 12 V: 12,7 V ≈ 100 %, 12,2 V ≈ 50 %, '
		.'por debajo de 11,8 V descarga profunda. Por encima de 14,8 V revisar el regulador de carga.</p></div>';
}

// --------------------------------------------------------------- interfaces
if ($desc['interfaces']) {
	$oper = [1 => 'up', 2 => 'down', 3 => 'testing', 4 => 'desconocido', 5 => 'dormant', 6 => 'no presente',
		7 => 'capa inferior caída'];
	echo '<div class="lg-pane" data-lg-pane="interfaces"><table class="lg-table lg-table-sm"><thead><tr>'
		.'<th>Interfaz</th><th>Estado</th><th>Entrante</th><th>Saliente</th><th>Errores entrada/salida</th>'
		.'<th>Velocidad</th></tr></thead><tbody>';
	foreach ($desc['interfaces'] as $if) {
		$est = $if['estado'] ?? null;
		echo '<tr><td><b>'.$h($if['nombre']).'</b></td><td>'
			.($est === null ? '—' : '<span class="lg-badge lg-badge-'.((int) $est === 1 ? 'ok' : 'bad').'">'
				.$h($oper[(int) $est] ?? $est).'</span>')
			.'</td><td>'.$h(Html::bps($if['in'] ?? null)).'</td><td>'.$h(Html::bps($if['out'] ?? null)).'</td><td>'
			.$h(Html::num($if['errin'] ?? null, 1).' / '.Html::num($if['errout'] ?? null, 1)).'</td><td>'
			.$h(Html::bps($if['velocidad'] ?? null)).'</td></tr>';
	}
	echo '</tbody></table>';
	$trafico = [];
	foreach ($desc['interfaces'] as $if) {
		foreach (['in', 'out'] as $k) {
			if (!empty($if['itemids'][$k]) && ($if['in'] ?? 0) + ($if['out'] ?? 0) > 0) {
				$trafico[] = ['itemid' => $if['itemids'][$k]];
			}
		}
	}
	echo $grafico(array_slice($trafico, 0, 8), 'Tráfico por interfaz (bps)');
	echo '</div>';
}

// ------------------------------------------------------------- dependencias
echo '<div class="lg-pane" data-lg-pane="dependencias">';
echo '<h5>Camino hacia el backbone</h5><ol class="lg-path">';
foreach (array_reverse($ancestros) as $a) {
	echo '<li>'.Html::estado($equipos[$a]['estado']).' <a href="#" data-lg-host="'.$h($a).'">'
		.$h($equipos[$a]['nombre']).'</a></li>';
}
echo '<li class="is-self">'.Html::estado($e['estado']).' <b>'.$h($e['nombre']).'</b></li></ol>';
echo '<h5>Si este equipo cae, quedan sin servicio ('.count($hijos).')</h5>';
if ($hijos) {
	echo '<table class="lg-table lg-table-sm"><thead><tr><th>Estado</th><th>Equipo</th><th>Rol</th><th>Depende de</th>'
		.'</tr></thead><tbody>';
	foreach ($hijos as $c) {
		$x = $equipos[$c];
		echo '<tr><td>'.Html::estado($x['estado']).'</td><td><a href="#" data-lg-host="'.$h($c).'">'
			.$h($x['nombre']).'</a></td><td>'.$h($x['rol']).'</td><td>'
			.$h($equipos[$x['padre']]['nombre'] ?? '—').'</td></tr>';
	}
	echo '</tbody></table>';
}
else {
	echo '<div class="lg-muted">Ningún equipo depende de este (extremo de la red).</div>';
}
echo '</div>';

// ------------------------------------------------------------------- UniFi
if ($e['es_ap']) {
	$ctrl = Html::valorItem($it, 'net.tcp.service[https,{$UNIFI.HOST},{$UNIFI.PORT}]');
	echo '<div class="lg-pane" data-lg-pane="unifi"><dl class="lg-info">';
	foreach ([
		'Estado informado' => Html::textoItem($it, 'ap.estado'),
		'Modelo' => Html::textoItem($it, 'ap.modelo'),
		'Firmware' => Html::textoItem($it, 'ap.firmware'),
		'Controlador UniFi' => $ctrl === null ? '—' : ($ctrl ? 'Accesible' : 'No accesible'),
		'Reintentos 2.4 GHz' => Html::num(Html::valorItem($it, 'ap.radio.24ghz.retries'), 1, '%'),
		'Reintentos 5 GHz' => Html::num(Html::valorItem($it, 'ap.radio.5ghz.retries'), 1, '%'),
		'Reintentos 6 GHz' => Html::num(Html::valorItem($it, 'ap.radio.6ghz.retries'), 1, '%'),
		'Uplink RX / TX' => Html::num(Html::valorItem($it, 'ap.uplink.rx') !== null
			? Html::valorItem($it, 'ap.uplink.rx') / 1000 : null, 1, 'kbps').' / '
			.Html::num(Html::valorItem($it, 'ap.uplink.tx') !== null
			? Html::valorItem($it, 'ap.uplink.tx') / 1000 : null, 1, 'kbps')
	] as $k => $v) {
		echo '<div><dt>'.$h($k).'</dt><dd>'.$h($v).'</dd></div>';
	}
	echo '</dl></div>';
}

echo '</div>';

echo json_encode(['body' => ob_get_clean()]);
