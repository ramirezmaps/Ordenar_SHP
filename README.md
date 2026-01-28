# Comparador de Archivos Shapefile (.shp)

Esta aplicación construida con **Streamlit** permite comparar dos archivos Shapefile para identificar diferencias a nivel de datos y gráfico.

## Características

- **Visualización Gráfica**: Muestra ambos archivos en un mapa interactivo para comparar tolerancias espaciales y diferencias visuales.
- **Análisis de Schema**: Compara nombres de columnas y tipos de datos.
- **Resumen Estadístico**: Compara número de filas, columnas y sistema de coordenadas (CRS).
- **Exportación**: Descarga reportes de diferencias en formato CSV.

## Instrucciones de Uso

1. **Instalar dependencias**:
    Asegúrate de tener Python instalado y luego ejecuta:
   ```bash
   pip install -r requirements.txt
   ```

2. **Ejecutar la aplicación**:
   ```bash
   streamlit run app.py
   ```

3. **Subir archivos**:
   - Comprime tus archivos Shapefile (debe incluir `.shp`, `.shx`, `.dbf`, etc.) en un archivo **.ZIP**.
   - Sube un ZIP para el "Archivo 1" (Referencia).
   - Sube un ZIP para el "Archivo 2" (Comparación).
