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
    page_title="Editor Geoespacial",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
        color: #1e293b;
        font-weight: 700;
    }
    /* Ajustes para maximizar el mapa */
    iframe {
        width: 100%;
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

# --- APP PRINCIPAL ---

def main():
    st.title("✏️ Editor de Mapas y Geometrías")
    st.markdown("Dibuja, define atributos y exporta datos compatibles con GIS (QGIS/ArcGIS).")
    
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
        st.header("1. Configuración")
        
        # A. Capas de Referencia
        with st.expander("📂 Capas de Referencia (SHP/TIF)"):
            uploaded_refs = st.file_uploader(
                "Subir archivos", 
                accept_multiple_files=True, 
                key="refs",
                help="Soporta Shapefiles (.shp+.shx+.dbf) e Imágenes GeoTIFF (.tif)"
            )
            
            if uploaded_refs:
                # Botón procesar para no re-procesar en cada rerun si no cambia
                if st.button("🔄 Procesar Capas Subidas"):
                    with st.spinner("Procesando referencias..."):
                        # 1. Separar Vectores y Rasters
                        shps = []
                        tifs = []
                        others = [] # components like .shx
                        
                        # Guardar todo en temp primero para agrupar SHPs
                        # Usamos la funcion save_uploaded_files existente para SHP
                        _, temp_dir = save_uploaded_files(uploaded_refs)
                        
                        # --- Procesar SHPs ---
                        if temp_dir:
                            import glob
                            shapefiles_found = glob.glob(os.path.join(temp_dir, "*.shp"))
                            for shp_path in shapefiles_found:
                                try:
                                    gdf = gpd.read_file(shp_path)
                                    if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                                        gdf = gdf.to_crs(epsg=4326)
                                    
                                    name = os.path.basename(shp_path)
                                    st.session_state['ref_layers'][name] = {
                                        'type': 'vector',
                                        'data': gdf
                                    }
                                except Exception as e:
                                    st.error(f"Error SHP {shp_path}: {e}")
                            
                        # --- Procesar rasters y KML/KMZ (uploaded_refs directo) ---
                        for f in uploaded_refs:
                            # Raster
                            if f.name.lower().endswith(('.tif', '.tiff')):
                                png_path, bounds = process_raster_upload(f)
                                if png_path and bounds:
                                    st.session_state['ref_layers'][f.name] = {
                                        'type': 'raster',
                                        'data': png_path,
                                        'bounds': bounds
                                    }
                            
                            # KML/KMZ
                            elif f.name.lower().endswith(('.kml', '.kmz')):
                                try:
                                    # Geopandas needs 'fiona' with KML driver enabled mostly.
                                    # Direct "read_file" can read KML if driver supported.
                                    # For KMZ, it's a zip. We need to unzip or handle via fiona virtual filesystem.
                                    # Simplest: Save to file, extract if KMZ, read with gpd.
                                    
                                    # Save temp
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{f.name}") as tmp_kml:
                                        tmp_kml.write(f.getbuffer())
                                        kml_path = tmp_kml.name
                                        
                                    # Handle KMZ (Zip)
                                    target_load_path = kml_path
                                    if f.name.lower().endswith('.kmz'):
                                        with zipfile.ZipFile(kml_path, 'r') as z:
                                            # KMZ usually has a doc.kml inside
                                            kml_files = [n for n in z.namelist() if n.endswith('.kml')]
                                            if kml_files:
                                                z.extract(kml_files[0], os.path.dirname(kml_path))
                                                target_load_path = os.path.join(os.path.dirname(kml_path), kml_files[0])
                                    
                                    # Load with GeoPandas
                                    # Forzar driver 'KML' si LIBKML falla o es ambiguo
                                    try:
                                        gdf_kml = gpd.read_file(target_load_path, driver='KML')
                                    except:
                                        # Fallback sin especificar driver
                                        gdf_kml = gpd.read_file(target_load_path)
                                    
                                    if not gdf_kml.empty:
                                       if gdf_kml.crs and gdf_kml.crs.to_string() != "EPSG:4326":
                                           gdf_kml = gdf_kml.to_crs(epsg=4326)
                                           
                                       st.session_state['ref_layers'][f.name] = {
                                            'type': 'vector',
                                            'data': gdf_kml
                                       }
                                except Exception as e:
                                    st.error(f"Error KML/KMZ {f.name}: {e}. (Asegúrate que GDAL soporte KML/LIBKML)")

                        st.success(f"Referencias cargadas: {len(st.session_state['ref_layers'])}")

        # B. Buscador y Zoom
        st.divider()
        st.markdown("### 🔍 Inspector y Zoom")
        
        # Filtrar solo vectores para búsqueda
        vector_layers = {k:v for k,v in st.session_state['ref_layers'].items() if v['type'] == 'vector'}
        
        if vector_layers:
            sel_layer_name = st.selectbox("Capa:", options=list(vector_layers.keys()))
            if sel_layer_name:
                gdf_search = vector_layers[sel_layer_name]['data']
                cols = list(gdf_search.columns.drop('geometry'))
                
                sel_col = st.selectbox("Columna ID/Nombre:", options=cols, index=0 if cols else None)
                
                if sel_col:
                    # Limitar valores para performance
                    unique_vals = gdf_search[sel_col].astype(str).unique()
                    sel_val = st.selectbox("Valor:", options=unique_vals)
                    
                    if st.button("📍 Ir al Objeto"):
                        # Buscar geometría
                        subset = gdf_search[gdf_search[sel_col].astype(str) == sel_val]
                        if not subset.empty:
                            geom = subset.geometry.iloc[0]
                            # Bounds: minx, miny, maxx, maxy
                            minx, miny, maxx, maxy = geom.bounds
                            
                            # Folium fit_bounds espera [[lat_min, lon_min], [lat_max, lon_max]]
                            # que corresponde a [[miny, minx], [maxy, maxx]]
                            bounds_to_fit = [[miny, minx], [maxy, maxx]]
                            
                            st.session_state['map_active_bounds'] = bounds_to_fit
                            st.session_state['map_key'] += 1 # Forzar recarga mapa
                            
                            # Opcional: guardar geometría resaltada temporalmente
                            st.session_state['search_highlight'] = geom.__geo_interface__
                            
                            st.rerun()
        else:
            st.caption("Sube shapefiles para buscar objetos.")
            
        # C. Gestión de Estilos (NUEVO)
        st.divider()
        with st.expander("🎨 Estilos y Colores", expanded=False):
            st.markdown("#### Capa de Trabajo (Dibujo)")
            # Color default azul
            work_color = st.color_picker("Color Elementos", "#2563eb", key="picker_work")
            st.session_state['style_work_color'] = work_color
            
            st.divider()
            st.markdown("#### Capas de Referencia")
            if st.session_state['ref_layers']:
                for name, layer in st.session_state['ref_layers'].items():
                    if layer['type'] == 'vector':
                        # Default gray
                        current_c = layer.get('color', '#555555')
                        new_c = st.color_picker(f"Color: {name}", current_c, key=f"picker_{name}")
                        if new_c != current_c:
                            st.session_state['ref_layers'][name]['color'] = new_c
                            st.session_state['map_key'] += 1 # Forzar recarga si cambia color
                            st.rerun()
            else:
                st.caption("No hay capas de referencia.")


        # D. Archivo de Trabajo y Tablas (Código existente, condensado visualmente)
        st.divider()
        with st.expander("💾 Configuración de Guardado"):
            default_path = os.path.join(os.getcwd(), "mis_dibujos.geojson")
            work_path = st.text_input("Ruta:", value=default_path)
            
            c1, c2 = st.columns(2)
            if c1.button("🔄 Cargar"):
                if os.path.exists(work_path):
                    try:
                        loaded_gdf = gpd.read_file(work_path)
                        if loaded_gdf.crs and loaded_gdf.crs.to_string() != "EPSG:4326":
                            loaded_gdf = loaded_gdf.to_crs(epsg=4326)
                        st.session_state['work_gdf'] = loaded_gdf
                        st.session_state['map_key'] += 1
                        st.success(f"Cargado")
                    except Exception as e: st.error(str(e))
            
            if c2.button("💾 Guardar"):
                try:
                    gdf_save = st.session_state['work_gdf'].copy()
                    if work_path.endswith(".shp"):
                        gdf_save.to_file(work_path)
                    else:
                        gdf_save.to_file(work_path, driver="GeoJSON")
                    st.success("Guardado")
                except Exception as e: st.error(str(e))

        st.divider()
        st.markdown("### 📝 Gestión de Campos")
        new_col_name = st.text_input("Nombre de nueva columna")
        new_col_type = st.selectbox("Tipo de dato", ["Texto", "Número Entero", "Número Decimal"])
        
        if st.button("➕ Agregar Columna"):
            if new_col_name:
                if new_col_name not in st.session_state['work_gdf'].columns:
                    # Inicializar con valores nulos del tipo correcto si es posible, o None
                    if new_col_type == "Número Entero":
                         st.session_state['work_gdf'][new_col_name] = pd.Series(dtype='Int64') # Int64 soporta NaN
                    elif new_col_type == "Número Decimal":
                         st.session_state['work_gdf'][new_col_name] = pd.Series(dtype='float')
                    else:
                         st.session_state['work_gdf'][new_col_name] = None
                         
                    st.success(f"Columna '{new_col_name}' agregada.")
                    st.rerun()
                else:
                    st.warning("Esa columna ya existe.")
            else:
                st.warning("Ingresa un nombre para la columna.")


    # --- ZONA PRINCIPAL ---
    # Layout Simplicado: Mapa arriba, Tabla abajo.
    # El layout split estaba causando problemas de repintado.
    
    st.subheader("🌍 Mapa de Trabajo")
    
    if 'Seleccionar' not in st.session_state['work_gdf'].columns:
        st.session_state['work_gdf'].insert(0, 'Seleccionar', False)
        
    # Crear mapa
    m = folium.Map(
        location=st.session_state.get('map_center', [-33.4489, -70.6693]), 
        zoom_start=st.session_state.get('map_zoom', 10), 
        tiles="CartoDB positron"
    )
    
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
                tooltip=folium.GeoJsonTooltip(fields=tooltip_fields) if tooltip_fields else None
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
    # Quitamos returned_objects restringidos para máxima estabilidad
    # Priorizamos que funcione.
    output = st_folium(
        m, width="100%", height=500, 
        key=f"map_{st.session_state['map_key']}",
        # No especificamos returned_objects para que traiga todo por defecto y sea más estable
    )
    
    # Persistir Vista
    if output:
        if "center" in output and output["center"]:
             st.session_state['map_center'] = [output["center"]["lat"], output["center"]["lng"]]
        if "zoom" in output and output["zoom"]:
             st.session_state['map_zoom'] = output["zoom"]

    # INCORPORACIÓN DIRECTA
    if output and "all_drawings" in output:
        features = []
        if isinstance(output["all_drawings"], list): features = output["all_drawings"]
        elif isinstance(output["all_drawings"], dict) and "features" in output["all_drawings"]: features = output["all_drawings"]["features"]
        
        if features:
            st.info(f"📍 {len(features)} objeto(s) nuevo(s) detectado(s).")
            # Botón simple y directo
            if st.button("Guardar en Tabla", type="primary"):
                try:
                    new_gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
                    # Alinear columnas
                    for col in st.session_state['work_gdf'].columns:
                        if col not in new_gdf.columns and col != 'geometry':
                            new_gdf[col] = False if col == 'Seleccionar' else None
                    
                    # Concatenar
                    st.session_state['work_gdf'] = pd.concat([st.session_state['work_gdf'], new_gdf], ignore_index=True)
                    st.session_state['map_key'] += 1
                    st.success("Guardado ok")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

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
            column_config={"Seleccionar": st.column_config.CheckboxColumn("Ver", width="small")}
        )
        
        # Sincronización simple
        if not edited_df.equals(st.session_state['work_gdf'][cols]):
            try:
                # Update básico de valores
                for col in edited_df.columns:
                     st.session_state['work_gdf'][col] = edited_df[col]
                
                # Handling borrar filas (Longitud diferente)
                if len(edited_df) != len(st.session_state['work_gdf']):
                     # Si es menor, asumimos borrado y reasignamos por index del editor
                     if len(edited_df) < len(st.session_state['work_gdf']):
                         st.session_state['work_gdf'] = st.session_state['work_gdf'].iloc[edited_df.index].reset_index(drop=True)
                     # Si es mayor (agregado manual), cuidado, no tiene geometry.
                
                # Check highlight
                if not edited_df['Seleccionar'].equals(st.session_state['work_gdf'][cols]['Seleccionar']):
                     st.session_state['map_key'] += 1
                     st.rerun()
            except: pass
    else:
        st.info("No hay datos aún.")

if __name__ == "__main__":
    main()
