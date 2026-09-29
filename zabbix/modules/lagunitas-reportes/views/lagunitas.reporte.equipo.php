<?php declare(strict_types = 0);

/**
 * Reports -> Disponibilidad de la red -> Ver detalle (detalle técnico de un equipo).
 *
 * @var CView $this
 * @var array $data
 */

use Modules\LagunitasReportes\Includes\{EquipoService, ReporteService};

$f = $data['filtros'];
$d = $data['detalle'];

$e = static fn($v) => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');
$dur = static fn(?int $s) => ReporteService::duracion($s);
$num = static fn(?float $v, int $dec = 1, string $u = '') => $v === null ? '—'
	: number_format($v, $dec, ',', '.').($u !== '' ? ' '.$u : '');
$pct = static fn(?float $v) => $v === null ? '—' : number_format($v, 3, ',', '.').' %';
$bps = static function(?float $v): string {
	if ($v === null) {
		return '—';
	}
	foreach ([[1e9, 'Gbps'], [1e6, 'Mbps'], [1e3, 'Kbps']] as [$div, $u]) {
		if (abs($v) >= $div) {
			return number_format($v / $div, 2, ',', '.').' '.$u;
		}
	}

	return number_format($v, 0, ',', '.').' bps';
};
$niveles = ['ok' => ['ok', 'Normal'], 'warn' => ['warn', 'Advertencia'], 'crit' => ['bad', 'Crítico'], 'na' => ['na', 'Sin datos']];
$severidades = ['Sin clasificar', 'Información', 'Advertencia', 'Media', 'Alta', 'Desastre'];
$volver = 'zabbix.php?'.ReporteService::query(['hostid' => ''] + $f, ['action' => 'lagunitas.reporte']);

/** Sparkline SVG con líneas de umbral. */
$spark = static function(array $m) use ($e): string {
	$serie = $m['serie'];
	if (count($serie) < 2) {
		return '<div class="lr-spark-vacio">Sin histórico suficiente<br><small>Se completa a medida que Zabbix '
			.'acumula datos del período.</small></div>';
	}
	$ys = array_column($serie, 1);
	foreach (['warn', 'crit'] as $k) {
		if ($m[$k] !== null) {
			$ys[] = $m[$k];
		}
	}
	$min = min($ys);
	$max = max($ys);
	if ($max - $min < 1e-9) {
		$max += 1;
		$min -= 1;
	}
	$pad = ($max - $min) * 0.1;
	$min -= $pad;
	$max += $pad;
	$x0 = $serie[0][0];
	$x1 = max($x0 + 1, $serie[count($serie) - 1][0]);
	$W = 300;
	$H = 70;
	$px = static fn($t) => round(($t - $x0) / ($x1 - $x0) * $W, 1);
	$py = static fn($v) => round($H - ($v - $min) / ($max - $min) * $H, 1);
	$pts = implode(' ', array_map(static fn($p) => $px($p[0]).','.$py($p[1]), $serie));
	$area = '0,'.$H.' '.$pts.' '.$W.','.$H;
	$svg = '<svg class="lr-spark" viewBox="0 0 '.$W.' '.$H.'" preserveAspectRatio="none" role="img" aria-label="'
		.$e($m['titulo']).'"><polygon class="lr-spark-area" points="'.$area.'"/><polyline class="lr-spark-line" points="'
		.$pts.'"/>';
	foreach (['warn' => 'lr-th-warn', 'crit' => 'lr-th-crit'] as $k => $cls) {
		if ($m[$k] !== null) {
			$y = $py($m[$k]);
			$svg .= '<line class="'.$cls.'" x1="0" x2="'.$W.'" y1="'.$y.'" y2="'.$y.'"/>';
		}
	}

	return $svg.'</svg><div class="lr-spark-ejes"><span>'.$e(date('d/m H:i', $x0)).'</span><span>'
		.$e(date('d/m H:i', $x1)).'</span></div>';
};

ob_start();

if ($d === null) {
	echo '<div class="lr-page"><div class="lr-empty">Equipo no encontrado.</div></div>';
}
else {
	$h = $d['host'];
	$fila = $d['fila'];
	$tags = array_column($h['tags'], 'value', 'tag');
	$ip = '';
	foreach ($h['interfaces'] as $i) {
		if ($i['main'] == 1) {
			$ip = $i['useip'] == 1 ? $i['ip'] : $i['dns'];
			break;
		}
	}
	$descripcion_tipo = [
		'airmax' => 'Radio Ubiquiti airMAX — calidad del enlace inalámbrico, estaciones asociadas e interfaces',
		'mikrotik' => 'Router Mikrotik — energía (batería), recursos, clientes DHCP, interfaces y enlace a Internet',
		'unifi' => 'Access point UniFi — recursos, clientes Wi-Fi y calidad de radio (API de UniFi Network)',
		'icmp' => 'Equipo monitoreado por disponibilidad y calidad ICMP (latencia y pérdida)'
	][$d['tipo']];
	$prob = $d['problemas'];
	$salud = $fila['salud'] ?? 0;
?>
<div class="lr-page">
	<div class="lr-head">
		<div>
			<div class="lr-org" data-lr-text="org">Red Comunitaria y Científica Las Lagunitas</div>
			<h1>Detalle técnico: <?= $e($h['name']) ?></h1>
			<p><?= $e(date('d/m/Y H:i', $f['from'])) ?> — <?= $e(date('d/m/Y H:i', $f['to'])) ?>
				· Generado: <?= $e(date('d/m/Y H:i', $data['generado'])) ?></p>
		</div>
		<div class="lr-head-actions lr-no-print">
			<button type="button" class="lr-btn" data-lr-print>Imprimir / PDF</button>
			<a class="lr-btn lr-btn-primary" href="<?= $e($volver) ?>">← Volver al reporte</a>
		</div>
	</div>

	<div class="lr-banner">
		<b><?= $e($h['name']) ?></b> · <?= $e($ip) ?> · <?= $e($tags['rol'] ?? '') ?>
		<?= ($h['inventory']['model'] ?? '') !== '' ? ' · '.$e($h['inventory']['model']) : '' ?>
		<div><?= $e($descripcion_tipo) ?><?= $fila && $fila['padre'] ? ' · depende de '.$e($fila['padre']) : '' ?></div>
	</div>

	<section class="lr-cards">
		<div class="lr-card lr-c-<?= $fila && $fila['cumple'] ? 'ok' : 'bad' ?>"><span>Disponibilidad</span>
			<b><?= $pct($fila['disp_propia'] ?? null) ?></b><small>Propia, por <?= $e(implode(' + ', $fila['indicadores'] ?? [])) ?: '—' ?></small></div>
		<div class="lr-card lr-c-aff"><span>Disponibilidad del servicio</span>
			<b><?= $pct($fila['disp_servicio'] ?? null) ?></b><small>Incluye caídas aguas arriba</small></div>
		<div class="lr-card lr-c-info"><span>SLA objetivo</span><b><?= $e(number_format($f['slo'], 3, ',', '.')) ?> %</b>
			<small><?= $fila && $fila['con_indicador'] ? ($fila['cumple'] ? 'Cumple' : 'No cumple') : 'Sin indicador' ?></small></div>
		<div class="lr-card lr-c-info"><span>Mantenimiento</span><b><?= $h['maintenance_status'] ? 'Sí' : 'No' ?></b>
			<small><?= $f['mantenimiento'] === 'excluir' ? 'Eventos suprimidos excluidos' : 'Eventos suprimidos incluidos' ?></small></div>
		<div class="lr-card lr-c-bad"><span>Caída propia</span><b><?= $e($dur($fila['caida_propia'] ?? 0)) ?></b>
			<small><?= (int) ($fila['incidentes'] ?? 0) ?> caída(s) · MTTR <?= $e($dur($fila['mttr'] ?? null)) ?></small></div>
		<div class="lr-card lr-c-warn"><span>Problemas del período</span><b><?= (int) $prob['total'] ?></b><small>Eventos individuales</small></div>
		<div class="lr-card lr-c-<?= $prob['activos'] ? 'bad' : 'ok' ?>"><span>Problemas activos</span><b><?= (int) $prob['activos'] ?></b><small>Sin recuperación al cierre</small></div>
		<div class="lr-card lr-c-violeta"><span>Tiempo afectado único</span><b><?= $e($dur($prob['tiempo_afectado'])) ?></b><small>Sin duplicar alertas simultáneas</small></div>
		<div class="lr-card lr-c-violeta"><span>Horas-evento acumuladas</span><b><?= $e($dur($prob['horas_evento'])) ?></b><small>Suma de todas las alertas</small></div>
		<div class="lr-card lr-c-<?= $salud ? 'warn' : 'ok' ?>"><span>Salud operativa</span><b><?= $salud ? 'Degradado' : 'Normal' ?></b><small>Separada del cálculo de SLA</small></div>
		<div class="lr-card lr-c-info"><span>Equipos dependientes</span><b><?= (int) ($fila['dependientes'] ?? 0) ?></b><small>Quedan sin servicio si cae</small></div>
	</section>

	<section class="lr-conclusiones">
		<h2>Conclusiones y recomendaciones</h2>
		<ul>
		<?php foreach ($d['conclusiones'] as [$nivel_c, $texto]): ?>
			<li class="lr-c-<?= $e($nivel_c) ?>"><?= $e($texto) ?></li>
		<?php endforeach; ?>
		</ul>
	</section>

	<?php if ($d['textos']): ?>
	<section class="lr-sec">
		<div class="lr-sec-head"><h2>Datos del equipo</h2></div>
		<dl class="lr-dl">
			<?php foreach ($d['textos'] as $k => $v): ?><div><dt><?= $e($k) ?></dt><dd><?= $e($v) ?></dd></div><?php endforeach; ?>
		</dl>
	</section>
	<?php endif; ?>

	<?php if ($d['metricas']): ?>
	<h2 class="lr-h2">Comportamiento de recursos y enlace</h2>
	<section class="lr-metricas">
		<?php foreach ($d['metricas'] as $m):
			[$cls_a, $txt_a] = $niveles[$m['nivel_actual']];
			[$cls_p, $txt_p] = $niveles[$m['nivel_pico']];
			$extremo = $m['sentido'] === 'bajo' ? ['Mínimo', $m['minimo']] : ['Máximo', $m['maximo']];
		?>
		<div class="lr-metrica lr-borde-<?= $e($cls_p) ?>">
			<div class="lr-metrica-head">
				<h3><?= $e($m['titulo']) ?></h3>
				<?php if ($m['sentido'] !== null): ?>
					<span class="lr-tag lr-tag-<?= $e($cls_a) ?>">Ahora: <?= $e($txt_a) ?></span>
					<span class="lr-tag lr-tag-<?= $e($cls_p) ?>">Pico: <?= $e($txt_p) ?></span>
				<?php endif; ?>
			</div>
			<dl>
				<div><dt>Actual</dt><dd><?= $e($num($m['actual'], $m['decimales'], $m['unidad'])) ?></dd></div>
				<div><dt>Promedio</dt><dd><?= $e($num($m['promedio'], $m['decimales'], $m['unidad'])) ?></dd></div>
				<div><dt><?= $extremo[0] ?></dt><dd><?= $e($num($extremo[1], $m['decimales'], $m['unidad'])) ?></dd></div>
			</dl>
			<?= $spark($m) ?>
			<?php if ($m['sentido'] !== null): ?>
				<p class="lr-umbral">Fuera de umbral (aprox.): <b><?= $e($num($m['horas_warn'], 1)) ?> h</b> advertencia ·
					<b><?= $e($num($m['horas_crit'], 1)) ?> h</b> crítico
					<small>(umbrales <?= $e($num((float) $m['warn'], $m['decimales'])) ?> / <?= $e($num((float) $m['crit'], $m['decimales'])) ?> <?= $e($m['unidad']) ?>)</small></p>
			<?php endif; ?>
			<p class="lr-item-key"><?= $e($m['key']) ?> · <?= $m['fuente'] === 'tendencias' ? 'tendencias horarias' : 'historial' ?></p>
		</div>
		<?php endforeach; ?>
	</section>
	<?php endif; ?>

	<?php if ($d['interfaces']):
		$ifs = $d['interfaces'];
		$up = count(array_filter($ifs, static fn($x) => isset($x['estado']) && (int) $x['estado'] === 1));
		$tin = array_sum(array_map(static fn($x) => $x['in'] ?? 0, $ifs));
		$tout = array_sum(array_map(static fn($x) => $x['out'] ?? 0, $ifs));
		$oper = [1 => 'UP', 2 => 'DOWN', 3 => 'TESTING', 4 => 'DESCONOCIDO', 5 => 'DORMANT', 6 => 'NO PRESENTE', 7 => 'CAPA INF. CAÍDA'];
	?>
	<section class="lr-sec" data-lr-filtrable>
		<div class="lr-sec-head"><h2>Estado de interfaces</h2><small>Tráfico actual y máximos de errores del período</small></div>
		<div class="lr-mini-cards">
			<div><span>Interfaces</span><b><?= count($ifs) ?></b></div>
			<div><span>UP</span><b class="lr-t-ok"><?= $up ?></b></div>
			<div><span>DOWN</span><b class="lr-t-bad"><?= count($ifs) - $up ?></b></div>
			<div><span>Con errores</span><b><?= count(array_filter($ifs, static fn($x) => $x['errores_max'] > 0)) ?></b></div>
			<div><span>Con cambios</span><b><?= count(array_filter($ifs, static fn($x) => $x['cambios'] > 0)) ?></b></div>
			<div><span>Tráfico entrada</span><b><?= $e($bps($tin)) ?></b></div>
			<div><span>Tráfico salida</span><b><?= $e($bps($tout)) ?></b></div>
		</div>
		<div class="lr-tabla-filtros lr-no-print">
			<input type="search" placeholder="Buscar interfaz…" data-lr-q>
			<select data-lr-f="estado"><option value="">Todos los estados</option><option value="up">UP</option><option value="down">DOWN</option></select>
			<select data-lr-f="err"><option value="">Con y sin errores</option><option value="si">Con errores</option><option value="no">Sin errores</option></select>
			<span class="lr-contador" data-lr-contador></span>
		</div>
		<div class="lr-table-wrap"><table class="lr-table">
			<thead><tr><th>Interfaz</th><th>Estado</th><th>Tráfico entrada</th><th>Tráfico salida</th><th>Errores máx. (/s)</th>
				<th>Cambios de estado</th><th>Velocidad</th><th>Estado del período</th></tr></thead>
			<tbody>
			<?php foreach ($ifs as $x):
				$est = isset($x['estado']) ? (int) $x['estado'] : null;
				[$dcls, $dtxt] = $x['diagnostico'];
			?>
				<tr data-lr-fila data-q="<?= $e(mb_strtolower($x['nombre'])) ?>" data-estado="<?= $est === 1 ? 'up' : 'down' ?>" data-err="<?= $x['errores_max'] > 0 ? 'si' : 'no' ?>">
					<td><b><?= $e($x['nombre']) ?></b></td>
					<td><b class="lr-t-<?= $est === 1 ? 'ok' : 'bad' ?>"><?= $e($oper[$est] ?? '—') ?></b></td>
					<td><?= $e($bps($x['in'] ?? null)) ?></td><td><?= $e($bps($x['out'] ?? null)) ?></td>
					<td><?= $e($num($x['errores_max'], 2)) ?></td><td><?= (int) $x['cambios'] ?></td>
					<td><?= $e($bps($x['velocidad'] ?? null)) ?></td>
					<td><span class="lr-tag lr-tag-<?= $dcls === 'crit' ? 'bad' : $e($dcls) ?>"><?= $e($dtxt) ?></span></td>
				</tr>
			<?php endforeach; ?>
			</tbody>
		</table></div>
	</section>
	<?php endif; ?>

	<?php if ($d['estaciones']): ?>
	<section class="lr-sec">
		<div class="lr-sec-head"><h2>Estaciones asociadas</h2><small>Otro extremo del enlace de radio</small></div>
		<div class="lr-table-wrap"><table class="lr-table">
			<thead><tr><th>Estación</th><th>Señal actual</th><th>Señal mínima del período</th><th>Ruido</th><th>CCQ</th>
				<th>Calidad / capacidad airMAX</th><th>Distancia</th><th>Latencia TX</th></tr></thead>
			<tbody>
			<?php foreach ($d['estaciones'] as $st): ?>
				<tr><td><b><?= $e($st['nombre'] ?? '—') ?></b></td>
					<td class="lr-t-<?= EquipoService::nivel($st['senal'] ?? null, 'bajo', -72, -80) === 'ok' ? 'ok' : 'warn' ?>"><?= $e($num($st['senal'] ?? null, 0, 'dBm')) ?></td>
					<td><?= $e($num($st['senal_min'] ?? null, 0, 'dBm')) ?></td>
					<td><?= $e($num($st['ruido'] ?? null, 0, 'dBm')) ?></td>
					<td><?= $e($num($st['ccq'] ?? null, 0, '%')) ?></td>
					<td><?= $e($num($st['calidad'] ?? null, 0, '%')) ?> / <?= $e($num($st['capacidad'] ?? null, 0, '%')) ?></td>
					<td><?= $e($num($st['distancia'] ?? null, 0, 'm')) ?></td>
					<td><?= $e($num($st['latencia'] ?? null, 0, 'ms')) ?></td></tr>
			<?php endforeach; ?>
			</tbody>
		</table></div>
	</section>
	<?php endif; ?>

	<section class="lr-sec" data-lr-filtrable>
		<div class="lr-sec-head"><h2>Problemas agrupados</h2><small>Las repeticiones se consolidan; "flapping" indica 3 o más apariciones.</small></div>
		<?php if ($prob['grupos']): ?>
		<div class="lr-tabla-filtros lr-no-print">
			<input type="search" placeholder="Buscar problema…" data-lr-q>
			<select data-lr-f="sev"><option value="">Todas las severidades</option>
				<?php foreach ($severidades as $i => $s): ?><option value="<?= $i ?>"><?= $e($s) ?></option><?php endforeach; ?></select>
			<select data-lr-f="cat"><option value="">Todas las categorías</option>
				<?php foreach (array_unique(array_column($prob['grupos'], 'categoria')) as $c): ?><option><?= $e($c) ?></option><?php endforeach; ?></select>
			<select data-lr-f="activo"><option value="">Todos los estados</option><option value="si">Activos</option><option value="no">Resueltos</option></select>
			<span class="lr-contador" data-lr-contador></span>
		</div>
		<div class="lr-table-wrap"><table class="lr-table">
			<thead><tr><th>Estado</th><th>Severidad</th><th>Categoría</th><th>Problema</th><th>Veces</th><th>Horas-evento</th>
				<th>Primero</th><th>Último</th><th>Reconocido</th></tr></thead>
			<tbody>
			<?php foreach ($prob['grupos'] as $g): ?>
				<tr data-lr-fila data-q="<?= $e(mb_strtolower($g['nombre'])) ?>" data-sev="<?= (int) $g['severidad'] ?>" data-cat="<?= $e($g['categoria']) ?>" data-activo="<?= $g['activo'] ? 'si' : 'no' ?>">
					<td><b class="lr-t-<?= $g['activo'] ? 'bad' : 'ok' ?>"><?= $g['activo'] ? 'Activo' : 'Resuelto' ?></b></td>
					<td><span class="lr-sev lr-sev-<?= (int) $g['severidad'] ?>"><?= $e($severidades[$g['severidad']]) ?></span></td>
					<td><?= $e($g['categoria']) ?></td>
					<td><b><?= $e($g['nombre']) ?></b><?= $g['flapping'] ? ' <span class="lr-flap">FLAPPING</span>' : '' ?>
						<small class="lr-sub"><?= $e($num($g['por_dia'], 2)) ?> eventos/día · duración media <?= $e($dur($g['duracion_media'])) ?></small></td>
					<td><?= (int) $g['veces'] ?></td><td><?= $e($dur($g['segundos'])) ?></td>
					<td><?= $e(date('d/m/Y H:i', $g['primero'])) ?></td><td><?= $e(date('d/m/Y H:i', $g['ultimo'])) ?></td>
					<td><?= $g['reconocido'] ? 'Sí' : 'No' ?></td>
				</tr>
			<?php endforeach; ?>
			</tbody>
		</table></div>
		<details class="lr-eventos">
			<summary>Ver eventos individuales (<?= (int) $prob['total'] ?>)</summary>
			<table class="lr-det"><thead><tr><th>Inicio</th><th>Fin</th><th>Duración</th><th>Severidad</th><th>Problema</th></tr></thead><tbody>
			<?php foreach ($prob['individuales'] as $ev): ?>
				<tr><td><?= $e(date('d/m/Y H:i', $ev['inicio'])) ?></td><td><?= $ev['fin'] ? $e(date('d/m/Y H:i', $ev['fin'])) : '<b>en curso</b>' ?></td>
					<td><?= $e($dur($ev['duracion'])) ?></td><td><?= $e($severidades[$ev['severidad']]) ?></td><td><?= $e($ev['nombre']) ?></td></tr>
			<?php endforeach; ?>
			</tbody></table>
		</details>
		<?php else: ?>
			<div class="lr-empty">Sin problemas en el período.</div>
		<?php endif; ?>
	</section>

	<div class="lr-foot">Datos consultados bajo demanda mediante la API de Zabbix · Módulo de reportes v1.1</div>
</div>
<?php
}
$html = ob_get_clean();

(new CHtmlPage())
	->setTitle('Detalle técnico')
	->addItem(new CObject($html))
	->show();
