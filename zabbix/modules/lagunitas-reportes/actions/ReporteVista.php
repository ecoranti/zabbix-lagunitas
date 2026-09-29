<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes\Actions;

use CController;
use CControllerResponseData;
use Modules\LagunitasReportes\Includes\ReporteService;

class ReporteVista extends CController {

	public function init(): void {
		$this->disableCsrfValidation(); // formulario GET de solo lectura
	}

	protected function checkInput(): bool {
		return $this->validateInput([
			'periodo' => 'in '.implode(',', array_keys(ReporteService::PERIODOS)),
			'desde' => 'string',
			'hasta' => 'string',
			'rol' => 'string',
			'slo' => 'string',
			'vista' => 'in tecnica,gerencial'
		]);
	}

	protected function checkPermissions(): bool {
		return $this->getUserType() >= USER_TYPE_ZABBIX_USER;
	}

	protected function doAction(): void {
		$f = ReporteService::normalizar([
			'periodo' => $this->getInput('periodo', '7d'),
			'desde' => $this->getInput('desde', date('Y-m-d', strtotime('-7 days'))),
			'hasta' => $this->getInput('hasta', date('Y-m-d')),
			'rol' => $this->getInput('rol', ''),
			'slo' => $this->getInput('slo', '99.5'),
			'vista' => $this->getInput('vista', 'tecnica')
		]);

		$response = new CControllerResponseData([
			'filtros' => $f,
			'reporte' => ReporteService::construir($f),
			'generado' => time()
		]);
		$response->setTitle('Disponibilidad de la red');
		$this->setResponse($response);
	}
}
