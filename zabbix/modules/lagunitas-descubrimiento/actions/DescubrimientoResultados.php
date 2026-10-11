<?php declare(strict_types = 0);

namespace Modules\LagunitasDescubrimiento\Actions;

use CController;
use CControllerResponseData;
use CControllerResponseFatal;
use Modules\LagunitasDescubrimiento\Includes\{DescubrimientoHtml, DescubrimientoService};

/**
 * GET: resultados del último escaneo (HTML ya armado + firma para detectar cambios). Responde JSON.
 */
class DescubrimientoResultados extends CController {

	public function init(): void {
		$this->disableCsrfValidation(); // solo lectura
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
		$regla = DescubrimientoService::regla();
		$res = $regla ? DescubrimientoService::analizar($regla, (bool) $this->getInput('ignorar_ping', 0)) : null;

		$this->setResponse(new CControllerResponseData(['json' => json_encode([
			'ok' => true,
			'rango' => $regla['iprange'] ?? '',
			'total' => $res ? $res['total'] : 0,
			'firma' => $res ? $res['firma'] : '',
			'html' => DescubrimientoHtml::resultados($res)
		])]));
	}
}
