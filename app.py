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
                
                # --- PESTAÑAS DE ANÁLISIS ---
                tab_resumen, tab_estructura, tab_datos, tab_grafico = st.tabs([
                    "📊 Resumen General", 
                    "🏗️ Estructura & Schema", 
                    "📋 Datos & Atributos", 
                    "🌍 Visualización Gráfica"
                ])
                
                # 1. RESUMEN
                with tab_resumen:
                    st.markdown("#### Métricas Principales")
                    m1, m2, m3, m4 = st.columns(4)
                    
                    m1.metric("Filas Archivo 1", len(gdf1))
                    m2.metric("Filas Archivo 2", len(gdf2), delta=len(gdf2)-len(gdf1))
                    m3.metric("Columnas Archivo 1", len(gdf1.columns))
                    m4.metric("Columnas Archivo 2", len(gdf2.columns), delta=len(gdf2.columns)-len(gdf1.columns))
                    
                    st.divider()
                    st.markdown("#### Sistemas de Coordenadas (CRS)")
                    c1, c2 = st.columns(2)
                    crs1_desc = str(gdf1.crs) if gdf1.crs else "Sin Definir"
                    crs2_desc = str(gdf2.crs) if gdf2.crs else "Sin Definir"
                    
                    c1.info(f"**Archivo 1:** {crs1_desc}")
                    if gdf1.crs == gdf2.crs:
                        c2.success(f"**Archivo 2:** {crs2_desc} (Coinciden)")
                    else:
                        c2.error(f"**Archivo 2:** {crs2_desc} (DIFERENTES)")

                # 2. ESTRUCTURA
                with tab_estructura:
                    common, u1, u2, dtype_mismatch = compare_schemas(gdf1, gdf2)
                    
                    col_struct_1, col_struct_2 = st.columns(2)
                    
                    with col_struct_1:
                        st.markdown("##### Columnas exclusivas en Archivo 1")
                        if u1:
                            st.dataframe(pd.DataFrame(list(u1), columns=["Nombre Columna"]), use_container_width=True)
                        else:
                            st.info("No hay columnas únicas en el Archivo 1.")

                    with col_struct_2:
                        st.markdown("##### Columnas exclusivas en Archivo 2")
                        if u2:
                            st.dataframe(pd.DataFrame(list(u2), columns=["Nombre Columna"]), use_container_width=True)
                        else:
                            st.info("No hay columnas únicas en el Archivo 2.")
                    
                    st.markdown("##### Diferencias de Tipo de Dato (en columnas comunes)")
                    if dtype_mismatch:
                        df_mismatch = pd.DataFrame(dtype_mismatch)
                        st.dataframe(df_mismatch, use_container_width=True)
                        
                        csv_mismatch = df_mismatch.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Diferencias de Tipos (CSV)",
                            data=csv_mismatch,
                            file_name="diferencias_tipos.csv",
                            mime="text/csv",
                        )
                    else:
                        st.success("Todas las columnas comunes tienen el mismo tipo de dato.")
                    
                    # Diferencias de columnas resumen
                    if u1 or u2:
                        diff_data = {
                            "Tipo": ["Columna Única en Archivo 1"] * len(u1) + ["Columna Única en Archivo 2"] * len(u2),
                            "Columna": list(u1) + list(u2)
                        }
                        if diff_data["Columna"]:
                            df_diff_cols = pd.DataFrame(diff_data)
                            csv_diff_cols = df_diff_cols.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Descargar Diferencias de Columnas (CSV)",
                                data=csv_diff_cols,
                                file_name="diferencias_columnas.csv",
                                mime="text/csv"
                            )

                # 3. DATOS
                with tab_datos:
                    st.markdown("#### Vista Previa de Datos")
                    st.markdown("**Archivo 1 (Primeras 5 filas):**")
                    st.dataframe(gdf1.head(), use_container_width=True)
                    
                    st.markdown("**Archivo 2 (Primeras 5 filas):**")
                    st.dataframe(gdf2.head(), use_container_width=True)
                    
                    # Comparación básica de geometrías totals (Area/Longitud) si aplica
                    if 'geometry' in gdf1.columns and 'geometry' in gdf2.columns:
                        st.divider()
                        st.markdown("#### Análisis Geométrico Global")
                        if gdf1.geom_type.unique()[0] in ['Polygon', 'MultiPolygon']:
                            total_area_1 = gdf1.geometry.area.sum()
                            total_area_2 = gdf2.geometry.area.sum()
                            st.write(f"Área total Archivo 1: {total_area_1:,.2f}")
                            st.write(f"Área total Archivo 2: {total_area_2:,.2f}")
                        
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
