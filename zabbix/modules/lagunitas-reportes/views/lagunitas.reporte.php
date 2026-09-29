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
$dur = static fn(?int $s) => ReporteService::duracion($s);
$num = static fn(?float $v, int $d = 1, string $u = '') => $v === null ? '—' : number_format($v, $d, ',', '.').$u;
$nivel = static fn(?float $v) => $v === null ? 'na' : ($v >= $f['slo'] ? 'ok' : ($v >= $f['slo'] - 1 ? 'warn' : 'bad'));
$pill = static fn(?float $v) => '<span class="lr-pill-val lr-p-'.$nivel($v).'">'.$pct($v).'</span>';
$estados = [
	'disponible' => ['ok', 'Disponible'], 'caido' => ['bad', 'Con caída activa'],
	'sin_servicio' => ['aff', 'Sin servicio'], 'mantenimiento' => ['info', 'En mantenimiento'],
	'sin_indicador' => ['na', 'Sin indicador']
];
$tipos = ['airmax' => 'Radio airMAX', 'mikrotik' => 'Router Mikrotik', 'icmp' => 'ICMP', 'unifi' => 'AP UniFi'];

ob_start();
?>
<div class="lr-page">
	<div class="lr-head">
		<div>
			<div class="lr-org" data-lr-text="org">Red Comunitaria y Científica Las Lagunitas</div>
			<h1><span data-lr-prefijo><?= $tecnica ? 'Reporte técnico' : 'Reporte gerencial' ?></span>:
				<span data-lr-text="titulo">Monitoreo y disponibilidad de la red</span></h1>
			<p>Período: <b><?= $e(date('d/m/Y H:i', $f['from'])) ?></b> — <b><?= $e(date('d/m/Y H:i', $f['to'])) ?></b>
				· Generado: <?= $e(date('d/m/Y H:i', $data['generado'])) ?>
				· Objetivo: <b><?= $e(number_format($f['slo'], 2, ',', '.')) ?> %</b>
				· Mantenimientos: <?= $f['mantenimiento'] === 'excluir' ? 'excluidos' : 'incluidos' ?></p>
		</div>
		<div class="lr-head-actions lr-no-print">
			<a class="lr-btn" href="zabbix.php?<?= $e(ReporteService::query($f, ['action' => 'lagunitas.reporte.csv'])) ?>">Exportar CSV</a>
			<button type="button" class="lr-btn lr-btn-primary" data-lr-print>Imprimir / Guardar PDF</button>
		</div>
	</div>

	<form class="lr-filtros lr-no-print" method="get" action="zabbix.php">
		<input type="hidden" name="action" value="lagunitas.reporte">
		<div class="lr-filtros-grid">
			<label>Tipo de reporte
				<select name="vista">
					<option value="tecnica"<?= $tecnica ? ' selected' : '' ?>>Técnico</option>
					<option value="gerencial"<?= !$tecnica ? ' selected' : '' ?>>Gerencial</option>
				</select>
			</label>
			<label>Período
				<select name="periodo" data-lr-periodo>
					<?php foreach (ReporteService::PERIODOS as $k => $v): ?>
						<option value="<?= $e($k) ?>"<?= $k === $f['periodo'] ? ' selected' : '' ?>><?= $e($v) ?></option>
					<?php endforeach; ?>
				</select>
			</label>
			<label class="lr-fecha">Desde <input type="date" name="desde" value="<?= $e(date('Y-m-d', $f['from'])) ?>"></label>
			<label class="lr-fecha">Hasta <input type="date" name="hasta" value="<?= $e(date('Y-m-d', max($f['from'], $f['to'] - 1))) ?>"></label>
			<label>Grupo
				<select name="grupo">
					<option value="">Todos los grupos</option>
					<?php foreach ($data['grupos'] as $gid => $gname): ?>
						<option value="<?= $e($gid) ?>"<?= (string) $gid === $f['grupo'] ? ' selected' : '' ?>><?= $e($gname) ?></option>
					<?php endforeach; ?>
				</select>
			</label>
			<label>Equipo
				<select name="hostid">
					<option value="">Todos los equipos</option>
					<?php foreach ($data['equipos'] as $hid => $hname): ?>
						<option value="<?= $e($hid) ?>"<?= (string) $hid === $f['hostid'] ? ' selected' : '' ?>><?= $e($hname) ?></option>
					<?php endforeach; ?>
				</select>
			</label>
			<label>Tipo de equipo
				<select name="tipo">
					<?php foreach (ReporteService::TIPOS as $k => $v): ?>
						<option value="<?= $e($k) ?>"<?= $k === $f['tipo'] ? ' selected' : '' ?>><?= $e($v) ?></option>
					<?php endforeach; ?>
				</select>
			</label>
			<label>Mantenimientos
				<select name="mantenimiento">
					<option value="excluir"<?= $f['mantenimiento'] === 'excluir' ? ' selected' : '' ?>>Excluir suprimidos</option>
					<option value="incluir"<?= $f['mantenimiento'] === 'incluir' ? ' selected' : '' ?>>Incluir todo</option>
				</select>
			</label>
			<label>SLA objetivo (%) <input type="number" name="slo" min="0" max="100" step="0.01" value="<?= $e($f['slo']) ?>"></label>
		</div>
		<details class="lr-personalizar">
			<summary>Personalizar encabezado</summary>
			<div class="lr-filtros-grid lr-dos">
				<label>Organización o institución <input type="text" data-lr-input="org" maxlength="120"></label>
				<label>Título del reporte <input type="text" data-lr-input="titulo" maxlength="160"></label>
			</div>
		</details>
		<button type="submit" class="lr-btn lr-btn-primary">Generar reporte</button>
	</form>

<?php if ($r === null): ?>
	<div class="lr-empty">No hay equipos que coincidan con los filtros en el grupo "<?= $e(ReporteService::GRUPO) ?>".</div>
<?php else: ?>
	<section class="lr-cards">
		<div class="lr-card lr-c-info"><span>Equipos</span><b><?= (int) $r['equipos'] ?></b></div>
		<div class="lr-card lr-c-ok"><span>Evaluados</span><b><?= (int) $r['evaluados'] ?></b></div>
		<div class="lr-card lr-c-violeta"><span>Disponibilidad media</span><b><?= $pct($r['disp_media']) ?></b></div>
		<div class="lr-card lr-c-ok"><span>Cumplen SLA</span><b><?= (int) $r['cumplen'] ?></b></div>
		<div class="lr-card lr-c-<?= $r['no_cumplen'] ? 'bad' : 'ok' ?>"><span>No cumplen</span><b><?= (int) $r['no_cumplen'] ?></b></div>
		<div class="lr-card lr-c-na"><span>Sin indicador</span><b><?= (int) $r['sin_indicador'] ?></b></div>
		<div class="lr-card lr-c-warn"><span>Caídas</span><b><?= (int) $r['incidentes'] ?></b></div>
		<div class="lr-card lr-c-bad"><span>Horas-equipo de caída</span><b><?= $e($dur($r['caida_total'])) ?></b></div>
		<div class="lr-card lr-c-aff"><span>Horas sin servicio</span><b><?= $e($dur($r['sin_servicio_total'])) ?></b></div>
		<div class="lr-card lr-c-info"><span>MTTR medio</span><b><?= $e($dur($r['mttr'])) ?></b></div>
		<div class="lr-card lr-c-ok"><span>Salud normal</span><b><?= (int) $r['salud_normal'] ?></b></div>
		<div class="lr-card lr-c-warn"><span>Degradados</span><b><?= (int) $r['degradados'] ?></b></div>
	</section>

	<section class="lr-conclusiones">
		<h2>Conclusiones</h2>
		<ul>
			<?php foreach ($rep['conclusiones'] as $c): ?><li><?= $e($c) ?></li><?php endforeach; ?>
		</ul>
	</section>

	<section class="lr-sec">
		<div class="lr-table-wrap">
		<table class="lr-table">
			<thead><tr>
				<th>Equipo</th><th>IP</th><th>Grupo</th>
				<?php if ($tecnica): ?><th>Indicador detectado</th><th>Disponibilidad propia</th><?php endif; ?>
				<th>Disponibilidad del servicio</th><th>Caída</th><th>Incidentes</th>
				<?php if ($tecnica): ?><th>MTTR</th><th>Mayor caída</th><?php endif; ?>
				<th>Salud actual</th><th>Estado actual</th><th>SLA</th><th class="lr-no-print">Detalle</th>
			</tr></thead>
			<tbody>
			<?php foreach ($rep['filas'] as $x):
				[$ecls, $etxt] = $estados[$x['estado']];
			?>
				<tr class="<?= $x['caido_ahora'] ? 'lr-caido' : '' ?>">
					<td><b><?= $e($x['nombre']) ?></b><small class="lr-sub"><?= $e($tipos[$x['tipo']] ?? '') ?><?= $x['padre'] !== '' ? ' · depende de '.$e($x['padre']) : '' ?></small></td>
					<td class="lr-mono"><?= $e($x['ip']) ?></td>
					<td><?= $e($x['grupo']) ?></td>
					<?php if ($tecnica): ?>
						<td><?php foreach ($x['indicadores'] as $ind): ?><span class="lr-ind lr-ind-<?= $e(strtolower($ind)) ?>"><?= $e($ind) ?></span><?php endforeach; ?>
							<small class="lr-sub"><?= $x['con_indicador'] ? 'Usa '.(in_array('ICMP', $x['indicadores']) ? 'ICMP' : 'API') : 'Sin indicador' ?></small></td>
						<td><?= $pill($x['disp_propia']) ?></td>
					<?php endif; ?>
					<td><?= $pill($x['disp_servicio']) ?></td>
					<td><?= $e($dur($x['caida_servicio'])) ?></td>
					<td><?= (int) $x['incidentes'] ?></td>
					<?php if ($tecnica): ?>
						<td><?= $e($dur($x['mttr'])) ?></td>
						<td><?= $x['mayor'] ? $e($dur($x['mayor'])) : '0 min' ?></td>
					<?php endif; ?>
					<td><?= $x['salud'] ? '<span class="lr-tag lr-tag-warn">Degradado ('.(int) $x['salud'].')</span>'
						: '<span class="lr-tag lr-tag-ok">Normal</span>' ?></td>
					<td><span class="lr-tag lr-tag-<?= $ecls ?>"><?= $e($etxt) ?></span>
						<?= $x['causa'] ? '<small class="lr-sub">por '.$e($x['causa']).'</small>' : '' ?></td>
					<td><?= $x['con_indicador'] ? '<span class="lr-tag lr-tag-'.($x['cumple'] ? 'ok">Cumple' : 'bad">No cumple').'</span>' : '—' ?></td>
					<td class="lr-no-print"><a class="lr-btn lr-btn-sm lr-btn-primary"
						href="zabbix.php?<?= $e(ReporteService::query($f, ['action' => 'lagunitas.reporte.equipo', 'hostid' => $x['hostid']])) ?>">Ver detalle</a></td>
				</tr>
				<?php if ($x['detalle']): ?>
				<tr class="lr-det-row"><td colspan="<?= $tecnica ? 14 : 9 ?>">
					<details>
						<summary>Detalle de incidentes de <?= $e($x['nombre']) ?> (<?= count($x['detalle']) ?>)</summary>
						<table class="lr-det"><thead><tr><th>Inicio</th><th>Fin</th><th>Duración</th><th>Causa</th></tr></thead><tbody>
						<?php foreach ($x['detalle'] as $i): ?>
							<tr><td><?= $e(date('d/m/Y H:i', $i['inicio'])) ?></td>
								<td><?= $i['fin'] ? $e(date('d/m/Y H:i', $i['fin'])) : '<b>en curso</b>' ?></td>
								<td><?= $e($dur(($i['fin'] ?? $data['generado']) - $i['inicio'])) ?></td>
								<td><?= $i['causa'] === null ? 'Caída del propio equipo' : 'Caída de '.$e($i['causa']).' (aguas arriba)' ?></td></tr>
						<?php endforeach; ?>
						</tbody></table>
					</details>
				</td></tr>
				<?php endif; ?>
			<?php endforeach; ?>
			</tbody>
		</table>
		</div>
	</section>

	<div class="lr-criterio">
		<b>Criterio de disponibilidad:</b> se calcula con el trigger de caída de cada equipo (ICMP, o el
		estado informado por la API en los AP UniFi). La <b>disponibilidad propia</b> mide al equipo; la
		<b>del servicio</b> descuenta además las caídas de los equipos de los que depende (lo que vivió el
		hogar o la institución). Los intervalos simultáneos se unen para no duplicar tiempo. Los problemas de
		señal, energía, recursos e interfaces se informan como <b>salud</b> sin descontar disponibilidad.
		<?= $f['mantenimiento'] === 'excluir' ? 'Los eventos suprimidos por mantenimiento se excluyen.' : '' ?>
		MTTR = tiempo medio de recuperación de las caídas resueltas.
	</div>
	<div class="lr-foot">Motor: API de Zabbix (independiente de la base de datos) · Módulo de reportes v1.1 ·
		Red Comunitaria y Científica Las Lagunitas</div>
<?php endif; ?>
</div>
<?php
$html = ob_get_clean();

(new CHtmlPage())
	->setTitle('Disponibilidad de la red')
	->addItem(new CObject($html))
	->show();
