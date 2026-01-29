
// --- TABLA DE ATRIBUTOS (TABULATOR) ---
let table = null;

function initAttributeTable() {
    // Si ya existe, destruirla para recrear con nuevas columnas si es necesario
    /* if (table) {
        table.destroy();
    } */

    // 1. Obtener datos de workLayer
    const data = [];
    const allKeys = new Set(['id']); // Garantizar columnas base

    workLayer.eachLayer(layer => {
        if (layer.feature && layer.feature.properties) {
            const props = layer.feature.properties;
            // Agregar ID interno de leaflet para referencia inversa
            props._leaflet_id = layer._leaflet_id;
            data.push(props);

            // Recolectar todas las llaves posibles
            Object.keys(props).forEach(k => allKeys.add(k));
        }
    });

    // 2. Definir Columnas
    const columns = Array.from(allKeys).filter(k => k !== '_leaflet_id').map(key => ({
        title: key.charAt(0).toUpperCase() + key.slice(1),
        field: key,
        editor: "input",
        headerFilter: "input"
    }));

    // Agregar columna de borrado
    columns.push({
        formatter: "buttonCross", width: 40, align: "center", cellClick: function (e, cell) {
            const id = cell.getRow().getData()._leaflet_id;
            const layer = workLayer.getLayer(id);
            if (layer) {
                workLayer.removeLayer(layer);
                cell.getRow().delete();
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
        cellEdited: function (cell) {
            // Sincronizar cambios de Tabla -> Mapa
            const rowData = cell.getRow().getData();
            const id = rowData._leaflet_id;
            const layer = workLayer.getLayer(id);

            if (layer) {
                layer.feature.properties = { ...rowData }; // Copiar
                delete layer.feature.properties._leaflet_id; // Limpiar interno
            }
        },
        rowClick: function (e, row) {
            // Zoom al elemento al hacer clic en la fila
            const id = row.getData()._leaflet_id;
            const layer = workLayer.getLayer(id);
            if (layer) {
                selectFeature(layer);
                if (layer.getBounds) map.fitBounds(layer.getBounds(), { maxZoom: 16 });
                else if (layer.getLatLng) map.setView(layer.getLatLng(), 16);
            }
        }
    });
}

// Sincronizar Mapa -> Tabla cuando se crea/borra algo
map.on('pm:create', () => { if (isTableOpen) initAttributeTable(); });
map.on('pm:remove', () => { if (isTableOpen) initAttributeTable(); });
// Falta capturar cambios de propiedades desde Sidebar -> Tabla
// Se agrega hook en saveActiveAttributes (ver abajo)


// UI toggle
let isTableOpen = false;
function toggleBottomPanel() {
    const panel = document.getElementById('bottomPanel');
    isTableOpen = !isTableOpen;

    if (isTableOpen) {
        panel.classList.remove('translate-y-full');
        initAttributeTable(); // Cargar datos
    } else {
        panel.classList.add('translate-y-full');
    }
}
