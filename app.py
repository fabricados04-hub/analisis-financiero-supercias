import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import gdown
import urllib.request
import os

st.set_page_config(
    page_title="Sistema de Inteligencia Financiera Societaria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #1f77b4;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 5px 5px 0px 0px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

DRIVE_FILES = {
    "financiero": "1gDdVCwN_Zpxn20cTXHlxhchZL36B9dXS",
    "directorio": "1jEBsTS6p6l4g8vxTKzkRdSSRyqDj_mpk",
    "sector":     "1ZiWa_se_gKlkBj5ceuAsCnsMkPi39n1n"
}

def descargar_archivo_drive(file_id, output_path):
    url = f"https://drive.google.com/uc?id={file_id}"
    try:
        gdown.download(url, output_path, quiet=True)
    except Exception:
        pass

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(output_path, "wb") as out:
            out.write(resp.read())

def leer_archivo_inteligente(filepath):
    with open(filepath, "rb") as f:
        cabecera = f.read(200).strip().lower()
    if cabecera.startswith(b"<!doctype html") or cabecera.startswith(b"<html"):
        raise ValueError(
            "Google Drive devolvió una página HTML en lugar del archivo de datos. "
            "Revisa que el archivo esté compartido como 'Cualquier persona con el enlace' y no requiera confirmación."
        )

    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(filepath, sep=sep, encoding=enc, low_memory=False)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue

    for engine in ["openpyxl", "xlrd"]:
        try:
            return pd.read_excel(filepath, engine=engine)
        except Exception:
            continue

    raise ValueError("No se pudo determinar el formato (CSV o Excel) del archivo descargado.")

@st.cache_data(show_spinner="Descargando y conectando las 3 bases de datos desde Google Drive...")
def cargar_y_conectar_bases():
    os.makedirs("data_cache", exist_ok=True)
    dfs = {}

    for key, file_id in DRIVE_FILES.items():
        output_path = f"data_cache/{key}.dat"
        descargar_archivo_drive(file_id, output_path)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise ValueError(f"No se pudo descargar el archivo '{key}' (ID: {file_id}).")
        df = leer_archivo_inteligente(output_path)
        df.columns = [str(c).strip().lower() for c in df.columns]
        dfs[key] = df

    df_fin = dfs["financiero"]
    df_dir = dfs["directorio"]
    df_sec = dfs["sector"]

    df_fin["expediente"] = df_fin["expediente"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df_dir["expediente"] = df_dir["expediente"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    df_fin["anio"] = pd.to_numeric(df_fin["anio"], errors="coerce").fillna(0).astype(int)
    df_sec["anio"] = pd.to_numeric(df_sec["anio"], errors="coerce").fillna(0).astype(int)

    df_fin["ciiu_n1"] = df_fin["ciiu_n1"].astype(str).str.strip().str.upper()
    df_sec["ciiu_n1"] = df_sec["ciiu_n1"].astype(str).str.strip().str.upper()

    df_fin = df_fin[df_fin["anio"] >= 2008].copy()

    cols_no_num = {"expediente", "cia_imvalores", "id_estado_financiero", "cod_segmento", "ciiu_n1", "ciiu_n6", "descripcion"}
    for col in df_fin.columns:
        if col not in cols_no_num and col != "anio":
            df_fin[col] = pd.to_numeric(df_fin[col], errors="coerce")

    for col in df_sec.columns:
        if col not in cols_no_num and col != "anio":
            df_sec[col] = pd.to_numeric(df_sec[col], errors="coerce")

    df_dir_clean = df_dir.drop_duplicates(subset=["expediente"]).copy()

    df_merged = pd.merge(df_fin, df_dir_clean, on="expediente", how="left")
    df_merged = pd.merge(df_merged, df_sec, on=["anio", "ciiu_n1"], how="left", suffixes=("", "_sector"))

    if "nombre" not in df_merged.columns:
        df_merged["nombre"] = "EXPEDIENTE " + df_merged["expediente"]
    else:
        df_merged["nombre"] = df_merged["nombre"].fillna("EXPEDIENTE " + df_merged["expediente"]).astype(str).str.strip()

    return df_merged, df_dir_clean, df_sec

def diagnosticar_estructura_bienes(row):
    rot_af = row.get("rot_activo_fijo", np.nan)
    end_af = row.get("end_activo_fijo", np.nan)
    liq = row.get("liquidez_corriente", np.nan)

    hallazgos = []
    if pd.notna(rot_af):
        if rot_af < 1.5:
            hallazgos.append("Alta intensidad en **Bienes Inmuebles / Maquinaria Pesada** (baja rotación de activo fijo; estructura intensiva en capital físico).")
        elif rot_af <= 5.0:
            hallazgos.append("Estructura **Mixta equilibrada** entre bienes de capital operativo (activos fijos) y capital de trabajo.")
        else:
            hallazgos.append("Predominio de **Bienes Corrientes / Activos Líquidos** (inventarios de rápida rotación, cartera comercial o servicios ligeros en activos fijos).")

    if pd.notna(end_af) and end_af > 1.0:
        hallazgos.append("Los activos fijos están respaldados holgadamente por el patrimonio propio (sin sobreendeudamiento estructural).")
    elif pd.notna(end_af) and end_af < 0.7:
        hallazgos.append("Parte importante de los bienes de larga duración han sido financiados con deuda externa.")

    if pd.notna(liq):
        if liq >= 1.5:
            hallazgos.append("Sólida cobertura de bienes realizables a corto plazo frente a obligaciones inmediatas.")
        elif liq < 1.0:
            hallazgos.append("Presión en activos corrientes: los bienes líquidos no alcanzan a cubrir las deudas de corto plazo.")

    return " ".join(hallazgos) if hallazgos else "Información de rotación de activos no reportada para este período."

def evaluar_rentabilidad_anual(df_emp):
    resultados = []
    for _, r in df_emp.iterrows():
        anio = int(r["anio"])
        u_neta = r.get("utilidad_neta", np.nan)
        u_ejer = r.get("utilidad_ejercicio", np.nan)
        roe = r.get("roe", np.nan)
        roa = r.get("roa", np.nan)
        m_neto = r.get("rent_neta_ventas", np.nan)
        roe_sec = r.get("roe_sector", np.nan)

        util_ref = u_neta if pd.notna(u_neta) else u_ejer

        if pd.isna(util_ref):
            estado = "⚪ Sin datos suficientes"
            detalle = "No registró estado de resultados completo."
        elif util_ref > 0:
            if pd.notna(roe) and pd.notna(roe_sec) and roe > roe_sec:
                estado = "🟢 ALTAMENTE RENTABLE (Supera al sector)"
            else:
                estado = "🟢 RENTABLE"
            detalle = (
                f"Generó utilidad neta de **${util_ref:,.2f}**. ROE: {roe*100:.2f}% | ROA: {roa*100:.2f}% | Margen Neto: {m_neto*100:.2f}%"
                if pd.notna(roe) and pd.notna(roa) and pd.notna(m_neto)
                else f"Generó utilidad positiva de **${util_ref:,.2f}**."
            )
        elif util_ref == 0:
            estado = "🟡 PUNTO DE EQUILIBRIO"
            detalle = "Ingresos cubrieron exactamente costos y gastos ($0.00 de utilidad)."
        else:
            estado = "🔴 NO RENTABLE (Pérdida)"
            detalle = f"Registró pérdida neta de **${util_ref:,.2f}**."

        resultados.append({
            "Año": anio,
            "Diagnóstico": estado,
            "Detalle Técnico": detalle
        })
    return pd.DataFrame(resultados)

try:
    df_total, df_dir, df_sec = cargar_y_conectar_bases()
except Exception as e:
    st.error(f"Error al cargar o conectar las bases desde Google Drive: {e}")
    st.info("Verifica que los 3 archivos en Google Drive tengan permiso de 'Cualquier persona con el enlace puede ver'.")
    st.stop()

st.sidebar.image("https://img.icons8.com/fluency/96/financial-analytics.png", width=70)
st.sidebar.title("Consulta Societaria")
st.sidebar.markdown("Conectado a **3 bases de datos** (`expediente` + `anio` + `ciiu_n1`).")

provincias = ["TODAS"] + sorted(df_total["provincia"].dropna().unique().tolist()) if "provincia" in df_total.columns else ["TODAS"]
prov_sel = st.sidebar.selectbox("Filtrar por Provincia (opcional):", provincias)

df_filtrado_prov = df_total if prov_sel == "TODAS" else df_total[df_total["provincia"] == prov_sel]

lista_companias = sorted(df_filtrado_prov["nombre"].dropna().unique().tolist())

st.sidebar.markdown("---")
compania_sel = st.sidebar.selectbox(
    "🔍 Buscar y seleccionar Compañía:",
    options=lista_companias,
    index=0,
    help="Escribe parte del nombre de la empresa para filtrar al instante."
)

df_emp = df_filtrado_prov[df_filtrado_prov["nombre"] == compania_sel].sort_values("anio").copy()
df_emp = df_emp.sort_values(["anio", "activos"], ascending=[True, False]).drop_duplicates(subset=["anio"])

ultimo_reg = df_emp.iloc[-1]
primer_reg = df_emp.iloc[0]
anio_max_global = df_total["anio"].max()
ultimo_anio_emp = int(ultimo_reg["anio"])

esta_activa = (anio_max_global - ultimo_anio_emp) <= 1
estado_texto = "🟢 ACTIVA (Reportes al día)" if esta_activa else f"🟠 INACTIVA / SIN REPORTES RECIENTES (Último reporte: {ultimo_anio_emp})"

st.title(f"🏢 {compania_sel}")
st.caption("Análisis Financiero Comparativo Histórico (2008 – Actualidad) y Benchmarking Sectorial")

col_info1, col_info2, col_info3, col_info4 = st.columns(4)
with col_info1:
    st.metric("Expediente / RUC", f"{ultimo_reg.get('expediente', 'N/D')} | {ultimo_reg.get('ruc', 'N/D')}")
with col_info2:
    st.metric("Estado Operativo", "ACTIVA" if esta_activa else "SIN REPORTE RECIENTE", delta=f"Último año: {ultimo_anio_emp}")
with col_info3:
    ubicacion = f"{ultimo_reg.get('provincia', 'N/D')} (Cód: {ultimo_reg.get('pro_codigo', 'N/D')})"
    st.metric("Ubicación / Tipo", ubicacion, delta=str(ultimo_reg.get("tipo", "N/D")))
with col_info4:
    st.metric("Historial Analizado", f"{int(primer_reg['anio'])} – {ultimo_anio_emp}", delta=f"{len(df_emp)} años registrados")

with st.expander("📋 Ver Ficha Societaria, Actividad Económica y Nota sobre Fecha de Constitución", expanded=True):
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"**Actividad Económica Principal (CIIU Nivel 1 - `{ultimo_reg.get('ciiu_n1', 'N/D')}`):** {ultimo_reg.get('descripcion', 'No especificada en catálogo')}")
        st.markdown(f"**Subactividad Específica (CIIU Nivel 6):** `{ultimo_reg.get('ciiu_n6', 'N/D')}` | **Segmento:** `{ultimo_reg.get('cod_segmento', 'N/D')}`")
        st.markdown(f"**Estado Situacional:** {estado_texto}")
    with c2:
        st.info(f"**Nota sobre Fecha de Constitución:** Las bases conectadas no incluyen la columna exacta de fecha de constitución notarial; sin embargo, el **primer registro financiero histórico** data del año **{int(primer_reg['anio'])}**.")

st.markdown("---")
st.subheader(f"📌 Resumen Ejecutivo ({ultimo_anio_emp})")

def calcular_delta(col):
    if len(df_emp) < 2:
        return None
    actual = df_emp.iloc[-1].get(col, np.nan)
    anterior = df_emp.iloc[-2].get(col, np.nan)
    if pd.notna(actual) and pd.notna(anterior) and anterior != 0:
        pct = ((actual - anterior) / abs(anterior)) * 100
        return f"{pct:+.1f}% vs {int(df_emp.iloc[-2]['anio'])}"
    return None

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Activos Totales", f"${ultimo_reg.get('activos', 0):,.0f}", calcular_delta("activos"))
k2.metric("Patrimonio", f"${ultimo_reg.get('patrimonio', 0):,.0f}", calcular_delta("patrimonio"))
k3.metric("Ingresos por Ventas", f"${ultimo_reg.get('ingresos_ventas', 0):,.0f}", calcular_delta("ingresos_ventas"))
k4.metric("Utilidad del Ejercicio", f"${ultimo_reg.get('utilidad_ejercicio', 0):,.0f}", calcular_delta("utilidad_ejercicio"))
k5.metric("Impuesto a la Renta", f"${ultimo_reg.get('impuesto_renta', 0):,.0f}", calcular_delta("impuesto_renta"))
k6.metric("Utilidad Neta", f"${ultimo_reg.get('utilidad_neta', 0):,.0f}", calcular_delta("utilidad_neta"))

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 1. Comparativo Histórico (Tabla Completa)",
    "📈 2. Evolución Gráfica y Empleo",
    "💰 3. Diagnóstico de Rentabilidad y Bienes",
    "⚖️ 4. Comparativo vs. Sector (CIIU)"
])

with tab1:
    st.markdown("### Evolución Anual de Rubros Principales (2008 en adelante)")

    cols_tabla = [
        "anio", "activos", "patrimonio", "ingresos_ventas", "ingresos_totales",
        "utilidad_an_imp", "impuesto_renta", "utilidad_ejercicio", "utilidad_neta",
        "n_empleados", "deuda_total", "total_gastos"
    ]
    cols_existentes = [c for c in cols_tabla if c in df_emp.columns]

    df_tabla = df_emp[cols_existentes].copy()
    nombres_amigables = {
        "anio": "Año",
        "activos": "Activos ($)",
        "patrimonio": "Patrimonio ($)",
        "ingresos_ventas": "Ingresos Ventas ($)",
        "ingresos_totales": "Ingresos Totales ($)",
        "utilidad_an_imp": "Utilidad Antes Imp. ($)",
        "impuesto_renta": "Impuesto Renta ($)",
        "utilidad_ejercicio": "Utilidad Ejercicio ($)",
        "utilidad_neta": "Utilidad Neta ($)",
        "n_empleados": "Trabajadores",
        "deuda_total": "Deuda Total ($)",
        "total_gastos": "Total Gastos ($)"
    }
    df_tabla.rename(columns=nombres_amigables, inplace=True)

    formato_dict = {col: "${:,.2f}" for col in df_tabla.columns if "($)" in col}
    if "Trabajadores" in df_tabla.columns:
        formato_dict["Trabajadores"] = "{:,.0f}"

    st.dataframe(
        df_tabla.style.format(formato_dict, na_rep="N/D"),
        use_container_width=True,
        hide_index=True
    )

    csv_export = df_tabla.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar Tabla Comparativa en CSV",
        data=csv_export,
        file_name=f"comparativo_{ultimo_reg.get('expediente', 'empresa')}.csv",
        mime="text/csv"
    )

with tab2:
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("#### Activos, Patrimonio e Ingresos por Ventas")
        fig_bal = go.Figure()
        for col, nombre, color in [
            ("activos", "Activos Totales", "#1f77b4"),
            ("patrimonio", "Patrimonio", "#2ca02c"),
            ("ingresos_ventas", "Ingresos por Ventas", "#ff7f0e")
        ]:
            if col in df_emp.columns:
                fig_bal.add_trace(go.Scatter(
                    x=df_emp["anio"], y=df_emp[col],
                    mode="lines+markers", name=nombre, line=dict(width=3, color=color)
                ))
        fig_bal.update_layout(hovermode="x unified", xaxis_title="Año", yaxis_title="Dólares (USD)", height=400)
        st.plotly_chart(fig_bal, use_container_width=True)

    with g2:
        st.markdown("#### Utilidad del Ejercicio, Impuesto a la Renta y Utilidad Neta")
        fig_util = go.Figure()
        for col, nombre, color in [
            ("utilidad_ejercicio", "Utilidad del Ejercicio", "#636efa"),
            ("impuesto_renta", "Impuesto a la Renta", "#ef553b"),
            ("utilidad_neta", "Utilidad Neta", "#00cc96")
        ]:
            if col in df_emp.columns:
                fig_util.add_trace(go.Bar(
                    x=df_emp["anio"], y=df_emp[col],
                    name=nombre, marker_color=color
                ))
        fig_util.update_layout(barmode="group", hovermode="x unified", xaxis_title="Año", yaxis_title="Dólares (USD)", height=400)
        st.plotly_chart(fig_util, use_container_width=True)

    st.markdown("#### Evolución del Número de Trabajadores por Año")
    if "n_empleados" in df_emp.columns:
        fig_emp = px.area(
            df_emp, x="anio", y="n_empleados",
            markers=True, labels={"anio": "Año", "n_empleados": "Número de Trabajadores"},
            color_discrete_sequence=["#9467bd"]
        )
        fig_emp.update_layout(height=320)
        st.plotly_chart(fig_emp, use_container_width=True)

with tab3:
    col_r1, col_r2 = st.columns([3, 2])

    with col_r1:
        st.markdown("### Veredicto de Rentabilidad Año por Año")
        df_diag_rent = evaluar_rentabilidad_anual(df_emp)
        st.dataframe(df_diag_rent, use_container_width=True, hide_index=True)

    with col_r2:
        st.markdown(f"### Estructura de Bienes y Solvencia ({ultimo_anio_emp})")
        diag_bienes = diagnosticar_estructura_bienes(ultimo_reg)
        st.success(diag_bienes)

        st.markdown("**Indicadores de Composición Patrimonial y Activos:**")
        indicadores_bienes = {
            "Rotación de Activo Fijo": ultimo_reg.get("rot_activo_fijo", np.nan),
            "Endeudamiento del Activo Fijo": ultimo_reg.get("end_activo_fijo", np.nan),
            "Liquidez Corriente": ultimo_reg.get("liquidez_corriente", np.nan),
            "Prueba Ácida": ultimo_reg.get("prueba_acida", np.nan),
            "Fortaleza Patrimonial": ultimo_reg.get("fortaleza_patrimonial", np.nan),
            "Endeudamiento del Activo": ultimo_reg.get("end_activo", np.nan),
            "Apalancamiento": ultimo_reg.get("apalancamiento", np.nan)
        }
        df_ind_bienes = pd.DataFrame([
            {"Indicador": k, "Valor": f"{v:.2f}" if pd.notna(v) else "N/D"}
            for k, v in indicadores_bienes.items()
        ])
        st.table(df_ind_bienes)

with tab4:
    st.markdown(f"### Desempeño de **{compania_sel}** frente al Sector `{ultimo_reg.get('ciiu_n1', 'N/D')}`")
    st.caption(f"Sector: {ultimo_reg.get('descripcion', 'No especificado')}")

    ratios_comparar = {
        "roe": "ROE (Rentabilidad sobre Patrimonio)",
        "roa": "ROA (Rentabilidad sobre Activos)",
        "rent_neta_ventas": "Margen Neto de Ventas",
        "margen_operacional": "Margen Operacional",
        "liquidez_corriente": "Liquidez Corriente",
        "end_activo": "Endeudamiento del Activo"
    }

    ratio_sel = st.selectbox(
        "Selecciona el indicador financiero para comparar contra el promedio de su industria:",
        options=list(ratios_comparar.keys()),
        format_func=lambda x: ratios_comparar[x]
    )

    col_sec = f"{ratio_sel}_sector"
    if ratio_sel in df_emp.columns and col_sec in df_emp.columns:
        fig_bench = go.Figure()
        fig_bench.add_trace(go.Scatter(
            x=df_emp["anio"], y=df_emp[ratio_sel],
            mode="lines+markers", name=f"{compania_sel}",
            line=dict(color="#1f77b4", width=3)
