<?php declare(strict_types = 0);

namespace Modules\LagunitasRed;

use Zabbix\Core\CWidget;

class Widget extends CWidget {

	public function getDefaultName(): string {
		return 'Red Las Lagunitas';
	}
}
