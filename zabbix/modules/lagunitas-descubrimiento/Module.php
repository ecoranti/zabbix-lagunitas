<?php declare(strict_types = 0);

namespace Modules\LagunitasDescubrimiento;

use APP;
use CMenuItem;
use CWebUser;
use Zabbix\Core\CModule;

class Module extends CModule {

	public function init(): void {
		// Crear la regla de descubrimiento requiere un usuario Admin o Super admin.
		if (CWebUser::getType() < USER_TYPE_ZABBIX_ADMIN) {
			return;
		}

		APP::Component()->get('menu.main')
			->findOrAdd(_('Monitoring'))
				->getSubmenu()
					->add((new CMenuItem('Descubrimiento de equipos'))->setAction('lagunitas.descubrimiento'));
	}
}
