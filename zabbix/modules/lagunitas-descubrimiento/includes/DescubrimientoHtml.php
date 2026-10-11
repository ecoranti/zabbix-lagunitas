<?php declare(strict_types = 0);

namespace Modules\LagunitasDescubrimiento\Includes;

/**
 * Bloque de resultados (se usa al cargar la página y en cada actualización por JS).
 */
class DescubrimientoHtml {

	public static function e($v): string {
		return htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');
	}

	private static function tipo(array $e): string {
		return '<span class="ld-tipo ld-tipo-'.self::e($e['tipo']).'">'.self::e($e['tipo_texto']).'</span>';
	}

	private static function host(array $e): string {
		return '<a href="zabbix.php?action=host.edit&amp;hostid='.self::e($e['hostid']).'" target="_blank" rel="noopener">'
			.self::e($e['nombre_host']).'</a> <span class="ld-muted">'.self::e($e['host']).'</span>';
	}

	public static function resultados(?array $r): string {
		if ($r === null) {
			return '<div class="ld-empty">Todavía no se hizo ningún escaneo. Ingresá un rango y presioná '
				.'<b>Escanear</b>.</div>';
		}

		$out = '<div class="ld-resumen">'
			.self::tarjeta($r['total'], 'Respondieron', 'info')
			.self::tarjeta(count($r['nuevos']), 'Nuevos (no inventariados)', count($r['nuevos']) ? 'warn' : 'ok')
			.self::tarjeta(count($r['conocidos']), 'Ya inventariados', 'ok')
			.self::tarjeta(count($r['ausentes']), 'Inventariados sin respuesta', count($r['ausentes']) ? 'bad' : 'ok')
			.'</div>';

		// ---------------------------------------------------------------- nuevos + propuesta
		$out .= '<section class="ld-sec"><div class="ld-sec-head"><h4>Equipos nuevos</h4>'
			.'<span class="ld-muted">Marcá los que querés sumar: la propuesta de abajo se arma con esos.</span></div>';
		if (!$r['nuevos']) {
			$out .= '<div class="ld-empty">No hay equipos nuevos en el rango. Todo lo que respondió ya está en el inventario.</div>';
		}
		else {
			$out .= '<div class="ld-table-wrap"><table class="ld-table"><thead><tr>'
				.'<th class="ld-check"><input type="checkbox" data-ld-todos checked aria-label="Seleccionar todos"></th>'
				.'<th>IP</th><th>Tipo detectado</th><th>Nombre (SNMP / DNS)</th><th>Descripción SNMP</th>'
				.'<th>Perfiles sugeridos</th></tr></thead><tbody>';
			foreach ($r['nuevos'] as $e) {
				$out .= '<tr><td class="ld-check"><input type="checkbox" data-ld-sel checked data-yaml="'.self::e($e['yaml']).'"'
					.' aria-label="Incluir '.self::e($e['ip']).'"></td>'
					.'<td class="ld-mono">'.self::e($e['ip']).'</td>'
					.'<td>'.self::tipo($e).'</td>'
					.'<td>'.self::e($e['sysname'] ?: ($e['dns'] !== $e['ip'] ? $e['dns'] : '')).'</td>'
					.'<td class="ld-muted ld-descr">'.self::e($e['sysdescr']).'</td>'
					.'<td class="ld-mono">'.self::e(implode(', ', $e['perfiles'])).'</td></tr>';
			}
			$out .= '</tbody></table></div>'
				.'<div class="ld-propuesta"><div class="ld-propuesta-head"><b>Propuesta para el inventario</b>'
				.'<span class="ld-muted">Pegar dentro de <code>dispositivos:</code> del sitio que corresponda (o en '
				.'<code>elementos:</code> agregando rol, estado y mapa), completar lo marcado <code>COMPLETAR</code> y '
				.'aplicar con <code>bin/lagunitas aprovisionar</code>.</span>'
				.'<button type="button" class="ld-btn" data-ld-copiar>Copiar</button></div>'
				.'<textarea class="ld-yaml" data-ld-yaml readonly spellcheck="false" rows="12"></textarea></div>';
		}
		$out .= '</section>';

		// ---------------------------------------------------------------- inventariados
		if ($r['conocidos']) {
			$out .= '<section class="ld-sec"><div class="ld-sec-head"><h4>Ya inventariados</h4></div>'
				.'<div class="ld-table-wrap"><table class="ld-table"><thead><tr><th>IP</th><th>Equipo en Zabbix</th>'
				.'<th>Tipo detectado</th><th>Sugerencia</th></tr></thead><tbody>';
			foreach ($r['conocidos'] as $e) {
				$sug = $e['falta_perfil']
					? 'Responde SNMP pero no tiene el perfil <code>'.self::e($e['falta_perfil']).'</code>: agregarlo en el inventario.'
					: '<span class="ld-muted">—</span>';
				$out .= '<tr><td class="ld-mono">'.self::e($e['ip']).'</td><td>'.self::host($e).'</td><td>'.self::tipo($e)
					.'</td><td>'.$sug.'</td></tr>';
			}
			$out .= '</tbody></table></div></section>';
		}

		// ---------------------------------------------------------------- ausentes
		if ($r['ausentes']) {
			$out .= '<section class="ld-sec"><div class="ld-sec-head"><h4>Inventariados que no respondieron</h4>'
				.'<span class="ld-muted">Equipos monitoreados con IP en el rango que no contestaron a ningún chequeo.</span></div>'
				.'<div class="ld-table-wrap"><table class="ld-table"><thead><tr><th>IP</th><th>Equipo en Zabbix</th>'
				.'</tr></thead><tbody>';
			foreach ($r['ausentes'] as $e) {
				$out .= '<tr><td class="ld-mono">'.self::e($e['ip']).'</td><td>'.self::host($e).'</td></tr>';
			}
			$out .= '</tbody></table></div></section>';
		}

		return $out;
	}

	private static function tarjeta(int $n, string $texto, string $nivel): string {
		return '<div class="ld-card ld-card-'.$nivel.'"><b>'.$n.'</b><span>'.self::e($texto).'</span></div>';
	}
}
