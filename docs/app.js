// --- CONFIGURACIÓN GLOBAL ---
const mapConfig = {
    center: [-33.4489, -70.6693], // Santiago, Chile
    zoom: 10
};

// --- INICIALIZACIÓN MAPA ---
const map = L.map('map', {
    zoomControl: false // Lo ponemos abajo a la derecha manualmente
}).setView(mapConfig.center, mapConfig.zoom);

// Controles de Zoom (Abajo Derecha)
L.control.zoom({ position: 'bottomright' }).addTo(map);

// Capas Base
const tiles = {
    "CartoDB Positron": L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CartoDB',
        maxNativeZoom: 19,
        maxZoom: 21
    }),
    "Esri Satélite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri',
        maxNativeZoom: 18,
        maxZoom: 21
    }),
    "Google Satélite": L.tileLayer('http://www.google.cn/maps/vt?lyrs=s@189&gl=cn&x={x}&y={y}&z={z}', {
        attribution: 'Google',
        maxZoom: 21
    }),
    "OpenStreetMap": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OSM',
        maxNativeZoom: 19,
        maxZoom: 21
    })
};

// Agregar por defecto
tiles["Google Satélite"].addTo(map);
L.control.layers(tiles, null, { position: 'bottomleft' }).addTo(map);


// --- CAPA DE DIBUJO (WORK LAYER) ---
// Aquí es donde el usuario dibuja. Es una FeatureGroup editable.
const workLayer = new L.FeatureGroup().addTo(map);


// --- CONFIGURACIÓN GEOMAN (HERRAMIENTAS DE DIBUJO) ---
map.pm.addControls({
    position: 'topleft',
    drawCircle: false,      // Simplificar 
    drawCircleMarker: false,
    drawText: false,
    drawRectangle: true,
    drawPolygon: true,
    drawPolyline: true,
    drawMarker: true,
    cutPolygon: true,       // Herramienta Pro: Cortar
    rotateMode: true,       // Herramienta Pro: Rotar
    editMode: true,
    dragMode: true,
    removalMode: true
});

map.pm.setGlobalOptions({
    layerGroup: workLayer, // Todo lo que se dibuje va a esta capa
    snappable: true,       // SNAPPING ACTIVADO!
    snapDistance: 20,
    allowSelfIntersection: false
});

// Eventos de Creación
map.on('pm:create', (e) => {
    const layer = e.layer;

    // Asignar propiedades por defecto si no tienen
    if (!layer.feature) {
        layer.feature = layer.feature || {};
        layer.feature.type = "Feature";
        layer.feature.properties = layer.feature.properties || { id: Date.now(), nombre: "Nuevo Elemento" };
    }

    // Agregar al grupo de trabajo
    workLayer.addLayer(layer);

    // Setup eventos clic para editar
    setupLayerEvents(layer);

    // Feedback visual
    updateLayerList();

    // AUTO-SELECT para editar atributos altiro
    selectFeature(layer);
});


// --- GESTIÓN DE CAPAS Y PROPIEDADES ---

// Referencias (Capas subidas que NO se editan, solo referencia)
const referenceLayers = {};

function setupLayerEvents(layer) {
    layer.on('click', (e) => {
        L.DomEvent.stopPropagation(e); // Evitar click en mapa
        selectFeature(e.target);
    });
}

// Variables estado selección
let selectedLayer = null;

function selectFeature(layer) {
    // Reset estilo anterior
    if (selectedLayer && selectedLayer !== layer) {
        // Restaurar estilo (simple check si es editable o ref)
        if (workLayer.hasLayer(selectedLayer)) {
            selectedLayer.setStyle({ color: '#3388ff', weight: 3 }); // Azul default Leaflet
        }
    }

    selectedLayer = layer;

    // Highlight
    if (layer.setStyle) {
        layer.setStyle({ color: '#f59e0b', weight: 5 }); // Naranja highlight
    }

    // Cargar propiedades en Panel Flotante
    renderInspector(layer);
    openInspector(); // Mostrar panel
}

function openInspector() {
    const p = document.getElementById('inspectorWidget');
    if (p) p.classList.remove('translate-x-[150%]');
}

function closeInspector() {
    const p = document.getElementById('inspectorWidget');
    if (p) p.classList.add('translate-x-[150%]');

    // Deseleccionar visualmente también? Opcional
    if (selectedLayer && workLayer.hasLayer(selectedLayer)) {
        selectedLayer.setStyle({ color: '#3388ff', weight: 3 });
        selectedLayer = null;
    }
}

function renderInspector(layer) {
    const props = layer.feature ? layer.feature.properties : {};
    const container = document.getElementById('inspectorPanel');
    const saveBtn = document.getElementById('saveAttributesBtn');

    let html = `<div class="grid gap-3">`;

    // Generar inputs dinámicos para cada propiedad
    for (const [key, val] of Object.entries(props)) {
        html += `
            <div>
                <label class="block text-xs font-bold text-gray-500 mb-1">${key}</label>
                <input type="text" data-key="${key}" value="${val || ''}" 
                       class="prop-input w-full bg-white border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500 transition">
            </div>
        `;
    }

    // Botón para agregar nueva propiedad
    html += `
        <div class="mt-2 pt-2 border-t border-gray-100">
            <button onclick="addNewField()" class="text-xs text-blue-600 hover:text-blue-800 font-medium">
                <i class="fa-solid fa-plus"></i> Agregar Campo
            </button>
        </div>
    </div>`;

    container.innerHTML = html;
    saveBtn.classList.remove('hidden');
}

function saveActiveAttributes() {
    if (!selectedLayer) return;

    const inputs = document.querySelectorAll('.prop-input');
    const newProps = {};

    inputs.forEach(input => {
        const key = input.dataset.key;
        newProps[key] = input.value;
    });

    // Actualizar feature
    if (!selectedLayer.feature) selectedLayer.feature = {};
    selectedLayer.feature.properties = newProps;

    // Feedback
    Swal.fire({
        toast: true, position: 'top-end', icon: 'success',
        title: 'Guardado', showConfirmButton: false, timer: 1500
    });

    // Sync tabla si está abierta
    if (typeof isTableOpen !== 'undefined' && isTableOpen) initAttributeTable();
}

function addNewField() {
    Swal.fire({
        title: 'Nuevo Campo',
        input: 'text',
        inputLabel: 'Nombre de la columna',
        showCancelButton: true
    }).then((result) => {
        if (result.isConfirmed && result.value) {
            if (!selectedLayer.feature.properties) selectedLayer.feature.properties = {};
            selectedLayer.feature.properties[result.value] = "";
            renderInspector(selectedLayer); // Re-render
        }
    });
}


// --- IMPORTAR ARCHIVOS ---

async function handleFileUpload(input) {
    const files = Array.from(input.files);
    if (!files.length) return;

    // 1. Agrupar archivos por nombre base para detectar sets de SHP (ej: "zona.shp" + "zona.dbf")
    const fileGroups = {};
    const standalones = [];

    for (const f of files) {
        const name = f.name;
        const lowerName = name.toLowerCase();

        // Detectar componentes de shapefile
        if (lowerName.endsWith('.shp') || lowerName.endsWith('.dbf') || lowerName.endsWith('.shx') || lowerName.endsWith('.prj') || lowerName.endsWith('.cpg')) {
            const baseName = name.substring(0, name.lastIndexOf('.'));
            if (!fileGroups[baseName]) fileGroups[baseName] = [];
            fileGroups[baseName].push(f);
        } else {
            standalones.push(f);
        }
    }

    const loadProgressBar = Swal.mixin({
        toast: true, position: 'top-end', showConfirmButton: false, timerProgressBar: true
    });

    try {
        // A. PROCESAR GRUPOS SHAPEFILE (Crear ZIP en memoria para shpjs)
        for (const [baseName, groupFiles] of Object.entries(fileGroups)) {
            // Verificar si tenemos al menos el .shp
            const hasShp = groupFiles.some(f => f.name.toLowerCase().endsWith('.shp'));
            if (!hasShp) {
                // Si son archivos sueltos sin .shp principal, tratarlos como error o ignorar
                console.warn(`Grupo ${baseName} incompleto (falta .shp).`);
                continue;
            }

            loadProgressBar.fire({ icon: 'info', title: `Procesando SHP: ${baseName}...` });

            // Crear ZIP en memoria
            const zip = new JSZip();
            for (const f of groupFiles) {
                zip.file(f.name, await f.arrayBuffer());
            }
            const zipBuffer = await zip.generateAsync({ type: 'arraybuffer' });

            // Cargar con shpjs como si fuera un zip normal
            const geojson = await shp(zipBuffer);
            addReferenceLayer(geojson, baseName);
        }

        // B. PROCESAR ARCHIVOS SUELTOS (KML, KMZ, GeoJSON, Zip)
        for (const file of standalones) {
            const name = file.name;
            const lowerName = name.toLowerCase();

            loadProgressBar.fire({ icon: 'info', title: `Leyendo ${name}...` });

            if (lowerName.endsWith('.zip')) {
                // SHP Zipeado
                const buffer = await file.arrayBuffer();
                const geojson = await shp(buffer);
                addReferenceLayer(geojson, name);

            } else if (lowerName.endsWith('.json') || lowerName.endsWith('.geojson')) {
                // GeoJSON
                const text = await file.text();
                const json = JSON.parse(text);
                addEditLayer(json);

            } else if (lowerName.endsWith('.kml')) {
                // KML
                const text = await file.text();
                const dom = new DOMParser().parseFromString(text, 'text/xml');
                const geojson = toGeoJSON.kml(dom);

                if (!geojson.features || geojson.features.length === 0) throw new Error("KML sin datos válidos.");
                addReferenceLayer(geojson, name);

            } else if (lowerName.endsWith('.kmz')) {
                // KMZ (Zip -> KML -> GeoJSON)
                const buffer = await file.arrayBuffer();
                const zip = await JSZip.loadAsync(buffer);

                // Buscar archivo .kml dentro del zip
                const kmlFile = Object.values(zip.files).find(f => f.name.toLowerCase().endsWith('.kml'));

                if (kmlFile) {
                    const text = await kmlFile.async('string');
                    const dom = new DOMParser().parseFromString(text, 'text/xml');
                    const geojson = toGeoJSON.kml(dom);
                    addReferenceLayer(geojson, name);
                } else {
                    throw new Error("No se encontró un archivo .kml dentro del KMZ.");
                }
            }
        }

        loadProgressBar.fire({ icon: 'success', title: 'Carga finalizada', timer: 2000 });

    } catch (e) {
        console.error(e);
        Swal.fire('Error', `Ocurrió un problema cargando archivos: ${e.message}`, 'error');
    }

    input.value = ''; // Reset
}


function addReferenceLayer(geojsonData, name) {
    const color = getRandomColor();
    const layer = L.geoJSON(geojsonData, {
        style: { color: color, weight: 2, fillOpacity: 0.2 },
        onEachFeature: (feature, l) => {
            // Bind tooltips
            if (feature.properties) {
                const keys = Object.keys(feature.properties);
                if (keys.length > 0) l.bindTooltip(String(feature.properties[keys[0]]));
            }
        }
    }).addTo(map);

    referenceLayers[name] = layer;
    updateLayerList();

    // Zoom to layer
    map.fitBounds(layer.getBounds());
}

function addEditLayer(geojsonData) {
    // Agregar a la capa de trabajo
    const layer = L.geoJSON(geojsonData, {
        onEachFeature: (f, l) => {
            setupLayerEvents(l);
            // IMPORTANTE: Agregar al FeatureGroup editor 'workLayer'
            // L.geoJSON crea un LayerGroup. Necesitamos extraer las capas individuales.
            // Pero Leaflet Geoman maneja LayerGroups? Si, pero mejor aplanar.
        }
    });

    layer.eachLayer(l => {
        workLayer.addLayer(l);
    });

    map.fitBounds(workLayer.getBounds());
    updateLayerList();
}


// --- UI SIDEBAR ---

function updateLayerList() {
    const list = document.getElementById('layerList');
    const count = document.getElementById('layerCount');
    list.innerHTML = '';

    // 1. Capa de Trabajo (Resumen)
    const workCounts = workLayer.getLayers().length;
    count.innerText = workCounts + Object.keys(referenceLayers).length;

    if (workCounts > 0) {
        list.innerHTML += `
        <div class="flex items-center justify-between p-2 bg-blue-50 rounded border border-blue-100">
            <div class="flex items-center gap-2">
                <i class="fa-solid fa-pen-ruler text-blue-600"></i>
                <span class="text-sm font-medium text-slate-700">Dibujo Actual (${workCounts})</span>
            </div>
            <button onclick="toggleLayerVisibility('work')" class="text-blue-500 hover:text-blue-700">
                <i class="fa-solid fa-eye"></i>
            </button>
        </div>`;
    }

    // 2. Capas de Referencia
    for (const [name, layer] of Object.entries(referenceLayers)) {
        list.innerHTML += `
        <div class="flex items-center justify-between p-2 bg-gray-50 rounded border border-gray-100">
            <div class="flex items-center gap-2 truncate">
                <i class="fa-solid fa-layer-group text-gray-400"></i>
                <span class="text-sm text-slate-600 truncate max-w-[150px]" title="${name}">${name}</span>
            </div>
            <div class="flex gap-2">
                <button onclick="zoomToRef('${name}')" class="text-gray-400 hover:text-gray-600" title="Zoom">
                    <i class="fa-solid fa-magnifying-glass-location"></i>
                </button>
                <button onclick="removeRefLayer('${name}')" class="text-red-300 hover:text-red-500" title="Eliminar">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        </div>`;
    }
}

function zoomToRef(name) {
    if (referenceLayers[name]) map.fitBounds(referenceLayers[name].getBounds());
}

function removeRefLayer(name) {
    if (referenceLayers[name]) {
        map.removeLayer(referenceLayers[name]);
        delete referenceLayers[name];
        updateLayerList();
    }
}

function toggleSidebar() {
    const sb = document.getElementById('sidebar');
    const openBtn = document.getElementById('openSidebarBtn');

    // Toggle class -translate-x-full to hide/show sidebar
    sb.classList.toggle('-translate-x-full');

    // If sidebar is hidden (has class -translate-x-full), show the Open Button
    if (sb.classList.contains('-translate-x-full')) {
        openBtn.classList.remove('hidden');
    } else {
        openBtn.classList.add('hidden');
    }
}


// --- EXPORTAR ---
function exportData() {
    if (workLayer.getLayers().length === 0) {
        Swal.fire('Vacío', 'No hay nada dibujado para guardar.', 'warning');
        return;
    }

    const geojson = workLayer.toGeoJSON();
    const str = JSON.stringify(geojson, null, 2);
    const blob = new Blob([str], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `dibujo_${Date.now()}.geojson`;
    a.click();
    URL.revokeObjectURL(url);

    Swal.fire('Exportado', 'Archivo GeoJSON descargado.', 'success');
}


// Utilidades
function getRandomColor() {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
}

// Clic en mapa (fuera de feature) limpia selección
map.on('click', () => {
    if (selectedLayer) {
        // Restaurar estilo
        if (workLayer.hasLayer(selectedLayer)) {
            selectedLayer.setStyle({ color: '#3388ff', weight: 3 });
        }
        selectedLayer = null;
        // Cerrar panel inspector
        closeInspector();
    }
});
