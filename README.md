# 📊 Sistema de Análisis Financiero Societario (2008 - Actualidad)

Aplicación web interactiva desarrollada en Python y Streamlit que conecta 3 bases de datos alojadas en Google Drive para auditar y comparar históricamente el desempeño financiero de compañías ecuatorianas.

## 🔗 Arquitectura de Cruce de Datos
1. **Base Financiera (`expediente`, `anio`, `ciiu_n1`)**: Balances, estados de resultados, empleados e indicadores financieros desde 2008.
2. **Base Directorio (`expediente`)**: RUC, razón social, tipo de compañía y provincia.
3. **Base Sectorial (`anio`, `ciiu_n1`)**: Descripción de actividad económica y ratios promedio de la industria.

## 🚀 Ejecución Local
```bash
pip install -r requirements.txt
streamlit run app.py
