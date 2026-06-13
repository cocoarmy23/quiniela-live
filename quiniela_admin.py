import streamlit as st
import pandas as pd
import requests
import unicodedata
from supabase import create_client, Client
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# ============================================================
# CONFIGURACIÓN
# ============================================================
URL_SUPABASE = "https://mznajuaorvnuakndinwo.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im16bmFqdWFvcnZudWFrbmRpbndvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzMDE0NDksImV4cCI6MjA5Njg3NzQ0OX0.gZjhUeXxLNjTmdJP7fzSxPHZHLd7H-fzMNYpfN_qFC8"

supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Ligas ESPN disponibles — incluye mundial
LIGAS_ESPN = {
    "fifa.world":  "Copa del Mundo 2026",
    "mex.1":       "Liga MX",
    "mex.2":       "Liga de Expansión MX",
    "eng.1":       "Premier League",
    "esp.1":       "LaLiga",
    "ita.1":       "Serie A",
    "fra.1":       "Ligue 1",
    "ger.1":       "Bundesliga",
    "ned.1":       "Eredivisie",
    "por.1":       "Primeira Liga",
    "bra.1":       "Serie A (Brasil)",
    "arg.1":       "Liga Profesional (Arg)",
    "bel.1":       "Pro League (Bélgica)",
    "usa.1":       "MLS",
    "concacaf.nations.league": "Nations League CONCACAF",
    "conmebol.world":          "Eliminatorias CONMEBOL",
}

st.set_page_config(page_title="Quiniela Admin", layout="wide", page_icon="⚽")

# ============================================================
# ESTILOS
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.partido-card {
    background: #11172a; border: 1px solid #1e2640; border-radius: 10px;
    padding: 14px 20px; margin-bottom: 10px;
}
.partido-card.confirmado { border-left: 3px solid #22c55e; }
.partido-card.pendiente  { border-left: 3px solid #f59e0b; }
.casilla-num { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #4b5680; letter-spacing: 1px; }
.equipo-name { font-weight: 600; font-size: 15px; color: #e2e8f0; }
.liga-tag { font-size: 10px; background: #1e2640; color: #6b7db3; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; }
.score-chip { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 700; color: #00ff87;
    background: #061a0f; border: 1px solid #00ff8740; border-radius: 8px; padding: 4px 16px; min-width: 90px; text-align: center; }
.score-pending { color: #334155; }
.estado-ft   { color: #22c55e; font-size: 11px; font-weight: 600; }
.estado-live { color: #ef4444; font-size: 11px; font-weight: 600; }
.estado-ns   { color: #64748b; font-size: 11px; }
.metric-box  { background: #11172a; border: 1px solid #1e2640; border-radius: 10px; padding: 16px; text-align: center; }
.metric-num  { font-size: 32px; font-weight: 700; color: #e2e8f0; }
.metric-lbl  { font-size: 11px; color: #4b5680; text-transform: uppercase; letter-spacing: 1px; }
.pred-L { background:#1e3a5f; color:#60a5fa; border-radius:4px; padding:2px 7px; font-weight:700; font-size:13px; }
.pred-E { background:#2d2a1e; color:#fbbf24; border-radius:4px; padding:2px 7px; font-weight:700; font-size:13px; }
.pred-V { background:#1e3528; color:#4ade80; border-radius:4px; padding:2px 7px; font-weight:700; font-size:13px; }
.acierto-bar-bg   { background: #1e2640; border-radius: 4px; height: 8px; width: 100%; }
.acierto-bar-fill { background: #22c55e; border-radius: 4px; height: 8px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# UTILS
# ============================================================
def normalizar(texto: str) -> str:
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def hora_utc_a_mx(hora_utc_str: str) -> str:
    try:
        dt = datetime.strptime(hora_utc_str[:16], "%Y-%m-%dT%H:%M")
        dt_mx = dt - timedelta(hours=6)
        return dt_mx.strftime("%H:%M")
    except Exception:
        return hora_utc_str[:5]

# ============================================================
# ESPN – FUNCIONES
# ============================================================
@st.cache_data(ttl=60)
def get_espn_scoreboard(slug: str, fecha: str = "") -> list:
    url = f"{ESPN_BASE}/{slug}/scoreboard?limit=100"
    if fecha:
        url += f"&dates={fecha}"
    try:
        data = requests.get(url, timeout=10).json()
        return data.get("events", [])
    except Exception:
        return []

@st.cache_data(ttl=55)
def get_espn_scores(slug: str) -> dict:
    hoy  = datetime.now().strftime("%Y%m%d")
    ayer = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    todos = []
    for fecha in [hoy, ayer]:
        todos += get_espn_scoreboard(slug, fecha)

    result = {}
    for event in todos:
        eid  = str(event.get("id", ""))
        if eid in result:
            continue
        comp  = event.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        home  = next((t for t in teams if t.get("homeAway") == "home"), {})
        away  = next((t for t in teams if t.get("homeAway") == "away"), {})
        stype     = event.get("status", {}).get("type", {})
        state     = stype.get("state", "pre")
        detail    = event.get("status", {}).get("displayClock", "")
        completed = stype.get("completed", False)
        result[eid] = {
            "g_home":    home.get("score"),
            "g_away":    away.get("score"),
            "state":     state,
            "detail":    detail,
            "completed": completed,
            "logo_home": home.get("team", {}).get("logo", ""),
            "logo_away": away.get("team", {}).get("logo", ""),
        }
    return result

def buscar_en_espn(slug: str, fecha: str, filtro: str = "") -> list:
    eventos = get_espn_scoreboard(slug, fecha)
    partidos = []
    for e in eventos:
        comp  = e.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        home  = next((t for t in teams if t.get("homeAway") == "home"), {})
        away  = next((t for t in teams if t.get("homeAway") == "away"), {})
        home_name = home.get("team", {}).get("displayName", "")
        away_name = away.get("team", {}).get("displayName", "")

        if filtro:
            q = normalizar(filtro)
            if q not in normalizar(home_name) and q not in normalizar(away_name):
                continue

        partidos.append({
            "espn_id":    str(e["id"]),
            "league_slug": slug,
            "home_name":  home_name,
            "away_name":  away_name,
            "hora_mx":    hora_utc_a_mx(e.get("date", "")),
            "logo_home":  home.get("team", {}).get("logo", ""),
            "logo_away":  away.get("team", {}).get("logo", ""),
        })
    return partidos

def calcular_resultado(g_h, g_a):
    if g_h is None or g_a is None:
        return None
    if g_h > g_a: return "L"
    if g_a > g_h: return "V"
    return "E"

# ============================================================
# SUPABASE – HELPERS
# ============================================================
def _check_conexion() -> bool:
    try:
        supabase.table("jornadas").select("id").limit(1).execute()
        return True
    except Exception as e:
        st.error(f"⚠️ Sin conexión a Supabase: `{str(e)[:150]}`")
        return False

def cargar_jornadas():
    try:
        res = supabase.table("jornadas").select("*").order("id", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.error(f"Error cargando jornadas: `{str(e)[:150]}`")
        return []

def cargar_partidos(jornada_id: int):
    try:
        res = supabase.table("partidos_jornada").select("*").eq("jornada_id", jornada_id).order("casilla").execute()
        return res.data or []
    except Exception as e:
        st.error(f"Error cargando partidos: `{str(e)[:150]}`")
        return []

def cargar_quinielas(jornada_id: int):
    try:
        res = supabase.table("quinielas").select("*").eq("jornada_id", jornada_id).order("numero_carton").order("casilla").execute()
        return res.data or []
    except Exception as e:
        return []

def actualizar_resultado_db(partido_id: int, goles_l, goles_v, estado: str, resultado):
    try:
        supabase.table("partidos_jornada").update({
            "goles_local":  goles_l,
            "goles_visita": goles_v,
            "estado":       estado,
            "resultado":    resultado,
        }).eq("id", partido_id).execute()
    except Exception as e:
        st.warning(f"No se pudo actualizar partido {partido_id}: `{str(e)[:100]}`")

# ============================================================
# PARSEAR CSV
# ============================================================
def parsear_csv(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file, sep=";", header=0)
    cols = list(df.columns)
    df.rename(columns={cols[0]: "casilla"}, inplace=True)
    base_cols = ["casilla", "local", "visita", "liga", "dia", "hora"]
    carton_cols = [c for c in df.columns if c not in base_cols]
    rename_map = {c: f"c{i}" for i, c in enumerate(carton_cols, 1)}
    df.rename(columns=rename_map, inplace=True)
    df = df.dropna(subset=["casilla", "local", "visita"])
    df["casilla"] = df["casilla"].astype(int)
    return df

# ============================================================
# VERIFICAR CONEXIÓN
# ============================================================
if not _check_conexion():
    st.stop()

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3 = st.tabs(["📂 Cargar Jornada", "🔍 Confirmar Partidos", "📡 Monitor en Vivo"])

# ============================================================
# TAB 1 – CARGAR JORNADA
# ============================================================
with tab1:
    st.markdown("### Subir nueva quiniela")
    col_up, col_hist = st.columns([1, 1], gap="large")

    with col_up:
        nombre_jornada = st.text_input("Nombre de la jornada", placeholder="Ej: Jornada 1 – Copa del Mundo")
        archivo = st.file_uploader("Sube tu CSV de quiniela", type=["csv"])

        if archivo and nombre_jornada:
            try:
                df_raw = parsear_csv(archivo)
                carton_cols = [c for c in df_raw.columns if c.startswith("c")]
                st.success(f"✅ CSV leído: {len(df_raw)} partidos, {len(carton_cols)} cartones")
                st.dataframe(df_raw[["casilla","local","visita","liga","dia"]].head(25), use_container_width=True)

                if st.button("💾 Guardar jornada en Supabase", type="primary"):
                    with st.spinner("Guardando..."):
                        res_j = supabase.table("jornadas").insert({"nombre": nombre_jornada, "activa": True}).execute()
                        jid = res_j.data[0]["id"]

                        partidos_insert = []
                        for _, row in df_raw.iterrows():
                            partidos_insert.append({
                                "jornada_id":    jid,
                                "casilla":       int(row["casilla"]),
                                "local_nombre":  str(row["local"]).strip(),
                                "visita_nombre": str(row["visita"]).strip(),
                                "liga":          str(row.get("liga","")).strip(),
                                "dia":           str(row.get("dia","")).strip(),
                                "hora":          str(row.get("hora","")).strip(),
                            })
                        supabase.table("partidos_jornada").insert(partidos_insert).execute()

                        quinielas_insert = []
                        for _, row in df_raw.iterrows():
                            for ci, col in enumerate(carton_cols, 1):
                                val = str(row.get(col, "")).strip().upper()
                                if val in ["L", "E", "V"]:
                                    quinielas_insert.append({
                                        "jornada_id":    jid,
                                        "numero_carton": ci,
                                        "casilla":       int(row["casilla"]),
                                        "prediccion":    val,
                                    })
                        if quinielas_insert:
                            supabase.table("quinielas").insert(quinielas_insert).execute()

                        st.success(f"🎉 Jornada '{nombre_jornada}' guardada — ID {jid}")
                        st.info("Ahora ve a **Confirmar Partidos** para enlazar cada casilla con ESPN.")

            except Exception as e:
                st.error(f"Error al leer el CSV: {e}")

    with col_hist:
        st.markdown("#### Jornadas guardadas")
        jornadas = cargar_jornadas()
        if jornadas:
            for j in jornadas:
                estado = "🟢 Activa" if j["activa"] else "⚫ Cerrada"
                st.markdown(f"""
                <div class="partido-card confirmado" style="padding:12px 16px;">
                    <div class="casilla-num">ID {j['id']} · {j['fecha_creacion'][:10]}</div>
                    <div class="equipo-name" style="margin:4px 0;">{j['nombre']}</div>
                    <span style="font-size:12px;">{estado}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Aún no hay jornadas guardadas.")

# ============================================================
# TAB 2 – CONFIRMAR PARTIDOS con ESPN
# ============================================================
with tab2:
    st.markdown("### Confirmar partidos — ESPN")
    jornadas = cargar_jornadas()
    if not jornadas:
        st.warning("Primero carga una jornada.")
        st.stop()

    opts = {j["nombre"]: j["id"] for j in jornadas}
    sel  = st.selectbox("Selecciona jornada", list(opts.keys()))
    jid_sel = opts[sel]

    partidos = cargar_partidos(jid_sel)
    confirmados = sum(1 for p in partidos if p.get("fixture_id"))
    total = len(partidos)

    col_a, col_b, col_c = st.columns(3)
    col_a.markdown(f'<div class="metric-box"><div class="metric-num">{total}</div><div class="metric-lbl">Partidos</div></div>', unsafe_allow_html=True)
    col_b.markdown(f'<div class="metric-box"><div class="metric-num" style="color:#22c55e">{confirmados}</div><div class="metric-lbl">Confirmados</div></div>', unsafe_allow_html=True)
    col_c.markdown(f'<div class="metric-box"><div class="metric-num" style="color:#f59e0b">{total-confirmados}</div><div class="metric-lbl">Pendientes</div></div>', unsafe_allow_html=True)

    st.divider()

    st.markdown("#### 🔍 Buscador ESPN")
    col_liga, col_fecha, col_filtro = st.columns([1.5, 1, 1.5])
    liga_slug = col_liga.selectbox("Liga", list(LIGAS_ESPN.keys()), format_func=lambda x: LIGAS_ESPN[x], index=0)
    fecha_sel = col_fecha.date_input("Fecha", datetime.now())
    filtro_eq = col_filtro.text_input("Filtrar equipo (opcional)", placeholder="ej: Mexico")

    if st.button("🔎 Buscar en ESPN", type="primary"):
        fecha_str = fecha_sel.strftime("%Y%m%d")
        get_espn_scoreboard.clear()
        resultados = buscar_en_espn(liga_slug, fecha_str, filtro_eq)
        st.session_state["espn_resultados"] = resultados
        st.session_state["espn_slug"] = liga_slug

    if st.session_state.get("espn_resultados"):
        res = st.session_state["espn_resultados"]
        slug_usado = st.session_state.get("espn_slug", "")

        if not res:
            st.warning("No se encontraron partidos. Prueba otra liga o fecha.")
        else:
            st.success(f"{len(res)} partidos encontrados en ESPN")
            opciones_label = [f"[{p['espn_id']}]  {p['home_name']} vs {p['away_name']}  🕒 {p['hora_mx']}" for p in res]
            partido_elegido_label = st.selectbox("Partido encontrado", opciones_label)
            idx_elegido = opciones_label.index(partido_elegido_label)
            partido_elegido = res[idx_elegido]

            casillas_pendientes = [p for p in partidos if not p.get("fixture_id")]
            if casillas_pendientes:
                casilla_opts = {f"Casilla {p['casilla']} — {p['local_nombre']} vs {p['visita_nombre']}": p for p in casillas_pendientes}
                casilla_label = st.selectbox("Asignar a casilla", list(casilla_opts.keys()))
                casilla_dest = casilla_opts[casilla_label]

                col_prev, col_btn = st.columns([3, 1])
                col_prev.info(f"**ESPN:** {partido_elegido['home_name']} vs {partido_elegido['away_name']} | ID `{partido_elegido['espn_id']}`")
                if col_btn.button("✅ Confirmar asignación", type="primary"):
                    supabase.table("partidos_jornada").update({
                        "fixture_id":  partido_elegido["espn_id"],
                        "liga":        LIGAS_ESPN.get(slug_usado, slug_usado),
                        "league_slug": slug_usado,
                        "hora":        partido_elegido["hora_mx"],
                    }).eq("id", casilla_dest["id"]).execute()
                    st.success(f"Casilla {casilla_dest['casilla']} vinculada ✅")
                    st.rerun()
            else:
                st.success("🎉 ¡Todos los partidos ya están confirmados!")

    st.divider()
    st.markdown("#### Resumen de casillas")
    for p in partidos:
        ya_conf = bool(p.get("fixture_id"))
        card_class = "confirmado" if ya_conf else "pendiente"
        st.markdown(f"""
        <div class="partido-card {card_class}">
            <span class="casilla-num">CASILLA {p['casilla']}</span>
            &nbsp;<span class="liga-tag">{p.get('liga','Sin liga')}</span>
            <div style="margin-top:6px;" class="equipo-name">{p['local_nombre']} vs {p['visita_nombre']}</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# TAB 3 – MONITOR EN VIVO (SEPARADO EN QUINIELA Y REVANCHA)
# ============================================================
with tab3:
    st.markdown("### Monitor en vivo")

    jornadas = cargar_jornadas()
    if not jornadas:
        st.warning("No hay jornadas cargadas.")
        st.stop()

    opts3 = {j["nombre"]: j["id"] for j in jornadas}
    sel3  = st.selectbox("Jornada", list(opts3.keys()), key="sel_monitor")
    jid_mon = opts3[sel3]

    col_btn1, col_btn2 = st.columns([1, 2])
    btn_refresh  = col_btn1.button("🔄 Actualizar ahora")
    auto_refresh = col_btn2.toggle("⏱ Auto cada 60s", value=False)

    partidos_mon  = cargar_partidos(jid_mon)
    quinielas_mon = cargar_quinielas(jid_mon)

    if btn_refresh or auto_refresh:
        slugs_mon = set(p.get("league_slug","") for p in partidos_mon if p.get("league_slug") and p.get("fixture_id"))
        scores_vivo = {}
        for slug in slugs_mon:
            get_espn_scores.clear()
            scores_vivo[slug] = get_espn_scores(slug)

        for p in partidos_mon:
            if not p.get("fixture_id") or not p.get("league_slug"):
                continue
            info = scores_vivo.get(p["league_slug"], {}).get(str(p["fixture_id"]), {})
            if not info:
                continue
            g_h   = info.get("g_home")
            g_a   = info.get("g_away")
            state = info.get("state", "NS")
            completed = info.get("completed", False)
            estado = "FT" if completed or state == "post" else ("LIVE" if state == "in" else "NS")
            resultado = calcular_resultado(g_h, g_a) if estado == "FT" else None
            actualizar_resultado_db(p["id"], g_h, g_a, estado, resultado)

        st.toast("Resultados actualizados ✅")
        partidos_mon = cargar_partidos(jid_mon)

    if not partidos_mon:
        st.info("Esta jornada no tiene partidos.")
        st.stop()

    num_cartones = max((q["numero_carton"] for q in quinielas_mon), default=0)
    preds_map = {(q["casilla"], q["numero_carton"]): q["prediccion"] for q in quinielas_mon}
    carton_ids = list(range(1, num_cartones + 1))

    # ── Separar Partidos lógicamente ──
    partidos_normal   = [p for p in partidos_mon if p["casilla"] <= 14]
    partidos_revancha = [p for p in partidos_mon if 15 <= p["casilla"] <= 21]

    # ── Calcular aciertos por sección por cartón ──
    aciertos_normal = {}
    aciertos_revancha = {}

    for ci in carton_ids:
        preds = {q["casilla"]: q["prediccion"] for q in quinielas_mon if q["numero_carton"] == ci}
        
        # Quiniela Normal (1-14)
        ac_n = sum(1 for p in partidos_normal if p.get("resultado") and preds.get(p["casilla"]) == p["resultado"])
        ter_n = sum(1 for p in partidos_normal if p.get("resultado"))
        aciertos_normal[ci] = (ac_n, ter_n)
        
        # Revancha (15-21)
        ac_r = sum(1 for p in partidos_revancha if p.get("resultado") and preds.get(p["casilla"]) == p["resultado"])
        ter_r = sum(1 for p in partidos_revancha if p.get("resultado"))
        aciertos_revancha[ci] = (ac_r, ter_r)

    # Encabezado HTML
    thead_ths = "".join([f'<th class="th-carton">C{ci}</th>' for ci in carton_ids])

    # Función interna auxiliar para renderizar los bloques de filas
    def construir_bloque_filas(lista_partidos):
        html_bloque = ""
        for p in lista_partidos:
            g_h = p.get("goles_local")
            g_a = p.get("goles_visita")
            estado   = p.get("estado", "NS")
            resultado = p.get("resultado")

            if g_h is not None and g_a is not None:
                marcador = f"{g_h}·{g_a}"
                marc_html = f'<span class="marc-ft">{marcador}</span>' if estado == "FT" else f'<span class="marc-live">{marcador}</span>'
            else:
                marc_html = '<span class="marc-ns">·</span>'

            if estado == "FT":
                est_badge = '<span class="badge-ft">FT</span>'
            elif estado == "LIVE":
                est_badge = '<span class="badge-live">●</span>'
            else:
                hora = p.get("hora","") or ""
                est_badge = f'<span class="badge-ns">{hora[:5]}</span>'

            loc_abbr = p["local_nombre"][:8].upper()
            vis_abbr = p["visita_nombre"][:8].upper()

            pred_cells = ""
            for ci in carton_ids:
                pred = preds_map.get((p["casilla"], ci), "")
                if resultado and pred == resultado:
                    css = "cell-ok"
                elif resultado and pred != resultado:
                    css = "cell-fail"
                elif pred == "L": css = "cell-L"
                elif pred == "E": css = "cell-E"
                elif pred == "V": css = "cell-V"
                else: css = "cell-empty"
                pred_cells += f'<td class="pred-cell {css}">{pred}</td>'

            html_bloque += f"""
            <tr>
                <td class="td-casilla">Q{p['casilla']}</td>
                <td class="td-equipos">
                    <div class="eq-local">{loc_abbr}</div>
                    <div class="eq-visita">{vis_abbr}</div>
                </td>
                <td class="td-marc">{marc_html}{est_badge}</td>
                {pred_cells}
            </tr>"""
        return html_bloque

    # Renderizar Filas Normales
    rows_normal_html = construir_bloque_filas(partidos_normal)

    # Fila Totales Normales
    totales_normal_cells = ""
    for ci in carton_ids:
        ac, ter = aciertos_normal.get(ci, (0, 0))
        totales_normal_cells += f'<td class="td-total style-n">{ac}/{ter}</td>'

    # Renderizar Filas Revancha
    rows_revancha_html = construir_bloque_filas(partidos_revancha)

    # Fila Totales Revancha
    totales_revancha_cells = ""
    for ci in carton_ids:
        ac, ter = aciertos_revancha.get(ci, (0, 0))
        totales_revancha_cells += f'<td class="td-total style-r">{ac}/{ter}</td>'

    # Juntar todo el HTML con la separación y estilos visuales
    table_html = f"""
    <style>
    .qtable {{
        width: 100%; border-collapse: collapse;
        font-family: 'Inter', sans-serif; font-size: 13px;
        background: #0d1117; border-radius: 12px; overflow: hidden;
    }}
    .qtable th, .qtable td {{ padding: 7px 6px; text-align: center; border-bottom: 1px solid #1e2640; }}
    .th-casilla  {{ background:#111827; color:#4b5680; font-size:11px; width:40px; }}
    .th-equipos  {{ background:#111827; color:#4b5680; font-size:11px; text-align:left; width:110px; }}
    .th-marc     {{ background:#111827; color:#4b5680; font-size:11px; width:70px; }}
    .th-carton   {{ background:#111827; color:#94a3b8; font-size:12px; font-weight:700; min-width:38px; }}
    
    .td-casilla  {{ color:#fbbf24; font-weight:700; font-size:12px; }}
    .td-equipos  {{ text-align:left; }}
    .eq-local    {{ color:#e2e8f0; font-weight:600; font-size:11px; }}
    .eq-visita   {{ color:#94a3b8; font-size:10px; margin-top:2px; }}
    
    .marc-ft     {{ color:#22c55e; font-weight:700; font-size:14px; }}
    .marc-live   {{ color:#ef4444; font-weight:700; font-size:14px; }}
    .marc-ns     {{ color:#334155; font-size:14px; }}
    .badge-ft    {{ display:block; font-size:9px; color:#22c55e; }}
    .badge-live  {{ display:block; font-size:9px; color:#ef4444; animation: blink 1s infinite; }}
    .badge-ns    {{ display:block; font-size:9px; color:#475569; }}
    @keyframes blink {{ 50%{{ opacity:0.3; }} }}
    
    .pred-cell   {{ font-weight:700; font-size:13px; border-radius:4px; }}
    .cell-ok     {{ background:#14532d; color:#4ade80; }}
    .cell-fail   {{ background:#1a1a1a; color:#334155; }}
    .cell-L      {{ background:#1e3a5f; color:#60a5fa; }}
    .cell-E      {{ background:#3d2e00; color:#fbbf24; }}
    .cell-V      {{ background:#14291e; color:#4ade80; }}
    .cell-empty  {{ color:#334155; }}
    
    /* Separadores y Subtotales */
    .row-revancha-header {{
        background: #1e1b4b !important; color: #c7d2fe !important;
        font-weight: 700; letter-spacing: 2px; font-size: 11px; text-align: left !important;
        padding: 10px 12px !important;
    }}
    .td-total    {{ font-weight:700; font-size:12px; background:#111827; }}
    .style-n     {{ color: #38bdf8; }}
    .style-r     {{ color: #a78bfa; }}
    .tr-total td {{ border-top: 2px solid #1e2640; border-bottom: 2px solid #2d3748; }}
    </style>
    
    <table class="qtable">
      <thead>
        <tr>
          <th class="th-casilla">Q</th>
          <th class="th-equipos">PARTIDO</th>
          <th class="th-marc">MARC</th>
          {thead_ths}
        </tr>
      </thead>
      <tbody>
        {rows_normal_html}
        <tr class="tr-total">
          <td colspan="3" class="td-total" style="color:#38bdf8; text-align:right; font-size:11px;">SUMA Q1-Q14 →</td>
          {totales_normal_cells}
        </tr>
        
        <tr>
          <td colspan="{3 + num_cartones}" class="row-revancha-header">🔥 REVANCHA (Q15 - Q21)</td>
        </tr>
        {rows_revancha_html}
        <tr class="tr-total">
          <td colspan="3" class="td-total" style="color:#a78bfa; text-align:right; font-size:11px;">SUMA REVANCHA →</td>
          {totales_revancha_cells}
        </tr>
      </tbody>
    </table>
    """

    # Ajuste dinámico de altura considerando las filas normales, de revancha y los dos bloques de sumas
    filas_totales = len(partidos_normal) + len(partidos_revancha) + 3
    altura_dinamica = 180 + (filas_totales * 44)
    components.html(table_html, height=altura_dinamica, scrolling=True)

    if auto_refresh:
        import time
        time.sleep(60)
        st.rerun()