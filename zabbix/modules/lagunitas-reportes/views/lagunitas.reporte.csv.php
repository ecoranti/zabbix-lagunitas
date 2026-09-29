<?php declare(strict_types = 0);

/**
 * Exportación CSV del reporte (separador ";" y BOM UTF-8 para abrir directo en Excel/LibreOffice).
 *
 * @var CView $this
 * @var array $data
 */

$f = $data['filtros'];

$out = fopen('php://output', 'w');
fwrite($out, "\xEF\xBB\xBF");
fputcsv($out, ['Período', date('d/m/Y H:i', $f['from']).' - '.date('d/m/Y H:i', $f['to']),
	'Objetivo SLA (%)', $f['slo']], ';');
fputcsv($out, ['Rol', 'Equipo', 'Nombre técnico', 'IP', 'Depende de', 'Disponibilidad propia (%)',
	'Disponibilidad del servicio (%)', 'Tiempo caído (min)', 'Tiempo sin servicio (min)', 'Caídas',
	'MTTR (min)', 'Mayor caída (min)', 'Latencia media (ms)', 'Pérdida media (%)', 'Advertencias',
	'Equipos dependientes', 'Cumple SLA'], ';');

$n = static fn(?float $v, int $d = 3) => $v === null ? '' : number_format($v, $d, ',', '');

foreach ($data['reporte']['filas'] as $r) {
	fputcsv($out, [
		$r['rol'], $r['nombre'], $r['host'], $r['ip'], $r['padre'],
		$n($r['disp_propia']), $n($r['disp_servicio']),
		$n($r['caida_propia'] / 60, 1), $n($r['caida_servicio'] / 60, 1), $r['incidentes'],
		$r['mttr'] !== null ? $n($r['mttr'] / 60, 1) : '', $n($r['mayor'] / 60, 1),
		$n($r['latencia_ms'], 2), $n($r['perdida'], 2), $r['avisos'], $r['dependientes'],
		$r['cumple'] ? 'Sí' : 'No'
	], ';');
}
fclose($out);
