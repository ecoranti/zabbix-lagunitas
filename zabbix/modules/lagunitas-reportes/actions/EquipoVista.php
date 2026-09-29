<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes\Actions;

use API;
use CControllerResponseData;
use Modules\LagunitasReportes\Includes\{EquipoService, ReporteService};

/** Detalle técnico de un equipo: zabbix.php?action=lagunitas.reporte.equipo&hostid=N&<filtros> */
class EquipoVista extends ReporteVista {

	protected function checkInput(): bool {
		return parent::checkInput() && $this->hasInput('hostid') && ctype_digit($this->getInput('hostid'));
	}

	protected function checkPermissions(): bool {
		return parent::checkPermissions()
			&& (bool) API::Host()->get(['output' => [], 'hostids' => [$this->getInput('hostid')]]);
	}

	protected function doAction(): void {
		$f = $this->filtros();
		$detalle = EquipoService::construir($this->getInput('hostid'), $f);
		$response = new CControllerResponseData([
			'filtros' => $f,
			'detalle' => $detalle,
			'generado' => time()
		]);
		$response->setTitle('Detalle técnico: '.($detalle['host']['name'] ?? ''));
		$this->setResponse($response);
	}
}
