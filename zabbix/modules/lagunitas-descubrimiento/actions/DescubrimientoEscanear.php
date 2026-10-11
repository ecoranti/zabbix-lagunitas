<?php declare(strict_types = 0);

namespace Modules\LagunitasDescubrimiento\Actions;

use CController;
use CControllerResponseData;
use Modules\LagunitasDescubrimiento\Includes\DescubrimientoService;

/**
 * POST: (re)crea la regla de descubrimiento con el rango indicado. Responde JSON.
 */
class DescubrimientoEscanear extends CController {

	protected function checkInput(): bool {
		$ok = $this->validateInput(['rango' => 'required|string|not_empty']);

		if (!$ok) {
			$this->setResponse(new CControllerResponseData(['json' => json_encode([
				'ok' => false, 'error' => 'Indicá un rango de IPs, por ejemplo 10.50.0.0/24.'
			])]));
		}

		return $ok;
	}

	protected function checkPermissions(): bool {
		return $this->getUserType() >= USER_TYPE_ZABBIX_ADMIN;
	}

	protected function doAction(): void {
		$r = DescubrimientoService::iniciar(trim($this->getInput('rango')));

		$this->setResponse(new CControllerResponseData(['json' => json_encode($r)]));
	}
}
