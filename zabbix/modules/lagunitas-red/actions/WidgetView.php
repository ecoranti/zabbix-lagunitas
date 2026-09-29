<?php declare(strict_types = 0);

namespace Modules\LagunitasRed\Actions;

use CControllerDashboardWidgetView;
use CControllerResponseData;
use Modules\LagunitasRed\Includes\RedService;

class WidgetView extends CControllerDashboardWidgetView {

	protected function doAction(): void {
		$red = RedService::recolectar($this->fields_values['groupids'], (bool) $this->fields_values['show_disabled']);

		$this->setResponse(new CControllerResponseData([
			'name' => $this->getInput('name', $this->widget->getDefaultName()),
			'red' => $red,
			'actualizado' => time(),
			'user' => [
				'debug_mode' => $this->getDebugMode()
			]
		]));
	}
}
