import streamlit as st
import geopandas as gpd
import pandas as pd
import tempfile
import os
import zipfile
import shutil
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Shapefile Comparator Pro",
    page_icon="🗺️",
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
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        text-align: center;
    }
    .stAlert {
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---

def save_uploaded_files(uploaded_files):
    """Guarda los archivos subidos (shp, shx, dbf, etc.) en una carpeta temporal."""
    if not uploaded_files:
        return None, None
    
    temp_dir = tempfile.mkdtemp()
    
    shp_file = None
    saved_files = []
    
    for uploaded_file in uploaded_files:
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_files.append(file_path)
        if uploaded_file.name.lower().endswith(".shp"):
            shp_file = file_path
            
    # Validación básica: advertir si faltan archivos críticos
    extensions = [os.path.splitext(f)[1].lower() for f in saved_files]
    if ".shp" not in extensions:
        return None, temp_dir
        
    return shp_file, temp_dir

def load_data(shp_path):
    """Carga el shapefile usando Geopandas."""
    try:
        gdf = gpd.read_file(shp_path)
        return gdf
    except Exception as e:
        st.error(f"Error al leer el archivo SHP: {e}")
        return None

def compare_schemas(gdf1, gdf2):
    """Compara las columnas y tipos de datos."""
    cols1 = set(gdf1.columns)
    cols2 = set(gdf2.columns)
    
    common_cols = cols1.intersection(cols2)
    unique_1 = cols1 - cols2
    unique_2 = cols2 - cols1
    
    dtypes_diff = []
    for col in common_cols:
        if gdf1[col].dtype != gdf2[col].dtype:
            dtypes_diff.append({
                "Columna": col,
                "Tipo en Archivo 1": str(gdf1[col].dtype),
                "Tipo en Archivo 2": str(gdf2[col].dtype)
            })
            
    return common_cols, unique_1, unique_2, dtypes_diff

# --- INTERFAZ PRINCIPAL ---

st.title("🗺️ Comparador de Shapefiles")
st.markdown("### Analiza y visualiza diferencias entre dos archivos geoespaciales")

with st.expander("ℹ️ Instrucciones"):
    st.write("""
    1. Para cada capa, selecciona **todos** los archivos que componen el Shapefile (.shp, .shx, .dbf, .prj, etc.) al mismo tiempo.
    2. La aplicación identificará el archivo .shp principal y usará los auxiliares automáticamente.
    3. Visualiza las diferencias en el mapa interactivo.
    """)

col_upload_1, col_upload_2 = st.columns(2)

with col_upload_1:
    st.subheader("📂 Archivo 1 (Referencia)")
    files1 = st.file_uploader("Sube los archivos (.shp, .shx, .dbf...)", accept_multiple_files=True, key="files1")

with col_upload_2:
    st.subheader("📂 Archivo 2 (Comparación)")
    files2 = st.file_uploader("Sube los archivos (.shp, .shx, .dbf...)", accept_multiple_files=True, key="files2")

if files1 and files2:
    with st.spinner("Procesando archivos..."):
        path1, dir1 = save_uploaded_files(files1)
        path2, dir2 = save_uploaded_files(files2)
        
        if not path1:
            st.error("❌ En el Grupo 1 falta el archivo .shp")
        elif not path2:
            st.error("❌ En el Grupo 2 falta el archivo .shp")
        else:
            gdf1 = load_data(path1)
            gdf2 = load_data(path2)
            
            if gdf1 is not None and gdf2 is not None:
                st.success("Archivos cargados correctamente.")
                
                # --- SELECCIÓN DE ID & ANÁLISIS AVANZADO ---
                st.divider()
                st.markdown("### 🔎 Comparación Avanzada por ID")
                
                # Detectar columnas comunes para sugerir ID
                common_cols = list(set(gdf1.columns).intersection(set(gdf2.columns)))
                common_cols.sort()
                
                # Intentar adivinar el ID
                default_idx = 0
                possible_ids = ['id', 'objectid', 'clave', 'code', 'rol']
                for i, col in enumerate(common_cols):
                    if col.lower() in possible_ids:
                        default_idx = i
                        break
                
                id_col = st.selectbox(
                    "Selecciona la columna con el Identificador Único (ID) para cruzar los datos:", 
                    options=common_cols,
                    index=default_idx
                )
                
                run_comparison = st.checkbox("Ejecutar comparación detallada (puede tardar en archivos grandes)", value=False)
                
                # --- PESTAÑAS DE ANÁLISIS ---
                if run_comparison:
                    # Preparar datos
                    gdf1 = gdf1.set_index(id_col)
                    gdf2 = gdf2.set_index(id_col)
                    
                    ids1 = set(gdf1.index)
                    ids2 = set(gdf2.index)
                    
                    added_ids = ids2 - ids1
                    removed_ids = ids1 - ids2
                    common_ids = ids1.intersection(ids2)
                    
                    # Analizar comunes
                    modified_attrs = []
                    modified_geom = []
                    
                    # Columns to compare (excluding geometry)
                    compare_cols = [c for c in common_cols if c != id_col and c != 'geometry']
                    
                    with st.spinner(f"Analizando {len(common_ids)} registros comunes..."):
                        for uid in common_ids:
                            row1 = gdf1.loc[uid]
                            row2 = gdf2.loc[uid]
                            
                            # 1. Comparar Atributos
                            diffs = {}
                            for col in compare_cols:
                                val1 = row1[col]
                                val2 = row2[col]
                                # Manejo básico de nulos y tipos
                                if pd.isna(val1) and pd.isna(val2):
                                    continue
                                if str(val1) != str(val2):
                                    diffs[col] = f"{val1} -> {val2}"
                            
                            if diffs:
                                diffs[id_col] = uid
                                modified_attrs.append(diffs)
                                
                            # 2. Comparar Geometría (simplificado)
                            # Usamos geom_equals o distance muy pequeña
                            g1 = row1.geometry
                            g2 = row2.geometry
                            
                            if g1 is not None and g2 is not None:
                                # Normalizar geometrías si es posible (buffer(0))
                                if not g1.geom_equals(g2):
                                    # Ver si es diferencia significativa (opcional: área/distancia)
                                    modified_geom.append(uid)

                    st.success("Análisis completado")
                    
                    tab_resumen, tab_detalles, tab_estructura, tab_grafico = st.tabs([
                        "📊 Resultados Clave", 
                        "📋 Detalle de Cambios",
                        "🏗️ Estructura", 
                        "🌍 Mapa Avanzado"
                    ])
                    
                    with tab_resumen:
                         c1, c2, c3, c4 = st.columns(4)
                         c1.metric("🆕 Nuevos Registros", len(added_ids))
                         c2.metric("❌ Registros Eliminados", len(removed_ids))
                         c3.metric("📝 Atributos Modificados", len(modified_attrs))
                         c4.metric("📐 Geometría Modificada", len(modified_geom))
                         
                         st.markdown("#### Resumen Gráfico")
                         chart_data = pd.DataFrame({
                             "Categoría": ["Nuevos", "Eliminados", "Modif. Atributos", "Modif. Geometría"],
                             "Cantidad": [len(added_ids), len(removed_ids), len(modified_attrs), len(modified_geom)]
                         })
                         st.bar_chart(chart_data.set_index("Categoría"))

                    with tab_detalles:
                        st.subheader("1. Cambios en Atributos")
                        if modified_attrs:
                            df_mod = pd.DataFrame(modified_attrs)
                            # Mover ID al principio
                            cols = [id_col] + [c for c in df_mod.columns if c != id_col]
                            st.dataframe(df_mod[cols], use_container_width=True)
                            st.download_button("Descargar Cambios de Atributos (CSV)", df_mod.to_csv().encode('utf-8'), "cambios_atributos.csv")
                        else:
                            st.info("No se detectaron diferencias en atributos para los registros comunes.")

                        st.divider()

                        c_new, c_del = st.columns(2)
                        with c_new:
                            st.subheader("2. Registros Nuevos (Solo en Archivo 2)")
                            if added_ids:
                                df_added = gdf2.loc[list(added_ids)].reset_index()
                                st.dataframe(df_added.drop(columns='geometry', errors='ignore').head(), use_container_width=True)
                                st.caption(f"Total: {len(added_ids)}")
                        with c_del:
                            st.subheader("3. Registros Eliminados (Solo en Archivo 1)")
                            if removed_ids:
                                df_removed = gdf1.loc[list(removed_ids)].reset_index()
                                st.dataframe(df_removed.drop(columns='geometry', errors='ignore').head(), use_container_width=True)
                                st.caption(f"Total: {len(removed_ids)}")
                                
                    with tab_estructura:
                         # Reutilizar lógica existente pero dentro de la pestaña
                         common, u1, u2, dtype_mismatch = compare_schemas(gdf1.reset_index(), gdf2.reset_index())
                         col_struct_1, col_struct_2 = st.columns(2)
                         with col_struct_1:
                            st.markdown("##### Columnas exclusivas en Archivo 1")
                            if u1: st.dataframe(pd.DataFrame(list(u1), columns=["Nombre Columna"]), use_container_width=True)
                         with col_struct_2:
                            st.markdown("##### Columnas exclusivas en Archivo 2")
                            if u2: st.dataframe(pd.DataFrame(list(u2), columns=["Nombre Columna"]), use_container_width=True)

                else:
                    # VISTA SIMPLE (SIN ID SELECCIONADO AÚN O CHECKBOX OFF)
                    st.info("Activa la casilla 'Ejecutar comparación detallada' para ver el análisis de altas, bajas y modificaciones.")
                    
                    tab_resumen, tab_estructura, tab_datos, tab_grafico = st.tabs([
                        "📊 Resumen General", 
                        "🏗️ Estructura & Schema", 
                        "📋 Datos & Atributos", 
                        "🌍 Visualización Gráfica"
                    ])
                    # ... (Mantener la lógica básica anterior como fallback o vista rápida)
                    with tab_resumen:
                         # ... (Lógica simple original)
                         st.markdown("#### Métricas Principales")
                         m1, m2 = st.columns(2)
                         m1.metric("Filas Archivo 1", len(gdf1))
                         m2.metric("Filas Archivo 2", len(gdf2))
                    
                    with tab_estructura:
                         # ... (Lógica simple original)
                         common, u1, u2, dtype_mismatch = compare_schemas(gdf1, gdf2)
                         st.write("Comparación de columnas ejecutada.")
                         if dtype_mismatch: st.write("Hay diferencias de tipos.")

                    with tab_datos:
                         st.dataframe(gdf1.head())
                
                # ... (El bloque de mapa se mantiene fuera para ser común o adaptarse)
                        
                # 4. GRÁFICO
                with tab_grafico:
                    st.markdown("#### Mapa Comparativo")
                    st.caption("Visualización de ambas capas. Usa el control de capas (arriba derecha) para alternar.")
                    
                    # Reproyectar a EPSG:4326 para Folium si es necesario
                    try:
                        if gdf1.crs and gdf1.crs.to_string() != "EPSG:4326":
                            gdf1_map = gdf1.to_crs(epsg=4326)
                        else:
                            gdf1_map = gdf1
                            
                        if gdf2.crs and gdf2.crs.to_string() != "EPSG:4326":
                            gdf2_map = gdf2.to_crs(epsg=4326)
                        else:
                            gdf2_map = gdf2
                            
                        # Crear mapa centrado en el primer archivo
                        bounds = gdf1_map.total_bounds
                        center_lat = (bounds[1] + bounds[3]) / 2
                        center_lon = (bounds[0] + bounds[2]) / 2
                        
                        m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="CartoDB positron")
                        
                        # Estilos
                        style1 = {'fillColor': '#3b82f6', 'color': '#3b82f6', 'weight': 2, 'fillOpacity': 0.4}
                        style2 = {'fillColor': '#ef4444', 'color': '#ef4444', 'weight': 2, 'fillOpacity': 0.4}
                        
                        # Añadir capas
                        # Prepare data for mapping (convert non-serializable types)
                        def prepare_for_map(gdf):
                            gdf_clean = gdf.copy()
                            for col in gdf_clean.columns:
                                if gdf_clean[col].dtype == 'object' or pd.api.types.is_datetime64_any_dtype(gdf_clean[col]):
                                    gdf_clean[col] = gdf_clean[col].astype(str)
                            return gdf_clean

                        gdf1_map = prepare_for_map(gdf1_map)
                        gdf2_map = prepare_for_map(gdf2_map)

                        folium.GeoJson(
                            gdf1_map,
                            name=f"Archivo 1: {os.path.basename(path1)}",
                            style_function=lambda x: style1,
                            tooltip=folium.GeoJsonTooltip(fields=list(gdf1_map.columns[:3]), aliases=list(gdf1_map.columns[:3])) 
                            if len(gdf1_map.columns) > 1 else None
                        ).add_to(m)
                        
                        folium.GeoJson(
                            gdf2_map,
                            name=f"Archivo 2: {os.path.basename(path2)}",
                            style_function=lambda x: style2,
                            tooltip=folium.GeoJsonTooltip(fields=list(gdf2_map.columns[:3]), aliases=list(gdf2_map.columns[:3]))
                            if len(gdf2_map.columns) > 1 else None
                        ).add_to(m)
                        
                        folium.LayerControl().add_to(m)
                        
                        st_folium(m, width="100%", height=600)
                        
                    except Exception as e:
                        st.error(f"Error al generar el mapa: {e}")
                        st.warning("Verifica que los archivos tengan un CRS válido definido.")

        # Cleanup temporal directories (optional, OS usually handles /tmp but good practice)
        # shutil.rmtree(dir1)
        # shutil.rmtree(dir2)
