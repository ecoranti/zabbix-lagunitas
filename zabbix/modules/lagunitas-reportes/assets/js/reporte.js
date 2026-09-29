/* Reporte de disponibilidad: encabezado editable (persistido en el navegador), fechas e impresión. */
(() => {
	const CLAVE = 'lagunitas.reporte.';

	const init = () => {
		const page = document.querySelector('.lr-page');

		if (page === null) {
			return;
		}

		page.querySelectorAll('[data-lr-edit]').forEach(el => {
			try {
				const guardado = localStorage.getItem(CLAVE + el.dataset.lrEdit);
				if (guardado) {
					el.textContent = guardado;
				}
			}
			catch (e) {
				// almacenamiento bloqueado: se usa el texto por defecto
			}
			el.addEventListener('blur', () => {
				try {
					localStorage.setItem(CLAVE + el.dataset.lrEdit, el.textContent.trim());
				}
				catch (e) {
					// sin almacenamiento: el cambio vale solo para esta vista
				}
			});
			el.addEventListener('keydown', e => {
				if (e.key === 'Enter') {
					e.preventDefault();
					el.blur();
				}
			});
		});

		const periodo = page.querySelector('[data-lr-periodo]');
		const fechas = page.querySelectorAll('.lr-fecha');
		const sync = () => fechas.forEach(f => f.hidden = periodo.value !== 'personalizado');
		if (periodo !== null) {
			periodo.addEventListener('change', sync);
			sync();
		}

		const imprimir = page.querySelector('[data-lr-print]');
		if (imprimir !== null) {
			imprimir.addEventListener('click', () => {
				// Al imprimir se expanden los detalles de incidentes.
				const cerrados = [...page.querySelectorAll('details:not([open])')];
				cerrados.forEach(d => d.open = true);
				window.print();
				cerrados.forEach(d => d.open = false);
			});
		}
	};

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', init);
	}
	else {
		init();
	}
})();
