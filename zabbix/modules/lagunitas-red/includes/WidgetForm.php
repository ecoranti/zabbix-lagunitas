<?php declare(strict_types = 0);

namespace Modules\LagunitasRed\Includes;

use Zabbix\Widgets\CWidgetForm;
use Zabbix\Widgets\Fields\{CWidgetFieldCheckBox, CWidgetFieldMultiSelectGroup};

class WidgetForm extends CWidgetForm {

	public function addFields(): self {
		return $this
			->addField(new CWidgetFieldMultiSelectGroup('groupids', 'Grupos de hosts'))
			->addField((new CWidgetFieldCheckBox('show_disabled', 'Mostrar equipos no monitoreados'))
				->setDefault(1)
			);
	}
}
