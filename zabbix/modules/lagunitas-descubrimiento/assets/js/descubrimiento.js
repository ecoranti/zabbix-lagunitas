/*
 * Monitoring -> Descubrimiento de equipos.
 * - "Escanear": crea la regla de descubrimiento por POST y consulta los resultados cada 5 s
 *   hasta que dejan de cambiar.
 * - Selección de equipos nuevos -> propuesta YAML para pegar en el inventario.
 */
(() => {
	const POLL_MS = 5000;
	const ESTABLE_MS = 40000;   // sin cambios durante este tiempo = escaneo terminado
	const TIMEOUT_MS = 300000;  // espera máxima
	const ENCABEZADO = '# Propuesta generada desde Monitoring -> Descubrimiento de equipos.\n'
		+ '# Completar lo marcado COMPLETAR y aplicar con: bin/lagunitas aprovisionar\n';

	const iniciar = (page) => {
		const $ = (sel) => page.querySelector(sel);
		const form = $('[data-ld-form]');
		const rango = $('[data-ld-rango]');
		const ignorar = $('[data-ld-ignorar-ping]');
		const estado = $('[data-ld-estado]');
		const resultados = $('[data-ld-resultados]');
		const btnEscanear = $('[data-ld-escanear]');
		const btnActualizar = $('[data-ld-actualizar]');
		let timer = null;

		const mostrarEstado = (html, nivel = '') => {
			estado.hidden = false;
			estado.className = 'ld-estado' + (nivel ? ' ld-estado-' + nivel : '');
			estado.innerHTML = html;
		};

		const esc = (t) => String(t).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;',
			'"': '&quot;', "'": '&#39;'}[c]));

		const armarYaml = () => {
			const area = $('[data-ld-yaml]');
			if (!area) {
				return;
			}
			const sel = [...page.querySelectorAll('[data-ld-sel]')];
			const marcados = sel.filter(c => c.checked);
			area.value = marcados.length ? ENCABEZADO + marcados.map(c => c.dataset.yaml).join('\n') : '';
			const todos = $('[data-ld-todos]');
			if (todos) {
				todos.checked = marcados.length === sel.length;
				todos.indeterminate = marcados.length > 0 && marcados.length < sel.length;
			}
		};

		const cargar = async () => {
			const url = page.dataset.urlResultados + '&ignorar_ping=' + (ignorar.checked ? 1 : 0);
			const r = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
			if (!r.ok) {
				throw new Error('HTTP ' + r.status);
			}
			const data = await r.json();
			resultados.innerHTML = data.html;
			armarYaml();
			return data;
		};

		const detener = () => {
			clearTimeout(timer);
			timer = null;
			btnEscanear.disabled = false;
			btnEscanear.textContent = 'Escanear';
		};

		const seguir = (scan) => {
			timer = setTimeout(async () => {
				let data;
				try {
					data = await cargar();
				}
				catch (e) {
					mostrarEstado('No se pudieron leer los resultados (' + esc(e.message) + '). Reintentando…', 'warn');
					seguir(scan);
					return;
				}
				const ahora = Date.now();
				if (data.firma !== scan.firma) {
					scan.firma = data.firma;
					scan.desde = ahora;
				}
				const seg = Math.round((ahora - scan.inicio) / 1000);
				if (data.total > 0 && ahora - scan.desde >= ESTABLE_MS) {
					detener();
					mostrarEstado('Escaneo de <b>' + esc(scan.rango) + '</b> terminado: ' + data.total
						+ ' equipos respondieron.', 'ok');
					return;
				}
				if (ahora - scan.inicio >= TIMEOUT_MS) {
					detener();
					mostrarEstado(data.total > 0
						? 'Se dejó de esperar a los 5 minutos con ' + data.total + ' equipos. Puede seguir llegando '
							+ 'información: usá <b>Actualizar resultados</b>.'
						: 'Ningún equipo respondió en 5 minutos. Revisá el rango y que el Zabbix server llegue a esa red.',
						data.total > 0 ? 'warn' : 'bad');
					return;
				}
				mostrarEstado('<span class="ld-spinner" aria-hidden="true"></span> Escaneando <b>' + esc(scan.rango)
					+ '</b> (' + scan.direcciones + ' direcciones)… ' + seg + ' s · ' + data.total
					+ ' equipos respondieron hasta ahora.' + scan.aviso, 'run');
				seguir(scan);
			}, POLL_MS);
		};

		form.addEventListener('submit', async (ev) => {
			ev.preventDefault();
			if (timer !== null) {
				return;
			}
			btnEscanear.disabled = true;
			btnEscanear.textContent = 'Escaneando…';
			let r;
			try {
				const resp = await fetch(page.dataset.urlEscanear, {
					method: 'POST',
					credentials: 'same-origin',
					headers: {'Content-Type': 'application/x-www-form-urlencoded'},
					body: new URLSearchParams({rango: rango.value, _csrf_token: page.dataset.csrf})
				});
				r = await resp.json();
			}
			catch (e) {
				r = {ok: false, error: 'No se pudo iniciar el escaneo (' + e.message + '). Recargá la página e intentá de nuevo.'};
			}
			if (!r.ok) {
				detener();
				mostrarEstado(esc(r.error), 'bad');
				return;
			}
			btnActualizar.hidden = false;
			resultados.innerHTML = '';
			const aviso = r.comunidad ? '' : '<br>Aviso: no existe la macro global {$SNMP_COMMUNITY}; '
				+ 'ejecutá <code>bin/lagunitas aprovisionar</code> para que el escaneo pueda usar SNMP.';
			const scan = {rango: r.rango, direcciones: r.direcciones, inicio: Date.now(), desde: Date.now(),
				firma: null, aviso};
			mostrarEstado('<span class="ld-spinner" aria-hidden="true"></span> Escaneo de <b>' + esc(r.rango)
				+ '</b> iniciado. El Zabbix server toma la regla en 10 a 60 segundos…' + aviso, 'run');
			seguir(scan);
		});

		btnActualizar.addEventListener('click', async () => {
			try {
				const data = await cargar();
				if (timer === null) {
					mostrarEstado('Resultados del último escaneo de <b>' + esc(data.rango) + '</b>: ' + data.total
						+ ' equipos respondieron.');
				}
			}
			catch (e) {
				mostrarEstado('No se pudieron leer los resultados (' + esc(e.message) + ').', 'bad');
			}
		});

		ignorar.addEventListener('change', () => {
			if (timer === null && !btnActualizar.hidden) {
				btnActualizar.click();
			}
		});

		page.addEventListener('change', (ev) => {
			if (ev.target.matches('[data-ld-todos]')) {
				page.querySelectorAll('[data-ld-sel]').forEach(c => c.checked = ev.target.checked);
			}
			if (ev.target.matches('[data-ld-todos], [data-ld-sel]')) {
				armarYaml();
			}
		});

		page.addEventListener('click', async (ev) => {
			const btn = ev.target.closest('[data-ld-copiar]');
			if (!btn) {
				return;
			}
			const area = $('[data-ld-yaml]');
			try {
				await navigator.clipboard.writeText(area.value);
			}
			catch (e) {
				area.select();
				document.execCommand('copy');
			}
			btn.textContent = 'Copiado';
			setTimeout(() => btn.textContent = 'Copiar', 1500);
		});

		armarYaml();
	};

	const arrancar = () => document.querySelectorAll('[data-ld-page]').forEach(iniciar);

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', arrancar);
	}
	else {
		arrancar();
	}
})();
