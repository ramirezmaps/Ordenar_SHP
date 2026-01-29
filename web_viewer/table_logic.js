
// --- TABLA DE ATRIBUTOS (TABULATOR) ---
let table = null;

function initAttributeTable() {
    // 1. Obtener datos de workLayer
    const data = [];
    // Definir llaves que NO queremos ver en la tabla
    const hiddenKeys = new Set(['_leaflet_id', 'stroke', 'stroke-width', 'stroke-opacity', 'fill', 'fill-opacity', 'marker-color', 'marker-symbol']);
    const allKeys = new Set(['id']);

    // Función helper para buscar capa robustamente (localizada)
    const findLayer = (id) => {
        // Primero intento directo (rápido)
        let l = workLayer.getLayer(id);
        if (l) return l;
        // Si falla, búsqueda manual (maneja mismatch string/number)
        return workLayer.getLayers().find(layer => layer._leaflet_id == id);
    };

    workLayer.eachLayer(layer => {
        if (layer.feature && layer.feature.properties) {
            const rowData = { ...layer.feature.properties };
            rowData._leaflet_id = layer._leaflet_id;
            data.push(rowData);

            // Recolectar solo llaves NO ocultas
            Object.keys(layer.feature.properties).forEach(k => {
                if (!hiddenKeys.has(k)) allKeys.add(k);
            });
        }
    });

    // 2. Definir Columnas
    const columns = Array.from(allKeys).filter(k => !hiddenKeys.has(k)).map(key => ({
        title: key.charAt(0).toUpperCase() + key.slice(1),
        field: key,
        editor: "input",
        headerFilter: "input"
    }));

    // [NUEVO] Columna ZOOM (Inicio)
    columns.unshift({
        title: "<i class='fa-solid fa-magnifying-glass'></i>",
        headerSort: false,
        width: 50,
        align: "center",
        formatter: function () { return "<i class='fa-solid fa-crosshairs text-blue-500 cursor-pointer text-lg'></i>"; },
        cellClick: function (e, cell) {
            const id = cell.getRow().getData()._leaflet_id;
            const layer = findLayer(id);
            if (layer) {
                // Seleccionar
                if (typeof selectFeature === 'function') selectFeature(layer);

                // Zoom "Profesional" (Centrado visualmente)
                // 1. Unificamos bounds (Puntos -> Bounds)
                const bounds = layer.getBounds ? layer.getBounds() : L.latLngBounds([layer.getLatLng()]);

                // 2. Calculamos Padding dinámico
                // Si la tabla está abierta (sabemos que sí porque hicimos clic en ella), 
                // restamos el tercio inferior de la pantalla (h-1/3) + un margen extra.
                const tableHeight = window.innerHeight * 0.35; // ~33% + margen

                map.flyToBounds(bounds, {
                    paddingTopLeft: [80, 80],      // Arriba/Izquierda: Buen aire
                    paddingBottomRight: [80, tableHeight + 50], // Abajo/Derecha: Aire + Tabla
                    maxZoom: 18,
                    duration: 0.8,
                    easeLinearity: 0.5
                });
            } else {
                console.warn("Capa no encontrada con ID:", id);
            }
        }
    });

    // Columna BORRAR (Final)
    columns.push({
        title: "<i class='fa-regular fa-trash-can'></i>",
        headerSort: false,
        width: 50,
        align: "center",
        formatter: "buttonCross", // O icono custom
        cellClick: function (e, cell) {
            const id = cell.getRow().getData()._leaflet_id;
            const layer = findLayer(id);
            if (layer) {
                Swal.fire({
                    title: '¿Borrar elemento?', icon: 'warning', showCancelButton: true, confirmButtonColor: '#d33', confirmButtonText: 'Sí, borrar'
                }).then((r) => {
                    if (r.isConfirmed) {
                        workLayer.removeLayer(layer);
                        cell.getRow().delete();
                        if (selectedLayer === layer) { closeInspector(); selectedLayer = null; }
                    }
                });
            }
        }
    });

    // 3. Inicializar Tabulator
    table = new Tabulator("#attributeTable", {
        data: data,
        layout: "fitColumns",
        columns: columns,
        height: "100%",
        placeholder: "No hay elementos dibujados.",

        // --- EDICIÓN EN TABLA ---
        cellEdited: function (cell) {
            const rowData = cell.getRow().getData();
            const id = rowData._leaflet_id;
            const layer = findLayer(id);

            if (layer) {
                // Preservar estilos existentes al actualizar propiedades
                const oldProps = layer.feature.properties;
                const newProps = { ...oldProps, ...rowData };

                delete newProps._leaflet_id;
                layer.feature.properties = newProps;

                // Si cambió algo de estilo visual, re-aplicar (aunque la tabla no muestra estilos, por seguridad)
                if (typeof applyStyle !== 'undefined') applyStyle(layer);

                if (typeof selectedLayer !== 'undefined' && selectedLayer === layer) {
                    renderInspector(layer);
                }
            }
        },

        // --- CLIC EN FILA (ZOOM OPTIMIZADO) ---
        rowClick: function (e, row) {
            /* 
               Ya no necesitamos zoom aquí porque tenemos el botón explícito.
               Si el usuario quiere editar, hace click en la celda.
               Si quiere ver, hace click en la lupa.
            */
        }
    });
}

// Sincronizar Mapa -> Tabla cuando se crea/borra algo
map.on('pm:create', () => { if (isTableOpen) initAttributeTable(); });
map.on('pm:remove', () => { if (isTableOpen) initAttributeTable(); });


// UI toggle
let isTableOpen = false;
function toggleBottomPanel() {
    const panel = document.getElementById('bottomPanel');
    isTableOpen = !isTableOpen;

    if (isTableOpen) {
        panel.classList.remove('translate-y-full');
        initAttributeTable(); // Cargar datos frescos
    } else {
        panel.classList.add('translate-y-full');
    }
}
