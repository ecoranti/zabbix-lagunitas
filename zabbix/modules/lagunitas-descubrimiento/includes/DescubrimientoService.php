<?php declare(strict_types = 0);

namespace Modules\LagunitasDescubrimiento\Includes;

use API;

/**
 * Detectar y proponer: escaneo con el network discovery nativo de Zabbix y comparación con los
 * hosts aprovisionados desde el inventario.
 *
 * Misma regla y misma clasificación que lagunitas/descubrimiento.py (comando
 * `bin/lagunitas descubrir`): si se cambia una, cambiar la otra.
 */
class DescubrimientoService {

	public const REGLA = 'Las Lagunitas - Escaneo bajo demanda';
	public const INTERVALO = '1d';
	public const MACRO_COMUNIDAD = '{$SNMP_COMMUNITY}';
	public const MAX_DIRECCIONES = 1024;
	public const GRUPO = 'Las Lagunitas';

	public const OID_DESCR = '1.3.6.1.2.1.1.1.0';
	public const OID_OBJETO = '1.3.6.1.2.1.1.2.0';
	public const OID_NOMBRE = '1.3.6.1.2.1.1.5.0';

	private const OID_UBIQUITI = ['1.3.6.1.4.1.10002.', '1.3.6.1.4.1.41112.'];
	private const OID_MIKROTIK = ['1.3.6.1.4.1.14988.'];

	/** Template SNMP que corresponde a cada tipo detectado (para sugerir perfiles faltantes). */
	private const TEMPLATE_TIPO = [
		'airmax' => ['Lagunitas - Ubiquiti airMAX por SNMP', 'airos_snmp'],
		'mikrotik' => ['Lagunitas - Mikrotik por SNMP', 'mikrotik_snmp']
	];

	public const TIPOS = [
		'mikrotik' => 'Router Mikrotik (SNMP)',
		'airmax' => 'Radio Ubiquiti airMAX (SNMP)',
		'snmp' => 'Responde SNMP (no es airMAX ni Mikrotik)',
		'web' => 'Gestión web, sin SNMP (UniFi, airCube u otro)',
		'ping' => 'Solo responde ping'
	];

	public static function dchecks(): array {
		$snmp = ['type' => SVC_SNMPv2c, 'ports' => '161', 'snmp_community' => self::MACRO_COMUNIDAD];

		return [
			['type' => SVC_ICMPPING],
			$snmp + ['key_' => self::OID_DESCR],
			$snmp + ['key_' => self::OID_OBJETO],
			$snmp + ['key_' => self::OID_NOMBRE],
			['type' => SVC_HTTPS, 'ports' => '443']
		];
	}

	/**
	 * Expande un rango con la sintaxis que acepta Zabbix (CIDR hasta /30, a.b.c.d-e en el último
	 * octeto, IPs sueltas, separados por comas) a una lista de enteros.
	 *
	 * @return int[]|string  Lista de IPs o mensaje de error.
	 */
	public static function direcciones(string $rango) {
		$out = [];
		$ip = '(\d{1,3}(?:\.\d{1,3}){3})';

		foreach (array_filter(array_map('trim', explode(',', $rango)), 'strlen') as $parte) {
			if (preg_match('#^'.$ip.'/(\d{1,2})$#', $parte, $m)) {
				$base = ip2long($m[1]);
				$bits = (int) $m[2];
				if ($base === false || $bits > 30) {
					return 'rango inválido: '.$parte.' (máscara hasta /30; para un solo equipo poné la IP sola)';
				}
				if ($bits < 22) {
					return 'el rango supera '.self::MAX_DIRECCIONES.' direcciones; escaneá por partes (ej. /24)';
				}
				$red = $base & ((~0 << (32 - $bits)) & 0xFFFFFFFF);
				$ini = $red + 1;
				$fin = $red + (1 << (32 - $bits)) - 2;
			}
			elseif (preg_match('#^'.$ip.'-(\d{1,3})$#', $parte, $m)) {
				$ini = ip2long($m[1]);
				$fin = $ini === false || $m[2] > 255 ? false : ($ini & 0xFFFFFF00) + (int) $m[2];
				if ($ini === false || $fin === false || $fin < $ini) {
					return 'rango inválido: '.$parte.' (el rango va en el último octeto, ej. 10.50.0.1-60)';
				}
			}
			elseif (preg_match('#^'.$ip.'$#', $parte) && ($l = ip2long($parte)) !== false) {
				$ini = $fin = $l;
			}
			else {
				return 'rango inválido: '.$parte.' (usar 10.50.0.0/24, 10.50.0.1-60 o IPs separadas por comas)';
			}

			if (count($out) + ($fin - $ini + 1) > self::MAX_DIRECCIONES) {
				return 'el rango supera '.self::MAX_DIRECCIONES.' direcciones; escaneá por partes (ej. /24)';
			}
			for ($i = $ini; $i <= $fin; $i++) {
				$out[] = $i;
			}
		}

		return $out ?: 'rango vacío';
	}

	public static function regla(): ?array {
		$r = API::DRule()->get([
			'output' => ['druleid', 'iprange'],
			'selectDChecks' => ['dcheckid', 'type', 'key_'],
			'filter' => ['name' => self::REGLA]
		]);

		return $r ? $r[0] : null;
	}

	/**
	 * (Re)crea la regla con el rango indicado. Recrearla descarta los resultados anteriores y el
	 * Zabbix server la ejecuta en cuanto sincroniza la configuración (entre 10 y 60 s).
	 */
	public static function iniciar(string $rango): array {
		$rango = preg_replace('/\s+/', '', $rango);
		$ips = self::direcciones($rango);
		if (is_string($ips)) {
			return ['ok' => false, 'error' => ucfirst($ips).'.'];
		}

		$viejas = API::DRule()->get(['output' => ['druleid'], 'filter' => ['name' => self::REGLA]]);
		if ($viejas && API::DRule()->delete(array_column($viejas, 'druleid')) === false) {
			return ['ok' => false, 'error' => self::errorApi('No se pudo borrar el escaneo anterior')];
		}

		$r = API::DRule()->create([
			'name' => self::REGLA,
			'iprange' => $rango,
			'delay' => self::INTERVALO,
			'status' => DRULE_STATUS_ACTIVE,
			'dchecks' => self::dchecks()
		]);
		if ($r === false) {
			return ['ok' => false, 'error' => self::errorApi('No se pudo crear la regla de descubrimiento')];
		}

		return ['ok' => true, 'druleid' => $r['druleids'][0], 'rango' => $rango, 'direcciones' => count($ips),
			'comunidad' => (bool) API::UserMacro()->get([
				'output' => ['globalmacroid'], 'globalmacro' => true, 'filter' => ['macro' => self::MACRO_COMUNIDAD]
			])
		];
	}

	private static function errorApi(string $texto): string {
		$msgs = array_column(get_and_clear_messages(), 'message');

		return $texto.($msgs ? ': '.implode(' ', $msgs) : '.');
	}

	/** Equipos que respondieron al último escaneo, uno por IP, ya clasificados. */
	public static function equipos(array $regla): array {
		$campo = [];
		foreach ($regla['dchecks'] as $c) {
			$t = (int) $c['type'];
			$campo[$c['dcheckid']] = $t == SVC_ICMPPING ? 'icmp' : ($t == SVC_HTTPS ? 'https' : ([
				self::OID_DESCR => 'descr', self::OID_OBJETO => 'objeto', self::OID_NOMBRE => 'nombre'
			][$c['key_']] ?? 'snmp'));
		}

		$equipos = [];
		$dhosts = API::DHost()->get([
			'output' => ['dhostid'],
			'druleids' => [$regla['druleid']],
			'selectDServices' => ['dcheckid', 'ip', 'dns', 'value', 'status', 'lastup']
		]);
		foreach ($dhosts as $dh) {
			foreach ($dh['dservices'] as $s) {
				if ($s['status'] != DOBJECT_STATUS_UP) {
					continue;
				}
				$ip = $s['ip'];
				$equipos[$ip] ??= ['ip' => $ip, 'dns' => $s['dns'], 'servicios' => [], 'visto' => 0];
				$equipos[$ip]['servicios'][$campo[$s['dcheckid']] ?? 'otro'] = $s['value'];
				$equipos[$ip]['visto'] = max($equipos[$ip]['visto'], (int) $s['lastup']);
			}
		}
		uksort($equipos, static fn($a, $b) => ip2long($a) <=> ip2long($b));

		return array_map([self::class, 'clasificar'], array_values($equipos));
	}

	public static function clasificar(array $e): array {
		$s = $e['servicios'];
		$descr = (string) ($s['descr'] ?? '');
		$objeto = ltrim((string) ($s['objeto'] ?? ''), '.');
		$nombre = trim((string) ($s['nombre'] ?? ''));
		$d = strtolower($descr);
		$empieza = static function(string $txt, array $prefijos): bool {
			foreach ($prefijos as $p) {
				if (strpos($txt, $p) === 0) {
					return true;
				}
			}

			return false;
		};
		$snmp = (bool) array_intersect(['descr', 'objeto', 'nombre', 'snmp'], array_keys($s));

		$e += ['sysname' => $nombre, 'sysdescr' => $descr, 'funcion' => null, 'modelo' => '',
			'snmp' => $snmp, 'https' => array_key_exists('https', $s)];

		if (strpos($d, 'routeros') !== false || $empieza($objeto, self::OID_MIKROTIK)) {
			$modelo = stripos($descr, 'RouterOS') !== false ? trim(substr($descr, stripos($descr, 'RouterOS') + 8)) : '';
			$e['tipo'] = 'mikrotik';
			$e['perfiles'] = ['icmp', 'mikrotik_snmp'];
			$e['funcion'] = 'router';
			$e['modelo'] = trim('Mikrotik '.$modelo);
		}
		elseif ($empieza($objeto, self::OID_UBIQUITI) || strpos($d, 'airos') !== false || strpos($d, 'ubnt') !== false) {
			$e['tipo'] = 'airmax';
			$e['perfiles'] = ['icmp', 'airos_snmp'];
		}
		else {
			$e['tipo'] = $snmp ? 'snmp' : ($e['https'] ? 'web' : 'ping');
			$e['perfiles'] = ['icmp'];
		}
		$e['tipo_texto'] = self::TIPOS[$e['tipo']];

		if ($nombre !== '') {
			$base = $nombre;
		}
		elseif ($e['dns'] !== '' && $e['dns'] !== $e['ip']) {
			$base = explode('.', $e['dns'])[0];
		}
		else {
			$base = 'Equipo_'.str_replace('.', '_', $e['ip']);
		}
		$e['host_sugerido'] = self::nombreTecnico($base);

		return $e;
	}

	public static function nombreTecnico(string $texto): string {
		$t = trim(preg_replace('/[^A-Za-z0-9_.-]+/', '_', trim($texto)), '_');

		return substr($t, 0, 60) ?: 'Equipo';
	}

	/**
	 * Compara lo descubierto con los hosts de Zabbix (que el provisionador crea desde el inventario).
	 *
	 * @return array{nuevos: array, conocidos: array, ausentes: array, total: int, firma: string}
	 */
	public static function analizar(array $regla, bool $ignorar_ping = false): array {
		$equipos = self::equipos($regla);
		if ($ignorar_ping) {
			$equipos = array_values(array_filter($equipos, static fn($e) => $e['tipo'] !== 'ping'));
		}

		$hosts = API::Host()->get([
			'output' => ['hostid', 'host', 'name', 'status'],
			'selectInterfaces' => ['ip'],
			'selectParentTemplates' => ['name'],
			'selectHostGroups' => ['name']
		]);
		$por_ip = [];
		foreach ($hosts as $h) {
			foreach ($h['interfaces'] as $i) {
				$por_ip[$i['ip']] ??= $h;
			}
		}

		$nuevos = $conocidos = [];
		$vistos = [];
		foreach ($equipos as $e) {
			$vistos[$e['ip']] = true;
			$h = $por_ip[$e['ip']] ?? null;
			if ($h === null) {
				$nuevos[] = $e;
				continue;
			}
			$e['hostid'] = $h['hostid'];
			$e['host'] = $h['host'];
			$e['nombre_host'] = $h['name'];
			$e['falta_perfil'] = null;
			if (array_key_exists($e['tipo'], self::TEMPLATE_TIPO)) {
				[$tpl, $perfil] = self::TEMPLATE_TIPO[$e['tipo']];
				if (!in_array($tpl, array_column($h['parentTemplates'], 'name'), true)) {
					$e['falta_perfil'] = $perfil;
				}
			}
			$conocidos[] = $e;
		}

		// Hosts de la red, monitoreados, cuya IP está en el rango y no respondieron.
		$en_rango = array_flip(is_array($ips = self::direcciones($regla['iprange'])) ? $ips : []);
		$ausentes = [];
		foreach ($hosts as $h) {
			if ($h['status'] != HOST_STATUS_MONITORED
					|| !preg_grep('#^'.preg_quote(self::GRUPO, '#').'(/|$)#', array_column($h['hostgroups'], 'name'))) {
				continue;
			}
			foreach ($h['interfaces'] as $i) {
				if (($l = ip2long($i['ip'])) !== false && isset($en_rango[$l]) && !isset($vistos[$i['ip']])) {
					$ausentes[$i['ip']] = ['ip' => $i['ip'], 'hostid' => $h['hostid'], 'host' => $h['host'],
						'nombre_host' => $h['name']];
				}
			}
		}
		uksort($ausentes, static fn($a, $b) => ip2long($a) <=> ip2long($b));

		$usados = array_flip(array_column($hosts, 'host'));
		foreach ($nuevos as &$e) {
			$host = $e['host_sugerido'];
			for ($n = 2; isset($usados[$host]); $n++) {
				$host = $e['host_sugerido'].'_'.$n;
			}
			$usados[$host] = true;
			$e['yaml'] = self::bloqueYaml($e, $host);
		}
		unset($e);

		$firma = md5(json_encode(array_map(static fn($e) => [$e['ip'], array_keys($e['servicios'])], $equipos)));

		return ['rango' => $regla['iprange'], 'nuevos' => $nuevos, 'conocidos' => $conocidos,
			'ausentes' => array_values($ausentes), 'total' => count($equipos), 'firma' => $firma];
	}

	public static function bloqueYaml(array $e, string $host): string {
		$coment = '  # '.$e['ip'].' — '.$e['tipo_texto'].($e['sysdescr'] !== '' ? ' — '.$e['sysdescr'] : '');
		$nombre = $e['sysname'] !== '' ? $e['sysname'] : str_replace('_', ' ', $host);

		return implode("\n", [
			str_replace(["\r", "\n"], ' ', $coment),
			'  - host: '.$host,
			'    nombre: '.self::yamlTexto($nombre),
			'    ip: '.$e['ip'],
			'    perfiles: ['.implode(', ', $e['perfiles']).']',
			$e['funcion'] ? '    funcion: '.$e['funcion'] : '    funcion: COMPLETAR   # ap | sm | ptp | router | switch | otro',
			$e['modelo'] !== '' ? '    modelo: '.self::yamlTexto($e['modelo']) : '    modelo: COMPLETAR',
			'    padre: COMPLETAR      # equipo del que depende (por defecto, el principal del sitio)'
		])."\n";
	}

	/** Comillas solo si el texto puede romper el YAML (':' '#' o caracteres especiales al inicio). */
	private static function yamlTexto(string $t): string {
		$t = str_replace(["\r", "\n"], ' ', $t);

		return preg_match('/[:#]|^[\s\-?\[\]{},&*!|>\'"%@`]/', $t) ? json_encode($t, JSON_UNESCAPED_UNICODE) : $t;
	}
}
