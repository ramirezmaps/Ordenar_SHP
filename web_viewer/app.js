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

// --- CONTROLES "PRO" (GIS STANDARD) ---

// 1. Escala (Métrica / Imperial)
L.control.scale({ imperial: false, maxWidth: 200, position: 'bottomright' }).addTo(map);

// 2. Coordenadas del Mouse (Custom Control)
const CoordControl = L.Control.extend({
    options: { position: 'bottomleft' },
    onAdd: function (map) {
        const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-custom');
        div.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
        div.style.padding = '4px 10px';
        div.style.borderRadius = '4px';
        div.style.boxShadow = '0 1px 4px rgba(0,0,0,0.3)';
        div.style.fontSize = '11px';
        div.style.fontFamily = 'monospace';
        div.style.color = '#334155';
        div.style.marginBottom = '25px'; // Separar del borde
        div.style.marginLeft = '10px';
        div.id = 'mouse-coords';
        div.innerHTML = 'Lat: - | Lng: -';
        return div;
    }
});
map.addControl(new CoordControl());

// Evento movimiento mouse
map.on('mousemove', function (e) {
    const el = document.getElementById('mouse-coords');
    if (el) {
        el.innerHTML = `Lat: <b>${e.latlng.lat.toFixed(5)}</b> | Lng: <b>${e.latlng.lng.toFixed(5)}</b> | Zoom: <b>${map.getZoom()}</b>`;
    }
});


// --- CAPA DE DIBUJO (WORK LAYER) ---
// Aquí es donde el usuario dibuja. Es una FeatureGroup editable.
const workLayer = new L.FeatureGroup().addTo(map);


// --- CONFIGURACIÓN GEOMAN (HERRAMIENTAS DE DIBUJO) ---
map.pm.addControls({
    position: 'topleft',
    drawCircle: false,
    drawCircleMarker: false,
    drawText: false,
    drawRectangle: true,
    drawPolygon: true,
    drawPolyline: true,
    drawMarker: true,
    cutPolygon: true,
    rotateMode: true,
    editMode: true,
    dragMode: true,
    removalMode: true
});

map.pm.setGlobalOptions({
    layerGroup: workLayer,
    snappable: true,
    snapDistance: 20,
    allowSelfIntersection: false,
    continueDrawing: true,
    // [NUEVO] Mediciones en vivo (GIS Pro)
    tooltips: true,
    measurements: { measurement: true }
});

// 3. Botón Home (Reset Vista)
const HomeControl = L.Control.Zoom.extend({
    options: { position: 'bottomright' },
    onAdd: function (map) {
        const btn = L.DomUtil.create('button', 'leaflet-bar leaflet-control leaflet-control-custom');
        btn.innerHTML = '<i class="fa-solid fa-house"></i>';
        btn.style.width = '30px';
        btn.style.height = '30px';
        btn.style.backgroundColor = 'white';
        btn.style.border = 'none';
        btn.style.cursor = 'pointer';
        btn.style.borderRadius = '4px';
        btn.style.boxShadow = '0 1px 4px rgba(0,0,0,0.3)';
        btn.style.color = '#333';
        btn.style.fontSize = '14px';
        btn.title = 'Vista Inicial';

        btn.onclick = () => {
            map.setView(mapConfig.center, mapConfig.zoom);
        };
        return btn;
    }
});
map.addControl(new HomeControl());


// --- CAPA DE DIBUJO (WORK LAYER) ---
// --- CONFIGURACIÓN GEOMAN (HERRAMIENTAS DE DIBUJO) ---
map.pm.addControls({
    position: 'topleft',
    drawCircle: false,
    drawCircleMarker: false,
    drawText: false,
    drawRectangle: true,
    drawPolygon: true,
    drawPolyline: true,
    drawMarker: true,
    cutPolygon: true,
    rotateMode: true,
    editMode: true,
    dragMode: true,
    removalMode: true
});

map.pm.setGlobalOptions({
    layerGroup: workLayer,
    snappable: true,
    snapDistance: 20,
    allowSelfIntersection: false,
    continueDrawing: true,
    tooltips: true,
    measurements: { measurement: true }
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

    // Auto-Calcular Geometría Básica (Si es posible)
    if (typeof updateGeometryProperties === 'function') updateGeometryProperties(layer);

    // Agregar al grupo de trabajo
    workLayer.addLayer(layer);

    // Setup eventos clic y contextmenu
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
        L.DomEvent.stopPropagation(e);
        selectFeature(e.target);
    });

    // Menu Contextual (Click Derecho)
    layer.on('contextmenu', (e) => {
        L.DomEvent.stopPropagation(e);

        Swal.fire({
            title: 'Opciones',
            html: `
                <button onclick="zoomToFeature('${layer._leaflet_id}')" class="swal2-confirm swal2-styled mb-2" style="background:#3b82f6; display:block; width:100%;">Zoom <i class="fa-solid fa-magnifying-glass"></i></button>
                <button onclick="selectFeatureInTable('${layer._leaflet_id}')" class="swal2-confirm swal2-styled mb-2" style="background:#10b981; display:block; width:100%;">Editar <i class="fa-solid fa-pen"></i></button>
                <button onclick="deleteFeature('${layer._leaflet_id}')" class="swal2-deny swal2-styled" style="background:#ef4444; display:block; width:100%;">Eliminar <i class="fa-solid fa-trash"></i></button>
            `,
            showConfirmButton: false,
            showCloseButton: true,
            width: 250,
            padding: '1em',
            target: document.getElementById('map') // Render dentro del mapa
        });
    });

    // Tooltip al pasar el mouse (sticky: sigue al puntero)
    if (layer.feature && layer.feature.properties) {
        layer.bindTooltip(getTooltipContent(layer.feature.properties), {
            sticky: true,
            direction: 'top',
            className: 'bg-white px-2 py-1 border border-gray-200 shadow-lg rounded text-xs font-sans'
        });
    }
}

// Helpers globales para el Swal (necesitan ser globales para el onclick string)
window.zoomToFeature = (id) => {
    const l = workLayer.getLayer(id);
    if (l) map.flyToBounds(l.getBounds ? l.getBounds() : l.getLatLng().toBounds(100), { maxZoom: 18 });
    Swal.close();
};

window.deleteFeature = (id) => {
    const l = workLayer.getLayer(id);
    if (l) {
        workLayer.removeLayer(l);
        updateLayerList();
        if (selectedLayer === l) closeInspector();
    }
    Swal.close();
};
window.selectFeatureInTable = (id) => {
    const l = workLayer.getLayer(id);
    if (l) {
        selectFeature(l);
        if (!isTableOpen) toggleBottomPanel();
    }
    Swal.close();
};

function updateGeometryProperties(layer) {
    // Calculo simple de area/longitud si no existe
    // Nota: Esto es aproximado sin Turf.js, pero sirve de referencia UX
    if (layer instanceof L.Polygon) {
        // Calcular Area aprox
        // Dejamos pendiente implementación robusta de área
    }
}

function getTooltipContent(props) {
    if (!props) return "Sin datos";

    // Filtramos llaves de estilo y sistema
    const ignore = ['stroke', 'stroke-width', 'stroke-opacity', 'fill', 'fill-opacity', 'marker-color', 'marker-symbol', '_leaflet_id', 'id'];

    let html = '<div class="text-left">';
    let hasContent = false;

    for (const [key, val] of Object.entries(props)) {
        if (ignore.includes(key)) continue;
        html += `<div class="mb-0.5"><span class="font-bold text-slate-600">${key}:</span> <span class="text-slate-800">${val}</span></div>`;
        hasContent = true;
    }

    if (!hasContent) return '<span class="italic text-gray-400">Sin atributos</span>';

    html += '</div>';
    return html;
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

    // Deseleccionar visualmente
    if (selectedLayer && workLayer.hasLayer(selectedLayer)) {
        if (typeof applyStyle === 'function') applyStyle(selectedLayer); // Restaurar estilo real
        else selectedLayer.setStyle({ color: '#3388ff', weight: 3 });
        selectedLayer = null;
    }
}


function applyStyle(layer) {
    if (!layer.feature || !layer.feature.properties) return;
    const p = layer.feature.properties;

    // Estilos por defecto (SimpleStyle Spec)
    const style = {
        color: p.stroke || '#3388ff',
        weight: typeof p['stroke-width'] === 'number' ? p['stroke-width'] : 3,
        opacity: typeof p['stroke-opacity'] === 'number' ? p['stroke-opacity'] : 1,
        fillColor: p.fill || '#3388ff',
        fillOpacity: typeof p['fill-opacity'] === 'number' ? p['fill-opacity'] : 0.2,
        dashArray: null
    };

    if (layer instanceof L.Marker) {
        // Lógica para Marcadores (Iconos)
        const markerColor = p['marker-color'] || '#3388ff';
        const iconName = p['marker-symbol'] || 'location-dot';

        if (p['marker-color'] || p['marker-symbol']) {
            const iconHtml = `<div style="color: ${markerColor}; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); font-size: 34px; text-align: center;">
                            <i class="fa-solid fa-${iconName}"></i>
                          </div>`;

            layer.setIcon(L.divIcon({
                html: iconHtml,
                className: 'custom-fa-marker',
                iconSize: [42, 42],
                iconAnchor: [21, 21]
            }));
        }
    } else {
        // Polígonos y Líneas
        layer.setStyle(style);
    }
}

function renderInspector(layer) {
    const props = layer.feature ? layer.feature.properties : {};
    const container = document.getElementById('inspectorPanel');
    const saveBtn = document.getElementById('saveAttributesBtn');

    // --- SECCIÓN 1: DATOS (ATRIBUTOS) ---
    let html = `<div class="mb-4">
        <h4 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2 border-b pb-1">Datos</h4>
        <div class="grid gap-3">`;

    // Filtrar propiedades de estilo para no mostrarlas en la lista de datos "raw"
    const styleKeys = ['stroke', 'stroke-width', 'stroke-opacity', 'fill', 'fill-opacity', 'marker-color', 'marker-symbol', '_leaflet_id'];

    for (const [key, val] of Object.entries(props)) {
        if (styleKeys.includes(key)) continue; // Ocultar estilos de la edición de datos

        html += `
            <div>
                <label class="block text-xs font-bold text-gray-500 mb-1">${key}</label>
                <input type="text" data-key="${key}" value="${val || ''}" 
                       class="prop-input w-full bg-white border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500 transition">
            </div>
        `;
    }
    html += `
        <button onclick="addNewField()" class="mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium">
            <i class="fa-solid fa-plus"></i> Agregar Campo
        </button>
    </div></div>`;


    // --- SECCIÓN 2: ESTILO VISUAL ---
    html += `<div class="mb-2 pt-2 border-t border-gray-100">
        <h4 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Estilo Visual</h4>
        <div class="grid grid-cols-2 gap-3 text-sm">`;

    if (layer instanceof L.Marker) {
        // PUNTOS
        html += `
            <div>
                <label class="block text-xs text-gray-500 mb-1">Color</label>
                <input type="color" data-style="marker-color" value="${props['marker-color'] || '#3388ff'}" class="style-input w-full h-8 rounded cursor-pointer">
            </div>
            <div>
                <label class="block text-xs text-gray-500 mb-1">Icono</label>
                <select data-style="marker-symbol" class="style-input w-full bg-white border border-gray-200 rounded px-2 py-1 h-8 focus:outline-none text-xs">
                    <option value="location-dot" ${props['marker-symbol'] === 'location-dot' ? 'selected' : ''}>📍 Pin</option>
                    <option value="circle" ${props['marker-symbol'] === 'circle' ? 'selected' : ''}>⚫ Círculo</option>
                    <option value="square" ${props['marker-symbol'] === 'square' ? 'selected' : ''}>⬛ Cuadrado</option>
                    <option value="star" ${props['marker-symbol'] === 'star' ? 'selected' : ''}>⭐ Estrella</option>
                    <option value="house" ${props['marker-symbol'] === 'house' ? 'selected' : ''}>🏠 Casa</option>
                    <option value="tree" ${props['marker-symbol'] === 'tree' ? 'selected' : ''}>🌲 Árbol</option>
                    <option value="car" ${props['marker-symbol'] === 'car' ? 'selected' : ''}>🚗 Auto</option>
                    <option value="play" ${props['marker-symbol'] === 'play' ? 'selected' : ''}>▶️ Play</option>
                </select>
            </div>
        `;
    } else {
        // LÍNEAS y POLÍGONOS
        html += `
            <div>
                <label class="block text-xs text-gray-500 mb-1">Borde</label>
                <input type="color" data-style="stroke" value="${props.stroke || '#3388ff'}" class="style-input w-full h-8 rounded cursor-pointer">
            </div>
            <div>
                <label class="block text-xs text-gray-500 mb-1">Relleno</label>
                <input type="color" data-style="fill" value="${props.fill || '#3388ff'}" class="style-input w-full h-8 rounded cursor-pointer">
            </div>
            <div class="col-span-2">
                <label class="block text-xs text-gray-500 mb-1">Transparencia Relleno</label>
                <input type="range" data-style="fill-opacity" min="0" max="1" step="0.1" value="${props['fill-opacity'] !== undefined ? props['fill-opacity'] : 0.2}" class="style-input w-full accent-blue-600">
            </div>
            <div class="col-span-2">
                <label class="block text-xs text-gray-500 mb-1">Grosor Línea</label>
                <input type="range" data-style="stroke-width" min="1" max="10" step="1" value="${props['stroke-width'] || 3}" class="style-input w-full accent-blue-600">
            </div>
        `;
    }
    html += `</div></div>`;

    container.innerHTML = html;
    saveBtn.classList.remove('hidden');

    document.querySelectorAll('.style-input').forEach(input => {
        input.addEventListener('input', () => saveActiveAttributes(true));
    });
}

function saveActiveAttributes(silent = false) {
    if (!selectedLayer) return;

    const newProps = { ...selectedLayer.feature.properties };

    // 1. Guardar Datos
    document.querySelectorAll('.prop-input').forEach(input => {
        newProps[input.dataset.key] = input.value;
    });

    // 2. Guardar Estilos
    document.querySelectorAll('.style-input').forEach(input => {
        let val = input.value;
        if (input.type === 'range') val = parseFloat(val);
        newProps[input.dataset.style] = val;
    });

    selectedLayer.feature.properties = newProps;
    applyStyle(selectedLayer); // Visual

    // Actualizar Tooltip con los nuevos datos
    if (selectedLayer.setTooltipContent) {
        selectedLayer.setTooltipContent(getTooltipContent(newProps));
    }

    if (!silent) {
        Swal.fire({
            toast: true, position: 'top-end', icon: 'success',
            title: 'Guardado', showConfirmButton: false, timer: 1500
        });
    }

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
            // Bind tooltips (Smart: try to find 'name' or 'etiqueta' first)
            if (feature.properties) {
                const props = feature.properties;
                const label = props.name || props.nombre || props.etiqueta || Object.values(props)[0];
                if (label) l.bindTooltip(String(label), { sticky: true });
            }
        }
    }).addTo(map);

    // Guardar referencia extra para color
    layer._customColor = color;

    referenceLayers[name] = layer;
    updateLayerList();

    map.fitBounds(layer.getBounds());
}

function updateLayerColor(name, newColor) {
    const layer = referenceLayers[name];
    if (layer) {
        layer.setStyle({ color: newColor, fillColor: newColor });
        layer._customColor = newColor;
    }
}

function searchInLayer(name, query) {
    const layer = referenceLayers[name];
    if (!layer || !query) return;

    const normalize = (str) => String(str).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const q = normalize(query);

    let found = null;

    layer.eachLayer(l => {
        if (found) return; // Solo buscar el primero por ahora o resaltar todos
        if (l.feature && l.feature.properties) {
            // Buscar en todos los valores
            const match = Object.values(l.feature.properties).some(val => normalize(val).includes(q));
            if (match) found = l;
        }
    });

    if (found) {
        if (found.getBounds) map.flyToBounds(found.getBounds(), { maxZoom: 18 });
        else map.flyTo(found.getLatLng(), 18);

        found.openTooltip(); // Mostrar etiqueta

        // Highlight temporal
        const originalStyle = { color: layer._customColor, weight: 2 };
        found.setStyle({ color: '#facc15', weight: 5 }); // Amarillo
        setTimeout(() => found.setStyle(originalStyle), 3000);
    } else {
        Swal.fire({ toast: true, position: 'top-end', icon: 'info', title: 'No encontrado', timer: 2000, showConfirmButton: false });
    }
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
        <div class="p-2 bg-gray-50 rounded border border-gray-100 flex flex-col gap-2 relative">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 truncate">
                    <input type="color" value="${layer._customColor || '#3388ff'}" 
                           class="w-4 h-4 rounded cursor-pointer border-none p-0 overflow-hidden" 
                           onchange="updateLayerColor('${name}', this.value)" title="Cambiar Color">
                    <span class="text-sm text-slate-700 font-medium truncate max-w-[140px]" title="${name}">${name}</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="zoomToRef('${name}')" class="text-gray-400 hover:text-blue-500" title="Zoom Global">
                        <i class="fa-solid fa-earth-americas"></i>
                    </button>
                    <button onclick="removeRefLayer('${name}')" class="text-gray-300 hover:text-red-500" title="Eliminar">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            
            <!-- Buscador interno con Autocompletado -->
            <div class="relative">
                 <input type="text" placeholder="Buscar..." 
                        class="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400"
                        oninput="updateSearchSuggestions('${name}', this.value, this)">
                 
                 <!-- Lista de Sugerencias -->
                 <ul id="suggestions-${name.replace(/\s+/g, '-')}" 
                     class="hidden absolute left-0 right-0 top-full mt-1 bg-white border border-gray-100 shadow-xl rounded z-50 max-h-40 overflow-y-auto text-xs">
                 </ul>
            </div>
        </div>`;
    }
}

// Lógica Autocompletado
function updateSearchSuggestions(name, query, input) {
    const listId = `suggestions-${name.replace(/\s+/g, '-')}`;
    const listEl = document.getElementById(listId);
    if (!listEl) return;

    if (!query || query.length < 2) {
        listEl.classList.add('hidden');
        listEl.innerHTML = '';
        return;
    }

    const layer = referenceLayers[name];
    if (!layer) return;

    const normalize = (str) => String(str).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const q = normalize(query);
    const matches = [];

    layer.eachLayer(l => {
        if (matches.length > 10) return;
        if (l.feature && l.feature.properties) {
            const props = l.feature.properties;

            // 1. Identificar nombre principal para mostrar
            const primaryName = props.name || props.nombre || props.id || "Elemento sin nombre";

            // 2. Buscar coincidencias en TODOS los valores
            let foundMatch = false;
            let matchContext = "";

            for (const [key, val] of Object.entries(props)) {
                if (val && normalize(val).includes(q)) {
                    foundMatch = true;
                    // Si el match NO es el nombre principal, lo guardamos para contexto
                    if (val !== primaryName) {
                        matchContext = `${key}: ${val}`;
                    }
                    break;
                }
            }

            if (foundMatch) {
                matches.push({ label: primaryName, context: matchContext, layer: l });
            }
        }
    });

    if (matches.length > 0) {
        let html = '';
        matches.forEach((m, index) => {
            // Guardamos referencia al layerId para recuperarlo despues (usando _leaflet_id)
            html += `<li onclick="zoomToSuggestion('${name}', ${m.layer._leaflet_id})" 
                         class="px-2 py-1.5 hover:bg-blue-50 cursor-pointer text-slate-600 border-b border-gray-50 last:border-0">
                        <div class="font-medium truncate"><i class="fa-solid fa-location-dot text-blue-300 mr-1"></i> ${m.label}</div>
                        ${m.context ? `<div class="text-[10px] text-gray-400 pl-4 truncate">${m.context}</div>` : ''}
                     </li>`;
        });
        listEl.innerHTML = html;
        listEl.classList.remove('hidden');
    } else {
        listEl.classList.add('hidden');
    }
}

function zoomToSuggestion(layerName, layerId) {
    const layerGroup = referenceLayers[layerName];
    if (!layerGroup) return;

    const targetLayer = layerGroup.getLayer(layerId);
    if (targetLayer) {
        // Zoom
        if (targetLayer.getBounds) map.flyToBounds(targetLayer.getBounds(), { maxZoom: 18 });
        else map.flyTo(targetLayer.getLatLng(), 18);

        // Highlight
        targetLayer.openTooltip();
        const color = layerGroup._customColor;
        const originalStyle = { color: color, weight: 2 };
        if (targetLayer.setStyle) {
            targetLayer.setStyle({ color: '#facc15', weight: 5 });
            setTimeout(() => targetLayer.setStyle(originalStyle), 3000);
        }

        // Limpiar sugerencias
        const listId = `suggestions-${layerName.replace(/\s+/g, '-')}`;
        const listEl = document.getElementById(listId);
        if (listEl) {
            listEl.classList.add('hidden');
            listEl.innerHTML = '';
        }
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
