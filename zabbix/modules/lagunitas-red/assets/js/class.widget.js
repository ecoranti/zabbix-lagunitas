/*
 * Widget "Red Las Lagunitas": filtros, búsqueda y modal de detalle por equipo.
 * Al seleccionar un equipo también se difunde su hostid (_hostid) a los widgets
 * del dashboard que lo tengan configurado como origen ("Override host").
 */

window.LagunitasModal = window.LagunitasModal || (() => {
	let overlay = null;
	let dialog = null;
	let ultimo_foco = null;

	const cerrar = () => {
		if (overlay === null) {
			return;
		}
		overlay.remove();
		overlay = null;
		document.removeEventListener('keydown', onKey);
		if (ultimo_foco) {
			ultimo_foco.focus();
		}
	};

	const onKey = (e) => {
		if (e.key === 'Escape') {
			cerrar();
		}
	};

	const cambiarTab = (tab) => {
		dialog.querySelectorAll('[data-lg-tab]').forEach(b => b.classList.toggle('is-active', b.dataset.lgTab === tab));
		dialog.querySelectorAll('[data-lg-pane]').forEach(p => p.classList.toggle('is-active', p.dataset.lgPane === tab));
	};

	const cambiarRango = (desde) => {
		dialog.querySelectorAll('[data-lg-range]').forEach(b => b.classList.toggle('is-active', b.dataset.lgRange === desde));
		dialog.querySelectorAll('img[data-lg-src]').forEach(img => {
			img.src = `${img.dataset.lgSrc}&from=${encodeURIComponent(desde)}&to=now&_=${Date.now()}`;
		});
	};

	const onClick = (e) => {
		if (e.target === overlay || e.target.closest('[data-lg-close]')) {
			cerrar();
			return;
		}
		const tab = e.target.closest('[data-lg-tab]');
		if (tab) {
			cambiarTab(tab.dataset.lgTab);
			return;
		}
		const rango = e.target.closest('[data-lg-range]');
		if (rango) {
			cambiarRango(rango.dataset.lgRange);
			return;
		}
		const otro = e.target.closest('[data-lg-host]');
		if (otro) {
			e.preventDefault();
			abrir(otro.dataset.lgHost);
		}
	};

	const abrir = (hostid) => {
		if (overlay === null) {
			ultimo_foco = document.activeElement;
			overlay = document.createElement('div');
			overlay.className = 'lg-modal-overlay';
			overlay.innerHTML = '<div class="lg-modal" role="dialog" aria-modal="true" aria-label="Detalle del equipo"></div>';
			dialog = overlay.firstElementChild;
			overlay.addEventListener('click', onClick);
			document.addEventListener('keydown', onKey);
			document.body.appendChild(overlay);
		}
		dialog.innerHTML = '<div class="lg-loading">Cargando detalle…</div>';

		fetch(`zabbix.php?action=lagunitas.equipo&hostid=${encodeURIComponent(hostid)}`, {credentials: 'same-origin'})
			.then(r => {
				if (!r.ok) {
					throw new Error(`HTTP ${r.status}`);
				}
				return r.json();
			})
			.then(json => {
				if (json.body === undefined) {
					throw new Error(json.error?.title || 'respuesta inesperada');
				}
				if (dialog !== null) {
					dialog.innerHTML = json.body;
					const cerrar_btn = dialog.querySelector('[data-lg-close]');
					if (cerrar_btn) {
						cerrar_btn.focus({preventScroll: true});
						dialog.scrollLeft = 0;
					}
				}
			})
			.catch(err => {
				if (dialog !== null) {
					dialog.innerHTML = `<div class="lg-empty">No se pudo cargar el detalle (${err.message}).`
						+ ' <button type="button" class="lg-btn" data-lg-close>Cerrar</button></div>';
				}
			});
	};

	return {abrir, cerrar};
})();

class CWidgetLagunitasRed extends CWidget {

	#filtro = 'todos';
	#busqueda = '';

	setContents(response) {
		super.setContents(response);

		const root = this._contents.querySelector('.lg-red');

		if (root === null) {
			return;
		}

		root.addEventListener('click', e => this.#onClick(e, root));
		root.addEventListener('keydown', e => {
			const row = e.target.closest('.lg-row');
			if (row !== null && (e.key === 'Enter' || e.key === ' ')) {
				e.preventDefault();
				this.#seleccionar(row);
			}
		});

		const q = root.querySelector('.lg-q');
		if (q !== null) {
			q.value = this.#busqueda;
			q.addEventListener('input', () => {
				this.#busqueda = q.value.trim().toLowerCase();
				this.#aplicar(root);
			});
		}

		this.#aplicar(root);
	}

	#onClick(e, root) {
		const filtro = e.target.closest('[data-lg-filter]');

		if (filtro !== null) {
			this.#filtro = filtro.dataset.lgFilter;
			this.#aplicar(root);
			return;
		}

		const row = e.target.closest('.lg-row');

		if (row !== null && !this._is_edit_mode) {
			this.#seleccionar(row);
		}
	}

	#seleccionar(row) {
		const hostid = row.dataset.hostid;

		this.broadcast({[CWidgetsData.DATA_TYPE_HOST_ID]: [hostid]});
		window.LagunitasModal.abrir(hostid);
	}

	#aplicar(root) {
		const filtro = this.#filtro;
		const q = this.#busqueda;
		let visibles = 0;

		root.querySelectorAll('[data-lg-filter]').forEach(el => {
			el.classList.toggle('is-active', el.dataset.lgFilter === filtro);
		});

		root.querySelectorAll('.lg-sec').forEach(sec => {
			let en_seccion = 0;

			sec.querySelectorAll('.lg-row').forEach(row => {
				let ok = true;

				if (filtro.startsWith('rol:')) {
					ok = row.dataset.rol === filtro.slice(4);
				}
				else if (filtro === 'nomon') {
					ok = row.dataset.estado === 'nomon' || row.dataset.estado === 'mantenimiento';
				}
				else if (filtro !== 'todos') {
					ok = row.dataset.estado === filtro;
				}

				if (ok && q !== '') {
					ok = row.dataset.q.includes(q);
				}

				row.hidden = !ok;
				en_seccion += ok ? 1 : 0;
			});

			sec.hidden = en_seccion === 0;
			visibles += en_seccion;
		});

		const contador = root.querySelector('.lg-count');
		if (contador !== null) {
			contador.textContent = `${visibles} ${visibles === 1 ? 'equipo' : 'equipos'}`;
		}

		const vacio = root.querySelector('.lg-none');
		if (vacio !== null) {
			vacio.hidden = visibles !== 0;
		}
	}
}
