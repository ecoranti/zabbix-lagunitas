<?php declare(strict_types = 0);

/**
 * Widget "Red Las Lagunitas".
 *
 * @var CView $this
 * @var array $data
 */

use Modules\LagunitasRed\Includes\Html;

$red = $data['red'];

if (!$red['equipos']) {
	$html = '<div class="lg-red"><div class="lg-empty">No hay equipos para mostrar. Revisá los grupos '
		.'configurados en el widget (por defecto: "Las Lagunitas").</div></div>';
}
else {
	$html = '<div class="lg-red">'.Html::tarjetas($red['resumen']).Html::barraFiltros($red['resumen']['total']);
	foreach ($red['secciones'] as $titulo => $ids) {
		$html .= Html::seccion($titulo, $ids, $red['equipos']);
	}
	$html .= '<div class="lg-none" hidden>Ningún equipo coincide con el filtro.</div>'
		.'<div class="lg-foot">Clic en un equipo para ver su detalle · Actualizado: '
		.Html::e(date('d/m/Y H:i:s', $data['actualizado'])).'</div></div>';
}

(new CWidgetView($data))
	->addItem(new CObject($html))
	->show();
