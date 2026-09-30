<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes\Actions;

use CControllerResponseData;
use Modules\LagunitasReportes\Includes\ReporteService;

class ReporteCsv extends ReporteVista {

	protected function doAction(): void {
		$f = $this->filtros();
		$response = new CControllerResponseData([
			'filtros' => $f,
			'reporte' => ReporteService::construir($f)
		]);
		$response->setFileName(sprintf('disponibilidad_lagunitas_%s_%s.csv', date('Ymd', $f['from']),
			date('Ymd', $f['to'])));
		$this->setResponse($response);
	}
}
