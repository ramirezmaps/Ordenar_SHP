import streamlit as st
import geopandas as gpd
import pandas as pd
import tempfile
import os
import shutil
import folium
import zipfile
from streamlit_folium import st_folium
from folium.plugins import Draw
import glob

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="GeoEditor Pro",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PROFESIONAL ---
st.markdown("""
    <style>
    /* Reset básico y Fuentes */
    .stApp {
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Maximizar area de trabajo */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 98% !important;
    }
    
    /* Header limpio */
    header[data-testid="stHeader"] {
        display: none;
    }
    
    /* Sidebar personalziado */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: #0f172a;
        font-weight: 600;
        letter-spacing: -0.025em;
    }
    
    /* Map Container Sizing - Vital para el look "App" */
    iframe {
        width: 100% !important;
        height: 85vh !important; /* Altura dinámica masiva */
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* Botones primarios mas atractivos */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

# ... (Imports anteriores se mantienen arriba, agregamos estos)
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from PIL import Image
import fiona

# Habilitar soporte para KML en Fiona (a veces desactivado por defecto)
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

# --- FUNCIONES AUXILIARES (RASTER) ---
def save_uploaded_files(uploaded_files):
    """Guarda los archivos subidos (shp, shx, dbf, etc.) en una carpeta temporal."""
    if not uploaded_files:
        return None, None
    
    temp_dir = tempfile.mkdtemp()
    
    saved_files = []
    
    for uploaded_file in uploaded_files:
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_files.append(file_path)
    
    # Retornamos el directorio temporal para buscar SHPs dentro
    return None, temp_dir


def process_raster_upload(uploaded_file):
    """Procesa una imagen georreferenciada: Reproyecta a 4326 y genera PNG + Bounds."""
    try:
        # Guardar archivo subido temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp_src:
            tmp_src.write(uploaded_file.getbuffer())
            src_path = tmp_src.name

        with rasterio.open(src_path) as src:
            # Definir destino WGS84
            dst_crs = 'EPSG:4326'
            
            # Calcular transformada para reproyección
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds)
            
            # Preparar array destino
            # Leemos bandas (asumimos RGB o Gra)
            # Simplificación: Usaremos la primera banda si es 1, o las 3 primeras si son más.
            
            if src.count >= 3:
                bands_to_read = [1, 2, 3] # RGB
                count = 3
            else:
                bands_to_read = [1] # Grayscale
                count = 1

            # Crear array destino para los datos reproyectados
            dest_array = np.zeros((count, height, width), dtype=np.uint8)

            for idx, band in enumerate(bands_to_read):
                reproject(
                    source=rasterio.band(src, band),
                    destination=dest_array[idx],
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest)

            # Generar Bounds [[lat_min, lon_min], [lat_max, lon_max]]
            # Folium espera [[lat_min, lon_min], [lat_max, lon_max]] -> SW, NE
            # Rasterio bounds: left, bottom, right, top -> lon_min, lat_min, lon_max, lat_max
            # new_bounds = (transform * (0, height)) , ...
            # Usaremos un método más directo para bounds lat/lon:
            lon_min, lat_min, lon_max, lat_max = rasterio.transform.array_bounds(height, width, transform)
            folium_bounds = [[lat_min, lon_min], [lat_max, lon_max]]

            # Convertir array a Imagen PIL y guardar como PNG
            # Formato (H, W, C) para PIL
            img_data = np.moveaxis(dest_array, 0, -1)
            
            if count == 1:
                img_data = img_data[:, :, 0] # Squeeze
                img = Image.fromarray(img_data, mode='L')
            else:
                img = Image.fromarray(img_data, mode='RGB')
                
            # Hacer transparente lo negro/nulo si se desea (opcional complejo)
            # Guardamos png temporal
            png_fd, png_path = tempfile.mkstemp(suffix=".png")
            os.close(png_fd)
            img.save(png_path, format="PNG")
            
            return png_path, folium_bounds

    except Exception as e:
        st.error(f"Error procesando raster: {e}")
        return None, None

def handle_table_edit():
    """Callback para manejar cambios en la tabla antes de recargar el script."""
    if "data_editor" not in st.session_state:
        return
        
    changes = st.session_state["data_editor"]
    needs_map_update = False
    
    # Referencia al DF de trabajo
    gdf = st.session_state['work_gdf']
    
    # 1. Filas Editadas
    # changes['edited_rows'] es {row_idx: {col_name: new_val}}
    for idx_str, edits in changes.get("edited_rows", {}).items():
        idx = int(idx_str)
        # Verificar integridad índex
        if idx < len(gdf):
            for col, val in edits.items():
                if col in gdf.columns:
                    # Aplicar cambio
                    gdf.at[idx, col] = val
                    if col == 'Seleccionar':
                        needs_map_update = True
                        
    # 2. Filas Borradas
    deleted = changes.get("deleted_rows", [])
    if deleted:
        # Borrar por índice y resetear
        st.session_state['work_gdf'] = gdf.drop(index=deleted).reset_index(drop=True)
        needs_map_update = True
        
    # (Opcional) Filas Agregadas - st.data_editor puede agregar filas vacías si num_rows="dynamic"
    # Handling complejo en GIS sin geometría, lo dejamos básico o ignoramos si no hay geom.
    # Por ahora el usuario agrega columnas o dibuja, no agrega filas manuales en blanco.
    
    # Si hubo cambio visual relevante, forzamos actualización de mapa
    if needs_map_update:
         if 'last_view' in st.session_state:
             if st.session_state['last_view']['center']:
                st.session_state['map_center'] = st.session_state['last_view']['center']
             if st.session_state['last_view']['zoom']:
                st.session_state['map_zoom'] = st.session_state['last_view']['zoom']
         
         st.session_state['map_key'] += 1

# --- APP PRINCIPAL ---

def main():
    # Título Flotante / Compacto
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; padding-bottom: 10px;">
            <h3 style="margin:0; padding:0;">✏️ GeoEditor Pro</h3>
            <span style="color:gray; font-size:0.9em;">| Editor GIS Web</span>
        </div>
    """, unsafe_allow_html=True)
    
    # --- ESTADO INICIAL ---
    if 'work_gdf' not in st.session_state:
        st.session_state['work_gdf'] = gpd.GeoDataFrame(columns=['geometry'], geometry='geometry', crs="EPSG:4326")
    if 'map_key' not in st.session_state:
        st.session_state['map_key'] = 0
    # Estado para capas de referencia persistentes (cache simple por nombre)
    if 'ref_layers' not in st.session_state:
        st.session_state['ref_layers'] = {} # {name: {'type': 'vector'/'raster', 'data': gdf/path, 'bounds': ...}}
    
    # Estado del Mapa (Vista)
    if 'map_center' not in st.session_state:
        st.session_state['map_center'] = [-33.4489, -70.6693]
    if 'map_zoom' not in st.session_state:
        st.session_state['map_zoom'] = 10

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.title("🗺️ Herramientas")
        
        # 1. GESTIÓN DE DATOS Y PROYECTO
        with st.expander("📂 Proyecto y Datos", expanded=True):
            st.markdown("**Archivo de Trabajo**")
            default_path = os.path.join(os.getcwd(), "mis_dibujos.geojson")
            work_path = st.text_input("Ruta:", value=default_path, label_visibility="collapsed")
            
            c_load, c_save = st.columns(2)
            if c_load.button("📂 Cargar"):
                if os.path.exists(work_path):
                    try:
                        loaded_gdf = gpd.read_file(work_path)
                        if loaded_gdf.crs and loaded_gdf.crs.to_string() != "EPSG:4326":
                            loaded_gdf = loaded_gdf.to_crs(epsg=4326)
                        st.session_state['work_gdf'] = loaded_gdf
                        st.session_state['map_key'] += 1
                        st.success("Cargado")
                    except Exception as e: st.error(str(e))
            
            if c_save.button("💾 Guardar"):
                try:
                    gdf_save = st.session_state['work_gdf'].copy()
                    if work_path.endswith(".shp"):
                        gdf_save.to_file(work_path)
                    else:
                        gdf_save.to_file(work_path, driver="GeoJSON")
                    st.success("Guardado!")
                except Exception as e: st.error(str(e))
                
            st.divider()
            st.markdown("**Gestión de Campos**")
            new_col_name = st.text_input("Nombre Columna", placeholder="Ej: Comentario")
            new_col_type = st.selectbox("Tipo", ["Texto", "Número Entero", "Número Decimal"], label_visibility="collapsed")
            
            if st.button("➕ Crear Columna"):
                if new_col_name:
                    if new_col_name not in st.session_state['work_gdf'].columns:
                        if new_col_type == "Número Entero":
                                st.session_state['work_gdf'][new_col_name] = pd.Series(dtype='Int64')
                        elif new_col_type == "Número Decimal":
                                st.session_state['work_gdf'][new_col_name] = pd.Series(dtype='float')
                        else:
                                st.session_state['work_gdf'][new_col_name] = None
                        st.success(f"Campo '{new_col_name}' ok.")
                        st.rerun()
                else:
                    st.warning("Esa columna ya existe.")

        # 2. CAPAS Y ESTILOS
        with st.expander("🎨 Capas y Estilos", expanded=False):
            st.markdown("**Capas de Referencia**")
            uploaded_refs = st.file_uploader(
                "Subir (SHP/KML/TIF)", 
                accept_multiple_files=True, 
                key="refs",
            )
            
            if uploaded_refs:
                if st.button("🔄 Procesar Capas"):
                    with st.spinner("Procesando..."):
                        _, temp_dir = save_uploaded_files(uploaded_refs)
                        
                        # SHP
                        if temp_dir:
                            import glob
                            shapefiles_found = glob.glob(os.path.join(temp_dir, "*.shp"))
                            for shp_path in shapefiles_found:
                                try:
                                    gdf = gpd.read_file(shp_path)
                                    if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                                        gdf = gdf.to_crs(epsg=4326)
                                    name = os.path.basename(shp_path)
                                    st.session_state['ref_layers'][name] = {'type': 'vector', 'data': gdf}
                                except Exception as e: st.error(f"{shp_path}: {e}")
                        
                        # Raster/KML
                        for f in uploaded_refs:
                            if f.name.lower().endswith(('.tif', '.tiff')):
                                png_path, bounds = process_raster_upload(f)
                                if png_path: st.session_state['ref_layers'][f.name] = {'type': 'raster', 'data': png_path, 'bounds': bounds}
                            elif f.name.lower().endswith(('.kml', '.kmz')):
                                try:
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{f.name}") as tmp:
                                        tmp.write(f.getbuffer())
                                        path = tmp.name
                                    # Lógica básica KML
                                    gdf_kml = gpd.read_file(path) # Puede fallar si no hay soporte, try/catch wrap
                                    if not gdf_kml.empty:
                                        if gdf_kml.crs and gdf_kml.crs.to_string() != "EPSG:4326": gdf_kml = gdf_kml.to_crs(epsg=4326)
                                        st.session_state['ref_layers'][f.name] = {'type': 'vector', 'data': gdf_kml}
                                except: pass 

                        st.success(f"Capas: {len(st.session_state['ref_layers'])}")
            
            st.divider()
            st.markdown("**Estilo Dibujo**")
            work_color = st.color_picker("Color Dibujo", st.session_state.get('style_work_color', "#2563eb"))
            st.session_state['style_work_color'] = work_color
            
            if st.session_state['ref_layers']:
                st.markdown("**Estilo Referencias**")
                for name, layer in st.session_state['ref_layers'].items():
                    if layer['type'] == 'vector':
                        current = layer.get('color', '#555555')
                        new = st.color_picker(f"{name}", current)
                        if new != current:
                            st.session_state['ref_layers'][name]['color'] = new
                            st.session_state['map_key'] += 1
                            st.rerun()

        # 3. BUSQUEDA
        with st.expander("� Buscador", expanded=False):
             vector_layers = {k:v for k,v in st.session_state['ref_layers'].items() if v['type'] == 'vector'}
             if vector_layers:
                sel_layer = st.selectbox("Capa", list(vector_layers.keys()))
                if sel_layer:
                    gdf_s = vector_layers[sel_layer]['data']
                    cols_s = list(gdf_s.columns.drop('geometry'))
                    col_id = st.selectbox("Campo", cols_s)
                    if col_id:
                        val = st.selectbox("Valor", gdf_s[col_id].astype(str).unique())
                        if st.button("� Localizar"):
                             subset = gdf_s[gdf_s[col_id].astype(str) == val]
                             if not subset.empty:
                                 geom = subset.geometry.iloc[0]
                                 minx, miny, maxx, maxy = geom.bounds
                                 st.session_state['map_active_bounds'] = [[miny, minx], [maxy, maxx]]
                                 st.session_state['map_key'] += 1
                                 st.session_state['search_highlight'] = geom.__geo_interface__
                                 st.rerun()
             else:
                 st.caption("Carga capas para buscar.")


    # --- ZONA PRINCIPAL ---
    # Layout Simplicado: Mapa arriba, Tabla abajo.
    # El layout split estaba causando problemas de repintado.
    
    st.subheader("🌍 Mapa de Trabajo")
    
    if 'Seleccionar' not in st.session_state['work_gdf'].columns:
        st.session_state['work_gdf'].insert(0, 'Seleccionar', False)
    
    # Estado temporal para la vista (evita reset al mover el mapa)
    if 'last_view' not in st.session_state:
        st.session_state['last_view'] = {'center': None, 'zoom': None}
        
    # Crear mapa
    m = folium.Map(
        location=st.session_state.get('map_center', [-33.4489, -70.6693]), 
        zoom_start=st.session_state.get('map_zoom', 10), 
        tiles="CartoDB positron"
    )
    
    # Adicionar Capa Satelital (Esri World Imagery)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satelite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Aplicar Zoom
    if 'map_active_bounds' in st.session_state:
        m.fit_bounds(st.session_state['map_active_bounds'])
        del st.session_state['map_active_bounds']

    # Highlight Búsqueda
    if 'search_highlight' in st.session_state:
        folium.GeoJson(
            st.session_state['search_highlight'],
            name="Resultado Búsqueda",
            style_function=lambda x: {'color': 'orange', 'weight': 4, 'fillOpacity': 0.0, 'dashArray': '5, 5'}
        ).add_to(m)
    
    st.markdown("""<style>.leaflet-div-icon { background: #fff; border: 1px solid #666; border-radius: 50%; }</style>""", unsafe_allow_html=True)
    
    # RENDER REFERENCIAS
    for name, layer in st.session_state['ref_layers'].items():
        if layer['type'] == 'vector':
            valid_tooltip_cols = [c for c in layer['data'].columns if c != 'geometry' and c != 'style']
            tooltip_fields = valid_tooltip_cols[:3]
            layer_color = layer.get('color', '#555555')
            
            folium.GeoJson(
                layer['data'], name=f"Ref: {name}",
                style_function=lambda x, col=layer_color: {'color': col, 'weight': 1, 'fillOpacity': 0.1},
                tooltip=folium.GeoJsonTooltip(fields=tooltip_fields) if tooltip_fields else None,
                popup=folium.GeoJsonPopup(fields=valid_tooltip_cols, localize=True) if valid_tooltip_cols else None
            ).add_to(m)
        elif layer['type'] == 'raster':
            folium.raster_layers.ImageOverlay(
                image=layer['data'], bounds=layer['bounds'], opacity=0.6, name=f"Img: {name}"
            ).add_to(m)

    # CAPA DE TRABAJO
    wgdf = st.session_state['work_gdf']
    w_color = st.session_state.get('style_work_color', '#2563eb')
    
    if not wgdf.empty:
        st.session_state['work_gdf']['Seleccionar'] = st.session_state['work_gdf']['Seleccionar'].astype(bool)
        selected_mask = wgdf['Seleccionar']
        
        if not wgdf[~selected_mask].empty:
            folium.GeoJson(
                wgdf[~selected_mask].drop(columns=['Seleccionar']), name="Datos",
                style_function=lambda x: {'color': w_color, 'weight': 3, 'fillOpacity': 0.4},
                marker=folium.CircleMarker(radius=4, fill_color=w_color, fill_opacity=0.6, color='white', weight=1)
            ).add_to(m)
        if not wgdf[selected_mask].empty:
            folium.GeoJson(
                wgdf[selected_mask].drop(columns=['Seleccionar']), name="Seleccionados",
                style_function=lambda x: {'color': '#ef4444', 'weight': 5, 'fillOpacity': 0.7},
                marker=folium.CircleMarker(radius=6, fill_color='#ef4444', fill_opacity=0.9, color='black', weight=2)
            ).add_to(m)

    # DIBUJOS PENDIENTES (Visualización Persistente)
    pending = st.session_state.get('pending_drawings', [])
    if pending:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": pending},
            name="Dibujos en Espera",
            style_function=lambda x: {'color': '#f59e0b', 'weight': 3, 'dashArray': '5, 5', 'fillOpacity': 0.2},
            tooltip="Elemento no guardado"
        ).add_to(m)

    # DIBUJO
    draw = Draw(
        export=False, position='topleft',
        draw_options={
            'polyline': True, 'polygon': True, 'rectangle': True, 
            'circle': False, 'marker': False, 'circlemarker': True
        },
        edit_options={'edit': False, 'remove': False}
    )
    draw.add_to(m)
    folium.LayerControl().add_to(m)
    
    # RENDER ST_FOLIUM
    # Restringimos returned_objects para evitar recargas excesivas al mover el mapa (bounds, etc).
    output = st_folium(
        m, width="100%", height=500, 
        key=f"map_{st.session_state['map_key']}",
        returned_objects=["all_drawings", "zoom", "center"]
    )
    
    # Persistir Vista (Solo en memoria temporal, NO en el state que reinicia el mapa)
    if output:
        if "center" in output and output["center"]:
             st.session_state['last_view']['center'] = [output["center"]["lat"], output["center"]["lng"]]
        if "zoom" in output and output["zoom"]:
             st.session_state['last_view']['zoom'] = output["zoom"]

    # LOGICA DE CAPTURA ROBUSTA
    if output and "all_drawings" in output:
        out_drawings = output["all_drawings"]
        
        # Normalizar a lista de features
        features_captured = []
        if isinstance(out_drawings, list): 
            features_captured = out_drawings
        elif isinstance(out_drawings, dict) and "features" in out_drawings: 
            features_captured = out_drawings["features"]
        
        if features_captured:
            # Estrategia: "Acumular y Limpiar"
            # Capturamos lo nuevo, lo agregamos a pending, y forzamos rerun.
            # Al hacer rerun, el mapa se regenera (Draw vacío) y mostramos los items como GeoJson fijo.
            
            import json
            current_pending = st.session_state.get('pending_drawings', [])
            
            # Deduplicación básica usando GeoJSON string
            # (El cliente puede devolver lo mismo si no hubo reset, evitamos duplicados)
            existing_geoms = {json.dumps(f['geometry'], sort_keys=True) for f in current_pending}
            
            added_count = 0
            for f in features_captured:
                f_geom_str = json.dumps(f['geometry'], sort_keys=True)
                if f_geom_str not in existing_geoms:
                    current_pending.append(f)
                    existing_geoms.add(f_geom_str)
                    added_count += 1
            
            if added_count > 0:
                st.session_state['pending_drawings'] = current_pending
                
                # Sincronizar vista para que no se resetee al redibujar el mapa
                if st.session_state['last_view']['center']:
                     st.session_state['map_center'] = st.session_state['last_view']['center']
                if st.session_state['last_view']['zoom']:
                     st.session_state['map_zoom'] = st.session_state['last_view']['zoom']
                
                st.rerun()

    # MENU DE GUARDADO (Si hay pendientes)
    final_features = st.session_state.get('pending_drawings', [])
    if final_features:
        st.info(f"📍 {len(final_features)} objeto(s) en espera de ser guardados en la tabla.")
        
        c_save, c_clear = st.columns([1, 4])
        if c_save.button("Guardar en Tabla", type="primary"):
            try:
                new_gdf = gpd.GeoDataFrame.from_features(final_features, crs="EPSG:4326")
                # Alinear columnas
                for col in st.session_state['work_gdf'].columns:
                    if col not in new_gdf.columns and col != 'geometry':
                         # Inicializar vacíos. Cuidado con tipos.
                        new_gdf[col] = False if col == 'Seleccionar' else None
                
                # Concatenar
                st.session_state['work_gdf'] = pd.concat([st.session_state['work_gdf'], new_gdf], ignore_index=True)
                
                # Sincronizar vista antes de recargar
                if st.session_state['last_view']['center']:
                     st.session_state['map_center'] = st.session_state['last_view']['center']
                if st.session_state['last_view']['zoom']:
                     st.session_state['map_zoom'] = st.session_state['last_view']['zoom']

                st.session_state['map_key'] += 1
                
                # Limpiar pendientes tras guardar
                st.session_state['pending_drawings'] = []
                
                st.success("Guardado ok")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        
        if c_clear.button("🗑️ Descartar Pendientes"):
             st.session_state['pending_drawings'] = []
             st.rerun()

    # TABLA (Abajo)
    st.divider()
    st.subheader("📋 Tabla de Atributos")
    
    if not st.session_state['work_gdf'].empty:
        cols = ['Seleccionar'] + [c for c in st.session_state['work_gdf'].columns if c != 'Seleccionar' and c != 'geometry']
        
        edited_df = st.data_editor(
            st.session_state['work_gdf'][cols],
            num_rows="dynamic", 
            use_container_width=True,
            key="data_editor",
            column_config={"Seleccionar": st.column_config.CheckboxColumn("Ver", width="small")},
            on_change=handle_table_edit
        )
        
        # Sincronización manejada por callback 'handle_table_edit' para evitar doble refresco y perdida de foco.
        pass
    else:
        st.info("No hay datos aún.")

if __name__ == "__main__":
    main()
