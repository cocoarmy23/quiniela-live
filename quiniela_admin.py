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

# Sincronización automática con ESPN
if btn_refresh or auto_refresh:
    slugs_mon = set(p.get("league_slug","") for p in partidos_mon if p.get("league_slug") and p.get("fixture_id"))
    scores_vivo = {}
    for slug in slugs_mon:
        get_espn_scores.clear()
        scores_vivo
