import streamlit as st
import pandas as pd
import requests
import unicodedata
from supabase import create_client, Client
from datetime import datetime, timedelta

# ============================================================
# CONFIGURACIÓN
# ============================================================
URL_SUPABASE = "https://mznajuaorvnuakndinwo.supabase.co"
KEY_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im16bmFqdWFvcnZudWFrbmRpbndvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzMDE0NDksImV4cCI6MjA5Njg3NzQ0OX0.gZjhUeXxLNjTmdJP7fzSxPHZHLd7H-fzMNYpfN_qFC8"

supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

st.set_page_config(page_title="Monitor de Quinielas", layout="wide", page_icon="⚽")

# ============================================================
# ESTILOS GENERALES DE STREAMLIT
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.metric-box  { background: #11172a; border: 1px solid #1e2640; border-radius: 10px; padding: 16px; text-align: center; }
.metric-num  { font-size: 32px; font-weight: 700; color: #e2e8f0; }
.metric-lbl  { font-size: 11px; color: #4b5680; text-transform: uppercase; letter-spacing: 1px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# UTILS & HELPERS
# ============================================================
def calcular_resultado(g_h, g_a):
    if g_h is None or g_a is None:
        return None
    if g_h > g_a: return "L"
    if g_a > g_h: return "V"
    return "E"

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
        }
    return result

# ============================================================
# SUPABASE – QUERIES
# ============================================================
def cargar_jornadas():
    try:
        res = supabase.table("jornadas").select("*").eq("activa", True).order("id", desc=True).execute()
        return res.data or []
    except Exception:
        return []

def cargar_partidos(jornada_id: int):
    try:
        res = supabase.table("partidos_jornada").select("*").eq("jornada_id", jornada_id).order("casilla").execute()
        return res.data or []
    except Exception:
        return []

def cargar_quinielas(jornada_id: int):
    try:
        res = supabase.table("quinielas").select("*").eq("jornada_id", jornada_id).order("numero_carton").order("casilla").execute()
        return res.data or []
    except Exception:
        return []

def actualizar_resultado_db(partido_id: int, goles_l, goles_v, estado: str, resultado):
    try:
        supabase.table("partidos_jornada").update({
            "goles_local":  goles_l,
            "goles_visita": goles_v,
            "estado":       estado,
            "resultado":    resultado,
        }).eq("id", partido_id).execute()
    except Exception:
        pass

# ============================================================
# APP PRINCIPAL (MONITOR EN VIVO)
# ============================================================
st.title("⚽ Monitor de Quinielas en Vivo")

jornadas = cargar_jornadas()
if not jornadas:
    st.info("No hay jornadas activas disponibles en este momento.")
    st.stop()

opts3 = {j["nombre"]: j["id"] for j in jornadas}
sel3  = st.selectbox("Selecciona la Jornada", list(opts3.keys()), key="sel_monitor")
jid_mon = opts3[sel3]

col_btn1, col_btn2 = st.columns([1, 2])
btn_refresh  = col_btn1.button("🔄 Actualizar marcadores")
auto_refresh = col_btn2.toggle("⏱ Auto-refrescar cada 1 hora", value=True)

partidos_mon  = cargar_partidos(jid_mon)
quinielas_mon = cargar_quinielas(jid_mon)

# Sincronización con la API de ESPN
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

    partidos_mon = cargar_partidos(jid_mon)

if not partidos_mon:
    st.info("Esta jornada aún no cuenta con partidos programados.")
    st.stop()

num_cartones = max((q["numero_carton"] for q in quinielas_mon), default=0)
preds_map = {(q["casilla"], q["numero_carton"]): q["prediccion"] for q in quinielas_mon}
carton_ids = list(range(1, num_cartones + 1))

# Filtrado por tramos de casillas tradicionales de Progol
partidos_normal   = [p for p in partidos_mon if p["casilla"] <= 14]
partidos_revancha = [p for p in partidos_mon if 15 <= p["casilla"] <= 21]

aciertos_normal = {}
aciertos_revancha = {}

for ci in carton_ids:
    preds = {q["casilla"]: q["prediccion"] for q in quinielas_mon if q["numero_carton"] == ci}
    ac_n = sum(1 for p in partidos_normal if p.get("resultado") and preds.get(p["casilla"]) == p["resultado"])
    aciertos_normal[ci] = ac_n # Se almacena directamente el número entero
    
    ac_r = sum(1 for p in partidos_revancha if p.get("resultado") and preds.get(p["casilla"]) == p["resultado"])
    aciertos_revancha[ci] = ac_r # Se almacena directamente el número entero

thead_ths = "".join([f'<th class="th-carton">Q{ci}</th>' for ci in carton_ids])

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
            est_badge = '<span class="badge-live">● LIVE</span>'
        else:
            hora = (p.get("hora","") or "")[:5]
            dia  = p.get("dia","") or ""
            est_badge = f'<span class="badge-ns">{hora}<div class="date-subtext">{dia}</div></span>'

        loc_abbr = p["local_nombre"][:12].upper()
        vis_abbr = p["visita_nombre"][:12].upper()

        pred_cells = ""
        for ci in carton_ids:
            pred = str(preds_map.get((p["casilla"], ci), "")).strip()
            
            if not pred:
                css = "cell-empty"
                mostrar_pred = "&nbsp;"
            elif resultado and pred == resultado:
                css = "cell-ok"
                mostrar_pred = pred
            elif resultado and pred != resultado:
                css = "cell-fail"
                mostrar_pred = pred
            elif pred == "L": 
                css = "cell-L"
                mostrar_pred = pred
            elif pred == "E": 
                css = "cell-E"
                mostrar_pred = pred
            elif pred == "V": 
                css = "cell-V"
                mostrar_pred = pred
            else: 
                css = "cell-empty"
                mostrar_pred = "&nbsp;"
            
            pred_cells += f'<td class="pred-cell {css}">{mostrar_pred}</td>'

        # Fila limpia: Se remueve el span "casilla-inline" que generaba el número de control entre paréntesis
        html_bloque += "<tr>"
        html_bloque += '<td class="td-equipos">'
        html_bloque += f'<div class="eq-local">{loc_abbr}</div>'
        html_bloque += f'<div class="eq-visita">{vis_abbr}</div>'
        html_bloque += '</td>'
        html_bloque += f'<td class="td-marc">{marc_html}{est_badge}</td>'
        html_bloque += pred_cells
        html_bloque += "</tr>"
        
    return html_bloque

rows_normal_html = construir_bloque_filas(partidos_normal)

totales_normal_cells = ""
for ci in carton_ids:
    ac = aciertos_normal.get(ci, 0)
    totales_normal_cells += f'<td class="td-total style-n">{ac}</td>' # Imprime solo el número limpio

rows_revancha_html = construir_bloque_filas(partidos_revancha)

totales_revancha_cells = ""
for ci in carton_ids:
    ac = aciertos_revancha.get(ci, 0)
    totales_revancha_cells += f'<td class="td-total style-r">{ac}</td>' # Imprime solo el número limpio

# ============================================================
# ESTILOS DE LA TABLA (CSS NATIVO)
# ============================================================
st.markdown("""
<style>
.qtable-container {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    border-radius: 12px;
    background: #0d1117;
    margin-top: 15px;
}
.qtable {
    width: 100%; border-collapse: collapse;
    font-family: 'Inter', sans-serif; font-size: 13px;
}
.qtable th, .qtable td { padding: 10px 8px; text-align: center; border-bottom: 1px solid #1e2640; }
.th-equipos  { background:#111827; color:#4b5680; font-size:11px; text-align:left; width:160px; }
.th-marc     { background:#111827; color:#4b5680; font-size:11px; width:85px; }
.th-carton   { background:#111827; color:#94a3b8; font-size:12px; font-weight:700; min-width:45px; }

.td-equipos  { text-align:left; }
.eq-local    { color:#e2e8f0; font-weight:600; font-size:12px; }
.eq-visita   { color:#94a3b8; font-size:11px; margin-top:2px; }

.marc-ft     { color:#22c55e; font-weight:700; font-size:15px; }
.marc-live   { color:#ef4444; font-weight:700; font-size:15px; }
.marc-ns     { color:#334155; font-size:15px; }
.badge-ft    { display:block; font-size:9px; color:#22c55e; font-weight: 600; }
.badge-live  { display:block; font-size:9px; color:#ef4444; font-weight: 600; animation: blink 1s infinite; }
.badge-ns    { display:block; font-size:10px; color:#94a3b8; font-weight: 500; line-height: 1.2; }
.date-subtext { font-size: 8px; color: #4b5680; margin-top: 1px; }

@keyframes blink { 50%{ opacity:0.3; } }

.pred-cell   { font-weight:700; font-size:13px; }
.cell-ok     { background:#14532d; color:#4ade80; }
.cell-fail   { background:#1a1a1a; color:#334155; }
.cell-L      { background:#1e3a5f; color:#60a5fa; }
.cell-E      { background:#3d2e00; color:#fbbf24; }
.cell-V      { background:#14291e; color:#4ade80; }
.cell-empty  { color:#334155; }

.row-revancha-header {
    background: #1e1b4b !important; color: #c7d2fe !important;
    font-weight: 700; letter-spacing: 2px; font-size: 11px; text-align: left !important;
    padding: 10px 12px !important;
}
.td-total    { font-weight:700; font-size:12px; background:#111827; }
.style-n     { color: #38bdf8; }
.style-r     { color: #a78bfa; }
.tr-total td { border-top: 2px solid #1e2640; border-bottom: 2px solid #2d3748; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# RENDERIZADO DEL HTML DE LA TABLA
# ============================================================
total_colspan_sin_q = 2 + num_cartones

table_html = f"""
<div class="qtable-container">
    <table class="qtable">
      <thead>
        <tr>
          <th class="th-equipos">PARTIDO</th>
          <th class="th-marc">MARC</th>
          {thead_ths}
        </tr>
      </thead>
      <tbody>
        {rows_normal_html}
        <tr class="tr-total">
          <td colspan="2" class="td-total" style="color:#38bdf8; text-align:right; font-size:11px; padding-right:10px;">Aciertos Q1-Q14 →</td>
          {totales_normal_cells}
        </tr>
        <tr>
          <td colspan="{total_colspan_sin_q}" class="row-revancha-header">🔥 REVANCHA</td>
        </tr>
        {rows_revancha_html}
        <tr class="tr-total">
          <td colspan="2" class="td-total" style="color:#a78bfa; text-align:right; font-size:11px; padding-right:10px;">Aciertos Revancha →</td>
          {totales_revancha_cells}
        </tr>
      </tbody>
    </table>
</div>
"""

st.markdown(table_html, unsafe_allow_html=True)

# Temporizador para refresco fijo cada 1 hora (3600 segundos)
if auto_refresh:
    import time
    time.sleep(3600)
    st.rerun()
