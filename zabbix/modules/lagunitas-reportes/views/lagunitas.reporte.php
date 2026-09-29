<?php declare(strict_types = 0);

/**
 * Reports -> Disponibilidad de la red.
 *
 * @var CView $this
 * @var array $data
 */

use Modules\LagunitasReportes\Includes\ReporteService;

$f = $data['filtros'];
$rep = $data['reporte'];
$r = $rep['resumen'];
$tecnica = $f['vista'] === 'tecnica';

$e = static fn($v) => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');
$pct = static fn(?float $v, int $d = 3) => $v === null ? '—' : number_format($v, $d, ',', '.').' %';
$dur = static fn(?int $s) => $s === null ? '—' : ReporteService::duracion($s);
$num = static fn(?float $v, int $d = 1, string $u = '') => $v === null ? '—' : number_format($v, $d, ',', '.').$u;
$nivel = static fn(float $v) => $v >= $f['slo'] ? 'ok' : ($v >= $f['slo'] - 1 ? 'warn' : 'bad');
$barra = static function(float $v) use ($nivel, $pct): string {
	// Escala desde 90 % para que las diferencias chicas (99,9 vs 99,5) sean visibles.
	$ancho = max(2, min(100, ($v - 90) * 10));

	return '<div class="lr-bar-wrap"><div class="lr-bar"><span class="lr-n-'.$nivel($v).'" style="width:'
		.number_format($ancho, 1, '.', '').'%"></span></div><b>'.$pct($v).'</b></div>';
};

$query = http_build_query(array_intersect_key($f, array_flip(['periodo', 'desde', 'hasta', 'rol', 'slo', 'vista'])));

ob_start();
?>
<div class="lr-page">
	<div class="lr-head">
		<div>
			<div class="lr-org" contenteditable="true" spellcheck="false" data-lr-edit="org"
				title="Clic para editar (se guarda en este navegador)">Red Comunitaria y Científica Las Lagunitas</div>
			<h1 contenteditable="true" spellcheck="false" data-lr-edit="titulo"
				title="Clic para editar (se guarda en este navegador)">Reporte de disponibilidad de la red</h1>
			<p>Período: <b><?= $e(date('d/m/Y H:i', $f['from'])) ?></b> al <b><?= $e(date('d/m/Y H:i', $f['to'])) ?></b>
				· <?= $e(ReporteService::PERIODOS[$f['periodo']]) ?>
				· Objetivo de disponibilidad: <b><?= $e(number_format($f['slo'], 2, ',', '.')) ?> %</b>
				· Vista <?= $tecnica ? 'técnica' : 'gerencial' ?></p>
		</div>
		<div class="lr-head-actions lr-no-print">
			<a class="lr-btn" href="zabbix.php?action=lagunitas.reporte.csv&amp;<?= $e($query) ?>">Exportar CSV</a>
			<button type="button" class="lr-btn lr-btn-primary" data-lr-print>Imprimir / PDF</button>
		</div>
	</div>

	<form class="lr-filtros lr-no-print" method="get" action="zabbix.php">
		<input type="hidden" name="action" value="lagunitas.reporte">
		<label>Período
			<select name="periodo" data-lr-periodo>
				<?php foreach (ReporteService::PERIODOS as $k => $v): ?>
					<option value="<?= $e($k) ?>"<?= $k === $f['periodo'] ? ' selected' : '' ?>><?= $e($v) ?></option>
				<?php endforeach; ?>
			</select>
		</label>
		<label class="lr-fecha">Desde <input type="date" name="desde" value="<?= $e(date('Y-m-d', $f['from'])) ?>"></label>
		<label class="lr-fecha">Hasta <input type="date" name="hasta" value="<?= $e(date('Y-m-d', max($f['from'], $f['to'] - 1))) ?>"></label>
		<label>Rol
			<select name="rol">
				<option value="">Todos</option>
				<?php foreach ($rep['roles'] as $rol): ?>
					<option value="<?= $e($rol) ?>"<?= $rol === $f['rol'] ? ' selected' : '' ?>><?= $e($rol) ?></option>
				<?php endforeach; ?>
			</select>
		</label>
		<label>Objetivo (%) <input type="number" name="slo" min="0" max="100" step="0.01" value="<?= $e($f['slo']) ?>"></label>
		<label>Vista
			<select name="vista">
				<option value="tecnica"<?= $tecnica ? ' selected' : '' ?>>Técnica</option>
				<option value="gerencial"<?= !$tecnica ? ' selected' : '' ?>>Gerencial</option>
			</select>
		</label>
		<button type="submit" class="lr-btn lr-btn-primary">Generar</button>
	</form>

<?php if ($r === null): ?>
	<div class="lr-empty">No hay equipos monitoreados en el grupo "<?= $e(ReporteService::GRUPO) ?>".</div>
<?php else: ?>
	<section class="lr-cards">
		<div class="lr-card lr-c-info"><span>Equipos</span><b><?= (int) $r['equipos'] ?></b></div>
		<div class="lr-card lr-c-<?= $nivel($r['disp_media']) ?>"><span>Disponibilidad media</span><b><?= $pct($r['disp_media']) ?></b></div>
		<div class="lr-card lr-c-ok"><span>Cumplen objetivo</span><b><?= (int) $r['cumplen'] ?></b></div>
		<div class="lr-card lr-c-<?= $r['no_cumplen'] ? 'bad' : 'ok' ?>"><span>No cumplen</span><b><?= (int) $r['no_cumplen'] ?></b></div>
		<div class="lr-card lr-c-<?= $r['incidentes'] ? 'warn' : 'ok' ?>"><span>Caídas</span><b><?= (int) $r['incidentes'] ?></b></div>
		<div class="lr-card lr-c-info"><span>Tiempo caído (total)</span><b><?= $e($dur($r['caida_total'])) ?></b></div>
		<div class="lr-card lr-c-info"><span>MTTR medio</span><b><?= $e($dur($r['mttr'])) ?></b></div>
	</section>

	<section class="lr-conclusiones">
		<h2>Conclusiones</h2>
		<ul>
			<?php foreach ($rep['conclusiones'] as $c): ?><li><?= $e($c) ?></li><?php endforeach; ?>
		</ul>
	</section>

	<?php
	$por_rol = [];
	foreach ($rep['filas'] as $fila) {
		$por_rol[$fila['rol']][] = $fila;
	}
	foreach ($por_rol as $rol => $filas):
	?>
	<section class="lr-sec">
		<div class="lr-sec-head"><h2><?= $e($rol) ?></h2><span class="lr-pill"><?= count($filas) ?></span></div>
		<div class="lr-table-wrap">
		<table class="lr-table">
			<thead><tr>
				<th>Equipo</th>
				<?php if ($tecnica): ?><th>Disponibilidad propia</th><?php endif; ?>
				<th>Disponibilidad del servicio</th>
				<th>Tiempo sin servicio</th>
				<th>Caídas</th>
				<?php if ($tecnica): ?>
					<th>MTTR</th><th>Mayor caída</th><th>Latencia media</th><th>Pérdida media</th><th>Advertencias</th>
				<?php endif; ?>
				<th>Objetivo</th>
			</tr></thead>
			<tbody>
			<?php foreach ($filas as $x): ?>
				<tr class="<?= $x['caido_ahora'] ? 'lr-caido' : '' ?>">
					<td>
						<details>
							<summary><b><?= $e($x['nombre']) ?></b><?= $x['caido_ahora'] ? ' <span class="lr-tag lr-tag-bad">caído ahora</span>' : '' ?>
								<small><?= $e($x['ip']) ?><?= $x['padre'] !== '' ? ' · depende de '.$e($x['padre']) : '' ?>
								<?= $x['dependientes'] ? ' · '.(int) $x['dependientes'].' dependientes' : '' ?></small></summary>
							<?php if ($x['detalle']): ?>
								<table class="lr-det"><thead><tr><th>Inicio</th><th>Fin</th><th>Duración</th><th>Causa</th></tr></thead><tbody>
								<?php foreach ($x['detalle'] as $i): ?>
									<tr><td><?= $e(date('d/m/Y H:i', $i['inicio'])) ?></td>
										<td><?= $i['fin'] ? $e(date('d/m/Y H:i', $i['fin'])) : '<b>en curso</b>' ?></td>
										<td><?= $e($dur(($i['fin'] ?? $data['generado']) - $i['inicio'])) ?></td>
										<td><?= $i['causa'] === null ? 'Caída del propio equipo' : 'Caída de '.$e($i['causa']).' (aguas arriba)' ?></td></tr>
								<?php endforeach; ?>
								</tbody></table>
							<?php else: ?>
								<div class="lr-muted">Sin caídas en el período.</div>
							<?php endif; ?>
						</details>
					</td>
					<?php if ($tecnica): ?><td><?= $barra($x['disp_propia']) ?></td><?php endif; ?>
					<td><?= $barra($x['disp_servicio']) ?></td>
					<td><?= $e($dur($x['caida_servicio'])) ?></td>
					<td><?= (int) $x['incidentes'] ?></td>
					<?php if ($tecnica): ?>
						<td><?= $e($dur($x['mttr'])) ?></td>
						<td><?= $x['mayor'] ? $e($dur($x['mayor'])) : '—' ?></td>
						<td><?= $e($num($x['latencia_ms'], 2, ' ms')) ?></td>
						<td><?= $e($num($x['perdida'], 2, ' %')) ?></td>
						<td><?= (int) $x['avisos'] ?></td>
					<?php endif; ?>
					<td><span class="lr-tag lr-tag-<?= $x['cumple'] ? 'ok' : 'bad' ?>"><?= $x['cumple'] ? 'Cumple' : 'No cumple' ?></span></td>
				</tr>
			<?php endforeach; ?>
			</tbody>
		</table>
		</div>
	</section>
	<?php endforeach; ?>

	<div class="lr-foot">
		<p><b>Disponibilidad propia</b>: tiempo en que el equipo respondió (su trigger de caída no estuvo activo).
			<b>Disponibilidad del servicio</b>: además descuenta las caídas de los equipos de los que depende
			(torre/nodo aguas arriba): es lo que efectivamente vivió el hogar o la institución.
			Los intervalos superpuestos se unen antes de sumar. MTTR = tiempo medio de recuperación de las caídas resueltas.</p>
		<p>Generado el <?= $e(date('d/m/Y H:i', $data['generado'])) ?> desde Zabbix · Red Comunitaria y Científica Las Lagunitas.</p>
	</div>
<?php endif; ?>
</div>
<?php
$html = ob_get_clean();

(new CHtmlPage())
	->setTitle('Disponibilidad de la red')
	->addItem(new CObject($html))
	->show();
