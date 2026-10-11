<?php declare(strict_types = 0);

/**
 * Monitoring -> Descubrimiento de equipos.
 *
 * @var CView $this
 * @var array $data
 */

use Modules\LagunitasDescubrimiento\Includes\DescubrimientoHtml;

$e = [DescubrimientoHtml::class, 'e'];
$rango = $data['regla']['iprange'] ?? '';

ob_start();
?>
<div class="ld-page" data-ld-page
	data-url-escanear="zabbix.php?action=lagunitas.descubrimiento.escanear"
	data-url-resultados="zabbix.php?action=lagunitas.descubrimiento.resultados"
	data-csrf="<?= $e(CCsrfTokenHelper::get('lagunitas.descubrimiento.escanear')) ?>">
	<div class="ld-head">
		<div>
			<div class="ld-org">Red Comunitaria y Científica Las Lagunitas</div>
			<h1>Descubrimiento de equipos</h1>
			<p>Escanea un rango de IPs con ping, SNMP y HTTPS, y propone los equipos que todavía no están en el
				inventario. <b>No crea hosts</b>: el inventario sigue siendo la fuente de verdad.</p>
		</div>
	</div>

	<form class="ld-form" data-ld-form autocomplete="off">
		<label class="ld-rango">Red o rango a escanear
			<input type="text" name="rango" value="<?= $e($rango) ?>" placeholder="10.50.0.0/24"
				required spellcheck="false" data-ld-rango>
			<small>Ej.: <code>10.50.0.0/24</code> · <code>192.168.88.1-60</code> (último octeto) · IPs separadas por comas
				(máximo 1024 direcciones)</small>
		</label>
		<label class="ld-opcion">
			<input type="checkbox" data-ld-ignorar-ping<?= $data['ignorar_ping'] ? ' checked' : '' ?>>
			Ignorar equipos que solo responden ping
		</label>
		<div class="ld-acciones">
			<button type="submit" class="ld-btn ld-btn-primary" data-ld-escanear>Escanear</button>
			<button type="button" class="ld-btn" data-ld-actualizar<?= $rango === '' ? ' hidden' : '' ?>>Actualizar resultados</button>
		</div>
	</form>

	<div class="ld-estado" data-ld-estado role="status" aria-live="polite"<?= $rango === '' ? ' hidden' : '' ?>>
		<?= $rango !== '' ? 'Resultados del último escaneo de <b>'.$e($rango).'</b>.' : '' ?>
	</div>

	<div data-ld-resultados><?= DescubrimientoHtml::resultados($data['resultado']) ?></div>

	<div class="ld-foot">Usa la regla de descubrimiento «Las Lagunitas - Escaneo bajo demanda» (Data collection →
		Discovery), que se vuelve a crear en cada escaneo. La comunidad SNMP es la macro global
		<code>{$SNMP_COMMUNITY}</code>, que carga <code>bin/lagunitas aprovisionar</code> desde el <code>.env</code>.
		Desde la consola: <code>bin/lagunitas descubrir &lt;rango&gt;</code>.</div>
</div>
<?php
$html = ob_get_clean();

(new CHtmlPage())
	->setTitle('Descubrimiento de equipos')
	->addItem(new CObject($html))
	->show();
