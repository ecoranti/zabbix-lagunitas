<?php declare(strict_types = 0);

namespace Modules\LagunitasReportes;

use APP;
use CMenuItem;
use Zabbix\Core\CModule;

class Module extends CModule {

	public function init(): void {
		APP::Component()->get('menu.main')
			->findOrAdd(_('Reports'))
				->getSubmenu()
					->add((new CMenuItem('Disponibilidad de la red'))->setAction('lagunitas.reporte'));
	}
}
