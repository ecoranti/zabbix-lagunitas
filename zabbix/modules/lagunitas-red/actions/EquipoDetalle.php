<?php declare(strict_types = 0);

namespace Modules\LagunitasRed\Actions;

use API;
use CController;
use CControllerResponseData;
use Modules\LagunitasRed\Includes\RedService;

/**
 * Detalle de un equipo (HTML para el modal del widget): zabbix.php?action=lagunitas.equipo&hostid=N
 */
class EquipoDetalle extends CController {

	public function init(): void {
		$this->disableCsrfValidation(); // solo lectura
	}

	protected function checkInput(): bool {
		return $this->validateInput(['hostid' => 'required|db hosts.hostid']);
	}

	protected function checkPermissions(): bool {
		if ($this->getUserType() < USER_TYPE_ZABBIX_USER) {
			return false;
		}

		return (bool) API::Host()->get([
			'output' => [],
			'hostids' => [$this->getInput('hostid')]
		]);
	}

	protected function doAction(): void {
		$hostid = $this->getInput('hostid');

		// Se carga la red completa del grupo para resolver padres, hijos y afectados.
		$red = RedService::recolectar([], true);
		if (!array_key_exists($hostid, $red['equipos'])) {
			$red = RedService::recolectar([], true, [$hostid]);
		}

		// Incidentes de los últimos 30 días (problemas ya resueltos o en curso).
		$eventos = API::Event()->get([
			'output' => ['eventid', 'clock', 'name', 'severity', 'r_eventid', 'acknowledged'],
			'hostids' => [$hostid],
			'source' => EVENT_SOURCE_TRIGGERS,
			'object' => EVENT_OBJECT_TRIGGER,
			'value' => TRIGGER_VALUE_TRUE,
			'time_from' => time() - 30 * 86400,
			'sortfield' => ['clock', 'eventid'],
			'sortorder' => ZBX_SORT_DOWN,
			'limit' => 20
		]);
		$recuperaciones = [];
		$r_ids = array_filter(array_column($eventos, 'r_eventid'));
		if ($r_ids) {
			$recuperaciones = array_column(API::Event()->get([
				'output' => ['eventid', 'clock'],
				'eventids' => array_values($r_ids)
			]), 'clock', 'eventid');
		}
		foreach ($eventos as &$ev) {
			$ev['r_clock'] = $ev['r_eventid'] != 0 ? (int) ($recuperaciones[$ev['r_eventid']] ?? 0) : null;
		}
		unset($ev);

		$response = new CControllerResponseData([
			'hostid' => $hostid,
			'red' => $red,
			'eventos' => $eventos,
			'descubiertos' => RedService::descubiertos($hostid)
		]);
		$this->setResponse($response);
	}
}
