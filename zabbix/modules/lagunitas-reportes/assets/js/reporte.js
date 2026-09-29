/*
 * Reporte de disponibilidad y detalle técnico:
 * - Encabezado personalizable (organización y título), guardado en el navegador y aplicado
 *   al reporte, al detalle por equipo y a la impresión.
 * - Filtros de tablas (búsqueda y selects) en interfaces y problemas agrupados.
 * - Fechas visibles solo con período "Personalizado"; impresión expandiendo los detalles.
 */
(() => {
	const CLAVE = 'lagunitas.reporte.';

	const leer = (k) => {
		try {
			return localStorage.getItem(CLAVE + k);
		}
		catch (e) {
			return null;
		}
	};

	const guardar = (k, v) => {
		try {
			localStorage.setItem(CLAVE + k, v);
		}
		catch (e) {
			// almacenamiento bloqueado: el cambio vale solo para esta vista
		}
	};

	const aplicarEncabezado = (page) => {
		page.querySelectorAll('[data-lr-text]').forEach(el => {
			el.dataset.lrDefecto = el.dataset.lrDefecto || el.textContent;
			const v = leer(el.dataset.lrText);
			el.textContent = v || el.dataset.lrDefecto;
		});
	};

	const filtrarTabla = (sec) => {
		const q = (sec.querySelector('[data-lr-q]')?.value || '').trim().toLowerCase();
		const filtros = [...sec.querySelectorAll('[data-lr-f]')].map(s => [s.dataset.lrF, s.value]);
		let visibles = 0;
		const filas = sec.querySelectorAll('[data-lr-fila]');
		filas.forEach(fila => {
			let ok = !q || fila.dataset.q.includes(q);
			for (const [campo, valor] of filtros) {
				if (ok && valor !== '' && fila.dataset[campo] !== valor) {
					ok = false;
				}
			}
			fila.hidden = !ok;
			visibles += ok ? 1 : 0;
		});
		const contador = sec.querySelector('[data-lr-contador]');
		if (contador) {
			contador.textContent = `${visibles} de ${filas.length}`;
		}
	};

	const init = () => {
		const page = document.querySelector('.lr-page');
		if (page === null) {
			return;
		}

		aplicarEncabezado(page);
		page.querySelectorAll('[data-lr-input]').forEach(input => {
			const k = input.dataset.lrInput;
			const destino = page.querySelector(`[data-lr-text="${k}"]`);
			input.value = leer(k) || (destino ? destino.dataset.lrDefecto : '');
			input.addEventListener('input', () => {
				guardar(k, input.value.trim());
				aplicarEncabezado(page);
			});
		});

		page.querySelectorAll('[data-lr-filtrable]').forEach(sec => {
			sec.querySelectorAll('[data-lr-q], [data-lr-f]').forEach(el => {
				el.addEventListener('input', () => filtrarTabla(sec));
				el.addEventListener('change', () => filtrarTabla(sec));
			});
			filtrarTabla(sec);
		});

		const periodo = page.querySelector('[data-lr-periodo]');
		const fechas = page.querySelectorAll('.lr-fecha');
		const sync = () => fechas.forEach(f => f.hidden = periodo.value !== 'personalizado');
		if (periodo !== null) {
			periodo.addEventListener('change', sync);
			sync();
		}

		page.querySelectorAll('[data-lr-print]').forEach(btn => btn.addEventListener('click', () => {
			const cerrados = [...page.querySelectorAll('details:not([open])')];
			cerrados.forEach(d => d.open = true);
			window.print();
			cerrados.forEach(d => d.open = false);
		}));
	};

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	}
	else {
		init();
	}
})();
