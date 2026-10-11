<?php declare(strict_types = 0);

namespace Modules\LagunitasDescubrimiento\Actions;

use CController;
use CControllerResponseData;
use CControllerResponseFatal;
use Modules\LagunitasDescubrimiento\Includes\DescubrimientoService;

/**
 * Monitoring -> Descubrimiento de equipos: formulario de escaneo y resultados del último escaneo.
 */
class DescubrimientoVista extends CController {

	public function init(): void {
		$this->disableCsrfValidation(); // página GET de solo lectura; el escaneo va por POST con token
	}

	protected function checkInput(): bool {
		$ok = $this->validateInput(['ignorar_ping' => 'in 0,1']);

		if (!$ok) {
			$this->setResponse(new CControllerResponseFatal());
		}

		return $ok;
	}

	protected function checkPermissions(): bool {
		return $this->getUserType() >= USER_TYPE_ZABBIX_ADMIN;
	}

	protected function doAction(): void {
		$ignorar_ping = (bool) $this->getInput('ignorar_ping', 0);
		$regla = DescubrimientoService::regla();

		$response = new CControllerResponseData([
			'regla' => $regla,
			'ignorar_ping' => $ignorar_ping,
			'resultado' => $regla ? DescubrimientoService::analizar($regla, $ignorar_ping) : null
		]);
		$response->setTitle('Descubrimiento de equipos');
		$this->setResponse($response);
	}
}
