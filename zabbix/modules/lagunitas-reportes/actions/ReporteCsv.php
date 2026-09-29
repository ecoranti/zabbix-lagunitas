<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes\Actions;

use CControllerResponseData;
use Modules\LagunitasReportes\Includes\ReporteService;

class ReporteCsv extends ReporteVista {

	protected function doAction(): void {
		$f = ReporteService::normalizar([
			'periodo' => $this->getInput('periodo', '7d'),
			'desde' => $this->getInput('desde', ''),
			'hasta' => $this->getInput('hasta', ''),
			'rol' => $this->getInput('rol', ''),
			'slo' => $this->getInput('slo', '99.5'),
			'vista' => $this->getInput('vista', 'tecnica')
		]);

		$response = new CControllerResponseData([
			'filtros' => $f,
			'reporte' => ReporteService::construir($f)
		]);
		$response->setFileName(sprintf('disponibilidad_lagunitas_%s_%s.csv', date('Ymd', $f['from']),
			date('Ymd', $f['to'])));
		$this->setResponse($response);
	}
}
