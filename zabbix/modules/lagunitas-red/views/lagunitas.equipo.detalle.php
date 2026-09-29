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
	'config' => 'zabbix.php?action=host.edit&hostid='.$hid
];

$grafico = static function(?array $item, string $titulo) use ($h): string {
	if ($item === null) {
		return '';
	}
	$src = 'chart.php?itemids%5B%5D='.$item['itemid'].'&type=0&profileIdx=web.item.graph.filter&profileIdx2='
		.$item['itemid'].'&width=860&height=170&legend=0';

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
if ($e['es_ap']) {
	$tabs['unifi'] = 'UniFi';
}
echo '<nav class="lg-tabs" role="tablist">';
foreach ($tabs as $k => $v) {
	echo '<button type="button" role="tab" data-lg-tab="'.$k.'"'.($k === 'resumen' ? ' class="is-active"' : '').'>'
		.$h($v).'</button>';
}
echo '</nav><div class="lg-m-body">';

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
}
echo $kpi('Problemas activos', (string) count($e['problemas']), $e['problemas'] ? 'bad' : 'ok');
echo $kpi('Equipos que dependen', (string) count($hijos), count($hijos) ? 'info' : '');
echo '</div>';

$padre = $e['padre'] !== null && isset($equipos[$e['padre']]) ? $equipos[$e['padre']]['nombre'] : '— (raíz)';
$filas = [
	'Nombre técnico' => $e['host'],
	'IP de gestión' => $e['ip'] ?: '—',
	'Rol' => $e['rol'],
	'Equipo instalado' => $e['equipo'] ?: '—',
	'Depende de' => $padre,
	'Estado del tramo' => $e['tramo'] ?: '—',
	'Grupos' => implode(', ', $e['grupos']),
	'Mantenimiento' => $e['mantenimiento'] ? 'Sí' : 'No'
];
if ($e['estado'] === 'afectado' && $e['causa']) {
	$filas['Causa'] = 'Sin servicio por caída de '.$equipos[$e['causa']]['nombre'];
}
echo '<dl class="lg-info">';
foreach ($filas as $k => $v) {
	echo '<div><dt>'.$h($k).'</dt><dd>'.$h($v).'</dd></div>';
}
echo '</dl><div class="lg-actions">'
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
	echo $grafico($it['icmppingsec'] ?? null, 'Latencia (ICMP)');
	echo $grafico($it['icmppingloss'] ?? null, 'Pérdida de paquetes (ICMP)');
	echo $grafico($it['icmpping'] ?? null, 'Disponibilidad (1 = activo, 0 = caído)');
}
echo '</div>';

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
