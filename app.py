"""
Aurora Nebula — Dashboard ERP (Streamlit + Google Sheets)
=========================================================
Style "Power BI" sombre (dégradé ambre/or).
Lecture stricte d'un Google Sheet via un compte de service
(service_account.json). Aucune donnée n'est inventée : si une colonne
obligatoire manque, l'app s'arrête avec un message d'erreur explicite.
Lancement :
    pip install -r requirements.txt
    streamlit run app.py
Le fichier `service_account.json` doit être placé dans le même dossier
que `app.py`.
"""

from __future__ import annotations
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json

# ---------------------------------------------------------------------------
# Configuration (LOGIQUE MÉTIER — NE PAS MODIFIER)
# ---------------------------------------------------------------------------
SHEET_ID = "1kLvCbD-uNMD-ljwZOj8ZtcMu_-irjRp_TMcVNncAlP0"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
# Click-to-filter state (Power BI style cross-filtering)
if "filtres" not in st.session_state:
    st.session_state.filtres = {}
REQUIRED_SCHEMA: Dict[str, List[str]] = {
    "Products": ["id", "reference", "name", "description", "image_path", "price",
                 "stock", "min_stock", "security_stock", "alert_stock",
                 "category_id", "supplier_id", "created_at", "updated_at"],
    "Sales": ["id", "reference", "client_id", "subtotal", "tax_rate",
              "tax_amount", "discount_amount", "total", "status",
              "created_at", "updated_at"],
    "SaleItems": ["id", "sale_id", "product_id", "price", "quantity",
                  "refund_quantity", "total", "refund_total", "refund_status"],
    "Clients": ["id", "name", "email", "phone", "address",
                "created_at", "updated_at"],
    "Categories": ["id", "name", "description", "created_at", "updated_at"],
    "Purchases": ["id", "supplier_id", "total", "status",
                  "created_at", "updated_at"],
    "PurchaseItems": ["id", "purchase_id", "product_id", "price", "quantity",
                      "total", "created_at", "updated_at"],
    "Suppliers": ["id", "name", "phone", "address",
                  "created_at", "updated_at"],
    "Payments": ["id", "sale_id", "client_id", "amount", "method", "status",
                 "external_reference", "approved_by", "approved_at", "notes",
                 "created_at", "updated_at"],
    "Refunds": ["id", "sale_id", "total", "reason",
                "created_at", "updated_at"],
    "Devis": ["id", "reference", "client_id", "subtotal", "discount", "tax",
              "total", "status", "sent_at", "accepted_at", "rejected_at",
              "expires_at", "notes", "created_by", "created_at", "updated_at"],
    "DevisItems": ["id", "devis_id", "product_id", "quantity", "price", "total",
                   "created_at", "updated_at"],
    "StockMovements": ["id", "product_id", "quantity", "type", "source",
                       "reference_id", "created_at", "updated_at"],
    "PaymentAllocations": ["id", "payment_id", "payable_type", "payable_id",
                           "amount_applied", "created_at", "updated_at"],
    "CashLogs": ["id", "payment_id", "user_id", "action", "description",
                 "old_value", "new_value", "ip_address", "created_at", "updated_at"],
    "RefundItems": ["id", "refund_id", "product_id", "price", "quantity",
                    "total", "created_at", "updated_at"],
}
NUMERIC_COLS = {
    "Products": ["price", "stock", "min_stock", "security_stock", "alert_stock",
                 "category_id", "supplier_id", "id"],
    "Sales": ["id", "client_id", "subtotal", "tax_rate", "tax_amount",
              "discount_amount", "total"],
    "SaleItems": ["id", "sale_id", "product_id", "price", "quantity",
                  "refund_quantity", "total", "refund_total"],
    "Clients": ["id"],
    "Categories": ["id"],
    "Purchases": ["id", "supplier_id", "total"],
    "PurchaseItems": ["id", "purchase_id", "product_id", "price", "quantity",
                      "total"],
    "Suppliers": ["id"],
    "Payments": ["id", "sale_id", "client_id", "amount", "approved_by"],
    "Refunds": ["id", "sale_id", "total"],
    "Devis": ["id", "client_id", "subtotal", "discount", "tax", "total", "created_by"],
    "DevisItems": ["id", "devis_id", "product_id", "quantity", "price", "total"],
    "StockMovements": ["id", "product_id", "quantity", "reference_id"],
    "PaymentAllocations": ["id", "payment_id", "payable_id", "amount_applied"],
    "CashLogs": ["id", "payment_id", "user_id"],
    "RefundItems": ["id", "refund_id", "product_id", "price", "quantity", "total"],
}
DATE_COLS = ["created_at", "updated_at", "approved_at",
             "sent_at", "accepted_at", "rejected_at", "expires_at"]

# ---------------------------------------------------------------------------
# Streamlit page + thème "Power BI" sombre
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Aurora Nebula — ERP Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Authentification privée
# ---------------------------------------------------------------------------
if not st.session_state.get("auth_ok", False):
    st.markdown("""
    <style>
        .stApp { background: #1C1917 !important; }
        .block-container { max-width: 380px; margin: 15vh auto; }
        .login-box { background: #292524; padding: 2rem; border-radius: 12px; border: 1px solid #44403C; }
        .login-box h1 { text-align: center; font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }
        .login-box p { text-align: center; color: #A8A29E; font-size: 0.85rem; margin-bottom: 1.5rem; }
    </style>
    <div class="login-box">
        <div style="text-align:center;font-size:2rem;margin-bottom:0.5rem;">&#128274;</div>
        <h1>Aurora Nebula</h1>
        <p>Tableau de bord ERP — accès privé</p>
    """, unsafe_allow_html=True)
    user = st.text_input("Nom d'utilisateur", placeholder="admin", label_visibility="collapsed")
    pwd  = st.text_input("Mot de passe", type="password", placeholder="••••••••", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Se connecter", use_container_width=True):
            if user == st.secrets.get("auth_username") and pwd == st.secrets.get("auth_password"):
                st.session_state.auth_ok = True
                st.rerun()
            else:
                st.error("Identifiants incorrects")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Palette « Premium BI » — ambre / or raffiné (sombre)
# ---------------------------------------------------------------------------
PRIMARY      = "#F59E0B"
ACCENT       = "#FBBF24"
ACCENT2      = "#FCD34D"
DARK         = "#1C1917"
INK          = "#FAFAF9"
MUTED        = "#A8A29E"
BG           = "#1C1917"
CARD         = "#292524"
GRID         = "#44403C"
HEADER_FROM  = "#78350F"
HEADER_TO    = "#B45309"
ICON_BG      = "#92400E"
KPI_ACCENT_FROM = "#F59E0B"
KPI_ACCENT_TO   = "#78350F"
POSITIVE = "#D97706"
WARNING  = "#F59E0B"
NEGATIVE = "#B45309"
BI_PALETTE = ["#F59E0B", "#FBBF24", "#FCD34D", "#D97706", "#B45309",
              "#78350F", "#FDE68A", "#92400E", "#FEF3C7", "#451A03"]
SEQ_BLUE   = ["#FEF3C7", "#FDE68A", "#FCD34D", "#FBBF24", "#F59E0B",
              "#D97706", "#B45309", "#92400E", "#78350F"]

def _fmt(v, zero=""):
    if pd.isna(v) or (isinstance(v, float) and v is float) or v is None:
        return zero
    v = float(v)
    if abs(v) >= 1e9:
        return f"{v/1e9:.1f} Mrd"
    elif abs(v) >= 1e6:
        return f"{v/1e6:.1f}M"
    elif abs(v) >= 1e3:
        return f"{v/1e3:.0f}k"
    elif v == 0:
        return zero
    else:
        return f"{v:.0f}"

POWERBI_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    html, body, [class*="css"]  {{
        font-family: 'Inter', 'Aptos', 'Helvetica', sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}
     
            .stApp {{
        background: {DARK};
        color: {INK};
    }}
    
    .block-container {{
        max-width: 1500px;
        padding-top: 0.6rem;
    }}
    .vba-header {{
        background: linear-gradient(120deg, #451A03 0%, {HEADER_FROM} 40%, #78350F 100%);
        border-radius: 10px;
        padding: 6px 16px;
        margin-bottom: 10px;
        position: relative;
        display: flex; align-items: center; justify-content: space-between;
        color: #FFFFFF;
        box-shadow: 0 2px 8px -4px rgba(0,0,0,0.4);
    }}
    .vba-header .icon-circle {{
        width: 26px; height: 26px; border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #D97706 0%, {ICON_BG} 60%, #451A03 100%);
        border: 1.5px solid rgba(255,255,255,0.55);
        display: flex; align-items: center; justify-content: center;
        color: #FFFFFF; font-size: 13px; font-weight: 800;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.35), inset 0 -1px 2px rgba(255,255,255,0.15), 0 4px 10px rgba(0,0,0,0.25);
    }}
    .vba-header .title {{
        flex: 1; text-align: center;
        font-size: 16px; font-weight: 800; letter-spacing: 0.5px;
        font-family: 'Inter','Aptos','Helvetica',sans-serif;
    }}
    .vba-header .meta {{
        text-align: right; font-size: 9px; line-height: 1.2;
        color: rgba(255,255,255,0.92); letter-spacing: 0.2px;
    }}
    .vba-header .meta b {{ font-weight: 700; }}
    h1, h2, h3, h4 {{
        color: {INK}; font-family: 'Inter','Aptos',sans-serif;
        letter-spacing: -0.2px;
    }}
    .element-container {{
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }}
    .stRow {{
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }}
    [data-testid="stSidebar"] .stCheckbox label {{
        color: {INK} !important;
        font-size: 13px;
    }}
    .stMarkdown {{
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    [data-testid="stVerticalBlock"] {{
        gap: 0rem !important;
        row-gap: 0rem !important;
        column-gap: 0rem !important;
    }}
    [data-testid="stVerticalBlock"] > div {{
        margin-bottom: 0 !important;
        margin-top: 0 !important;
    }}
    [data-testid="column"] [data-testid="stVerticalBlock"] {{
        gap: 0rem !important;
        row-gap: 0rem !important;
    }}
    .stHorizontalBlock {{
        gap: 12px !important;
    }}
    div[data-testid="stMarkdownContainer"] {{
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
        min-height: 0 !important;
    }}
    .stRow:has([data-testid="stMarkdownContainer"]) + .stRow:has([data-testid="stPlotlyChart"]) {{
        margin-top: -6px !important;
    }}
    section[data-testid="stSidebar"] > div {{
        background: linear-gradient(180deg, #1C1917 0%, #231F1D 100%);
        border-right: 1px solid rgba(68,64,60,0.3);
    }}
    section[data-testid="stSidebar"] > div > div:first-child > div:first-child {{
        padding-top: 10px !important;
    }}
    section[data-testid="stSidebar"] * {{
        border-color: rgba(68,64,60,0.3) !important;
    }}
    .kpi-card {{
        background: {CARD};
        border: 1px solid {GRID};
        border-radius: 14px;
        padding: 10px 14px;
        position: relative;
        overflow: hidden;
        text-align: center;
        transition: all 0.2s ease;
    }}
    .kpi-card::before {{
        content: "";
        position: absolute;
        top: -20px; right: -20px;
        width: 60px; height: 60px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(245,158,11,0.15) 0%, transparent 70%);
        pointer-events: none;
    }}
    .kpi-card > * {{ position: relative; z-index: 2; }}
    .kpi-card:hover {{
        border-color: rgba(245,158,11,0.25);
    }}
    .kpi-head {{
        display: flex; align-items: center; justify-content: center;
        gap: 6px; margin-bottom: 4px;
    }}
    .kpi-icon {{
        font-size: 16px; font-weight: 700; color: {PRIMARY};
    }}
    .kpi-title {{
        font-size: 10px; font-weight: 500; color: {MUTED};
        letter-spacing: 0.5px; text-transform: uppercase;
        white-space: nowrap;
    }}
    .kpi-value {{
        font-size: 22px; font-weight: 700; color: {INK};
        font-family: 'Inter','Aptos',sans-serif;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }}
    .kpi-sub {{
        font-size: 11px; font-weight: 600;
        margin-top: 2px;
        display: flex; align-items: center; justify-content: center; gap: 4px;
        min-height: 16px;
    }}
    .kpi-delta-pos {{ color: #10B981; }}
    .kpi-delta-neg {{ color: #EF4444; }}
    .kpi-delta-neu {{ color: {MUTED}; }}
    div[data-testid="stMetric"] {{
        background: linear-gradient(160deg, #302C28 0%, {CARD} 45%, #23201E 100%);
        border: 1px solid rgba(68,64,60,0.4);
        border-left: 3px solid {PRIMARY};
        border-radius: 12px;
        padding: 8px 12px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1), 0 4px 8px -4px rgba(0,0,0,0.2);
        transition: all 0.2s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        border-color: rgba(245,158,11,0.15);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1), 0 6px 12px -6px rgba(0,0,0,0.25);
    }}
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetric"] > :first-child > :first-child,
    [data-testid="stMetric"] > :first-child > :first-child * {{
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 10px !important;
    }}
    div[data-testid="stMetric"] * {{
        color: #FFFFFF !important;
    }}
    div[data-testid="stMetricValue"] {{
        color: #FFFFFF; font-weight: 800; font-size: 20px;
        letter-spacing: -0.4px; font-variant-numeric: tabular-nums;
    }}
    div[data-testid="stMetricDelta"] {{ font-weight: 600; font-size: 11px; }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; background: {CARD}; padding: 6px;
        border-radius: 12px; border: 1px solid {GRID};
        box-shadow: 0 6px 16px -8px rgba(0,0,0,0.3);
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent; border-radius: 8px;
        padding: 8px 18px; color: {MUTED}; font-weight: 600;
        letter-spacing: 0.2px;
        transition: all .2s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ color: {INK}; background: #3C3528; }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {HEADER_FROM}, {HEADER_TO});
        color: #FFFFFF !important;
        box-shadow: 0 6px 14px -4px rgba(0,0,0,0.5);
    }}
    .stSelectbox label,
    .stSelectbox div[data-baseweb="select"] > div {{
        color: #D6D3D1 !important;
        font-weight: 600 !important;
    }}
    .stSelectbox div[data-baseweb="select"] > div {{
        background: rgba(41,37,36,0.85) !important;
        border: 1px solid rgba(68,64,60,0.5) !important;
        color: #F5F5F4 !important;
        font-weight: 500 !important;
    }}
    .stSelectbox ul {{
        background: #292524 !important;
        border: 1px solid rgba(68,64,60,0.5) !important;
    }}
    .stSelectbox li {{
        color: #D6D3D1 !important;
    }}
    .stSelectbox li:hover {{
        background: rgba(245,158,11,0.15) !important;
        color: #F5F5F4 !important;
    }}
    .stSelectbox [role="option"][aria-selected="true"] {{
        background: rgba(245,158,11,0.25) !important;
        color: #FFFFFF !important;
    }}
    div[data-testid="stSelectbox"] > div:first-child {{
        margin-top: -8px;
    }}
    .chart-card {{
        background: linear-gradient(160deg, #302C28 0%, {CARD} 45%, #23201E 100%);
        border: 1px solid rgba(68,64,60,0.35);
        border-radius: 14px;
        padding: 8px 12px 6px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1), 0 4px 8px -4px rgba(0,0,0,0.2);
        margin-bottom: 8px;
        transition: border-color .2s ease;
    }}
    .chart-card::before {{
        content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px;
        background: linear-gradient(90deg, {ACCENT2}, {PRIMARY} 40%, {KPI_ACCENT_TO});
        z-index: 2;
    }}
    .chart-card > * {{ position: relative; z-index: 1; }}
    .chart-card:hover {{
        border-color: rgba(245,158,11,0.1);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1), 0 6px 12px -6px rgba(0,0,0,0.25);
    }}
    .chart-card h4 {{
        margin: 0 0 4px 0; color: {INK};
        font-size: 12px; font-weight: 700;
        letter-spacing: 0.2px;
    }}
    .chart-title {{
        display: flex; align-items: center; gap: 6px;
        margin: 0 0 -4px;
        padding: 2px 10px;
        background: rgba(41,37,36,0.4);
        border: 1px solid rgba(68,64,60,0.2);
        border-radius: 8px 8px 0 0;
        position: relative;
        overflow: hidden;
    }}
    .chart-title .accent {{
        width: 3px; min-height: 20px; border-radius: 3px;
        background: linear-gradient(180deg, {ACCENT2}, {PRIMARY} 40%, {KPI_ACCENT_TO});
        flex-shrink: 0;
    }}
    .chart-title .ct-main {{
        font-size: 11px; font-weight: 700; color: {INK};
        letter-spacing: -0.2px; line-height: 1.2;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .chart-title .ct-sub {{
        font-size: 9px; font-weight: 600; color: #D6D3D1;
        letter-spacing: 0.3px; margin-top: 1px;
        text-transform: uppercase;
    }}
    div[data-testid="stPlotlyChart"] {{
        background: linear-gradient(160deg, #302C28 0%, {CARD} 45%, #23201E 100%);
        border: 1px solid rgba(68,64,60,0.3);
        border-top: none;
        border-radius: 0 0 8px 8px;
        padding: 4px 4px 2px;
        margin-bottom: 2px !important;
        margin-top: 0 !important;
        position: relative;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1), 0 4px 8px -4px rgba(0,0,0,0.2);
    }}
    div[data-testid="stPlotlyChart"]:hover {{
        border-color: rgba(245,158,11,0.08);
        box-shadow: 0 2px 4px rgba(0,0,0,0.1), 0 6px 12px -6px rgba(0,0,0,0.25);
    }}
    .stDataFrame, .stTable {{
        background: {CARD}; border-radius: 10px;
        border: 1px solid {GRID};
        box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        overflow: hidden;
    }}
    .stDataFrame [data-testid="stTable"], .stDataFrame table {{
        font-variant-numeric: tabular-nums;
    }}
    .stDataFrame thead tr th, .stDataFrame [role="columnheader"] {{
        background: linear-gradient(135deg, {HEADER_FROM}, {HEADER_TO}) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        letter-spacing: 0.3px;
        text-transform: uppercase;
        font-size: 10px !important;
        padding: 6px 8px !important;
        border-bottom: 0 !important;
    }}
    .stDataFrame tbody tr:nth-child(even) td {{
        background: #33302E !important;
    }}
    .stDataFrame tbody tr:hover td {{
        background: #3C3528 !important;
    }}
    .stDataFrame tbody td {{
        font-size: 11px !important;
        color: {INK} !important;
        border-color: {GRID} !important;
        padding: 4px 8px !important;
    }}
    .stButton>button, .stDownloadButton>button {{
        background: linear-gradient(135deg, {HEADER_FROM}, {HEADER_TO});
        color: #FFFFFF; border: 0; border-radius: 10px;
        font-weight: 600; padding: 8px 18px;
        letter-spacing: 0.3px;
        box-shadow:
            0 6px 14px -4px rgba(0,0,0,0.5),
            inset 0 1px 0 rgba(255,255,255,0.08);
        transition: all .22s cubic-bezier(.2,.95,.4,1.05);
    }}
    .stButton>button:hover, .stDownloadButton>button:hover {{
        transform: translateY(-1px) scale(1.02);
        box-shadow:
            0 10px 22px -6px rgba(0,0,0,0.6),
            inset 0 1px 0 rgba(255,255,255,0.1);
        filter: brightness(1.06);
    }}
    .stButton>button:active, .stDownloadButton>button:active {{
        transform: translateY(0) scale(0.99);
    }}
    div[data-baseweb="select"] > div, .stTextInput input, .stDateInput input,
    div[data-baseweb="input"] > div {{
        background: {DARK} !important;
        border: 1px solid {GRID} !important;
        border-radius: 10px !important;
        transition: all .2s ease;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }}
    div[data-baseweb="select"] > div:hover,
    div[data-baseweb="input"] > div:hover {{
        border-color: #7C6A3F !important;
    }}
    div[data-baseweb="select"] > div:focus-within,
    .stTextInput input:focus, .stDateInput input:focus,
    div[data-baseweb="input"] > div:focus-within {{
        border-color: {PRIMARY} !important;
        box-shadow: 0 0 0 3px rgba(245,158,11,0.2) !important;
    }}
    .slicer-label {{
        font-size: 11px; font-weight: 600; color: {DARK};
        text-transform: uppercase; letter-spacing: 1px;
        margin-bottom: 6px;
    }}
    .stSidebar div[data-testid="stButton"] {{
        margin-bottom: 5px !important;
    }}
    .stSidebar div[data-testid="stButton"] button {{
        border-radius: 10px !important;
        padding: 10px 14px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        text-align: left !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        transition: all .2s ease !important;
        background: linear-gradient(135deg, #FBBF24, #D97706, #B45309) !important;
        border: 2px solid #FBBF24 !important;
        color: #FFFFFF !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    }}
    .stSidebar div[data-testid="stButton"] button:hover {{
        transform: translateX(3px) !important;
        box-shadow: 0 4px 16px rgba(245,158,11,0.4), inset 0 1px 0 rgba(255,255,255,0.2) !important;
        filter: brightness(1.08);
    }}
    .stSidebar div[data-testid="stButton"] button[data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, #FCD34D, #F59E0B, #D97706) !important;
        border-color: #FCD34D !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        box-shadow: 0 0 20px rgba(245,158,11,0.4), inset 0 0 30px rgba(255,255,255,0.08) !important;
    }}
    .stSidebar .stSelectbox {{
        margin-bottom: -4px;
    }}
    .stSidebar .stSelectbox label {{
        font-size: 10px !important;
        text-transform: uppercase;
        letter-spacing: .4px;
        color: #D6D3D1 !important;
    }}
    .stSidebar .stCheckbox label {{
        font-size: 11px;
    }}
    .section-title {{
        display: flex; align-items: center; gap: 8px;
        margin: 10px 0 6px;
        padding: 6px 12px;
        background: rgba(41,37,36,0.6);
        border: 1px solid rgba(68,64,60,0.3);
        border-radius: 10px;
        position: relative;
        overflow: hidden;
    }}
    .section-title::before {{
        content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
        background: linear-gradient(180deg, {PRIMARY}, {KPI_ACCENT_TO});
        border-radius: 10px 0 0 10px;
    }}
    .section-title .text {{
        font-size: 12px; font-weight: 700; color: {INK};
        letter-spacing: 0.2px;
        text-transform: uppercase;
    }}
    footer {{ visibility: hidden; }}
    #MainMenu {{ visibility: hidden; }}
    #chart-g4 div[data-testid="stPlotlyChart"] {{
        padding-top: 2px !important;
        padding-bottom: 2px !important;
    }}
    @media print {{
        @page {{ size: A4 landscape; margin: 8mm; }}
        body {{ background: #FFFFFF !important; }}
        section[data-testid="stSidebar"] {{ display: none !important; }}
        section.main > div:first-child {{ margin-left: 0 !important; max-width: 100% !important; }}
        .stApp {{ background: #FFFFFF !important; }}
        footer, #MainMenu, header {{ display: none !important; }}
        .block-container {{ max-width: 100% !important; padding: 0 !important; }}
        div[data-testid="stVerticalBlock"] > div:has(> .section-title) {{ page-break-before: always; }}
        div[data-testid="stVerticalBlock"] > div:first-child:has(> .section-title) {{ page-break-before: avoid; }}
        .kpi-card, div[data-testid="stMetric"], .chart-card {{
            break-inside: avoid;
            box-shadow: none !important;
            border: 1px solid #E7E5E4 !important;
            background: #FAFAF9 !important;
        }}
        .vba-header, .stSelectbox, div[data-testid="stSelectbox"], .stTabs, button {{
            display: none !important;
        }}
        .kpi-value {{ color: #1C1917 !important; font-size: 20px !important; }}
        div[data-testid="stMetric"] * {{ color: #1C1917 !important; }}
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ color: #1C1917 !important; }}
    }}
</style>
"""
st.markdown(POWERBI_CSS, unsafe_allow_html=True)

# ---------- Fonction d'espacement ----------
def spacer(height: int = 15):
    st.markdown(f"<div style='height:{height}px'></div>", unsafe_allow_html=True)

# ---------- Style des graphiques ----------
def style_fig(fig: go.Figure, height: int = 220, *, pie: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(family="Inter, sans-serif", size=10, color=INK),
        margin=dict(l=4, r=4, t=25 if pie else 30, b=12 if pie else 18),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="center", x=0.5,
                    font=dict(size=9, color=MUTED),
                    bgcolor="rgba(41,37,36,0.5)"),
        colorway=BI_PALETTE,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(41,37,36,0.95)",
                        bordercolor=PRIMARY,
                        font_size=10,
                        font_family="Inter, sans-serif",
                        font_color=INK),
    )
    fig.update_xaxes(
        showgrid=False, zeroline=False, title=None,
        showticklabels=True, tickfont=dict(size=8, color=MUTED),
        showline=True, linecolor=GRID,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, zeroline=False, title=None,
        tickfont=dict(size=8, color=MUTED),
        showline=False,
    )
    fig.update_traces(
        selector=dict(type="bar"),
        marker_line_width=0,
        width=0.85,
        textfont=dict(size=9, color=INK, family="Inter, sans-serif"),
        textposition="inside",
        insidetextanchor="middle",
        cliponaxis=False,
    )
    for tr in fig.data:
        if tr.type == "bar" and (getattr(tr, "text", None) is None) and (
           getattr(tr, "texttemplate", None) is None):
            tr.texttemplate = "%{y:,.0f}"
    try:
        fig.update_traces(selector=dict(type="bar"), marker_cornerradius=4)
    except (ValueError, TypeError):
        pass
    fig.update_layout(bargap=0.05, bargroupgap=0.02)
    fig.update_traces(
        selector=dict(type="scatter"),
        line=dict(width=2, shape="spline", smoothing=0.6),
        marker=dict(size=4, line=dict(width=1, color="#292524")),
    )
    fig.update_traces(
        selector=dict(type="pie"),
        textfont=dict(size=9, color=INK, family="Inter, sans-serif"),
        marker=dict(line=dict(color="#292524", width=1.5)),
    )
    fig.update_traces(
        selector=dict(type="funnel"),
        marker=dict(line=dict(color="#292524", width=1)),
        textfont=dict(size=9, color=INK),
    )
    return fig

def styled_table(df: pd.DataFrame, max_rows: int = 400):
    view = df.head(max_rows).copy()
    for c in view.columns:
        if view[c].dtype == object:
            view[c] = view[c].fillna("—")
    num_cols = view.select_dtypes(include=np.number).columns.tolist()
    sty = (
        view.style
        .set_table_styles([
            {"selector": "th.col_heading",
             "props": [("background", f"linear-gradient(135deg,{HEADER_FROM},{HEADER_TO})"),
                       ("color", "#FFFFFF"), ("font-weight", "700"),
                       ("text-transform", "uppercase"), ("letter-spacing", "0.4px"),
                       ("font-size", "11px"), ("padding", "8px 10px"),
                        ("border", "0")]},
            {"selector": "th.row_heading",
             "props": [("background", "#33302E"), ("color", INK),
                       ("font-weight", "600"), ("border", "0")]},
            {"selector": "td",
             "props": [("font-size", "12.5px"), ("color", INK),
                       ("border-color", {GRID}),
                       ("font-variant-numeric", "tabular-nums")]},
        ])
        .set_properties(**{"padding": "6px 10px"})
    )
    if num_cols:
        sty = sty.format("{:,.0f}", subset=num_cols, na_rep="—")
        try:
            sty = sty.background_gradient(cmap="YlOrBr", subset=num_cols, axis=0)
        except Exception:
            pass
        try:
            sty = sty.bar(subset=num_cols, color="rgba(245,158,11,0.25)", align="left")
        except Exception:
            pass
    return sty

def card(title: str):
    return st.container()

def section_title(title: str, subtitle: str = ""):
    sub = f"<div class='ct-sub'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"<div class='chart-title'><span class='accent'></span>"
        f"<div><div class='ct-main'>{title}</div>{sub}</div></div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Cross-filter helper
# ---------------------------------------------------------------------------
def _set_filter(key: str, value):
    st.session_state.filtres[key] = value
    st.rerun()

def _handle_chart_selection(selection_state, key: str, label_key: str):
    if selection_state and selection_state.selection and selection_state.selection.points:
        pt = selection_state.selection.points[0]
        val = str(pt.get("label", pt.get("x", pt.get("location"))))
        if not val or val == "":
            return
        if st.session_state.filtres.get(key) != val:
            _set_filter(key, val)

# ---------------------------------------------------------------------------
# Chargement des données depuis Google Sheets
# ---------------------------------------------------------------------------
def _get_client() -> gspread.Client:
    if SERVICE_ACCOUNT_FILE.exists():
        creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    elif "SERVICE_ACCOUNT_JSON" in st.secrets:
        info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        st.error(
            f"Fichier d'identifiants introuvable : `{SERVICE_ACCOUNT_FILE.name}`.\n\n"
            "Placez votre fichier `service_account.json` à côté de `app.py` "
            "ou ajoutez `SERVICE_ACCOUNT_JSON` dans les secrets Streamlit."
        )
        st.stop()
    return gspread.authorize(creds)

def _coerce(df: pd.DataFrame, sheet: str) -> pd.DataFrame:
    df = df.replace({"": np.nan})
    for col in NUMERIC_COLS.get(sheet, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

@st.cache_data(show_spinner="Chargement du Google Sheet…", ttl=600)
def load_all_sheets() -> Dict[str, pd.DataFrame]:
    client = _get_client()
    try:
        sh = client.open_by_key(SHEET_ID)
    except Exception as exc:
        st.error(f"Impossible d'ouvrir le Google Sheet `{SHEET_ID}` : {exc}")
        st.stop()
    available = {ws.title: ws for ws in sh.worksheets()}
    data: Dict[str, pd.DataFrame] = {}
    for sheet, required_cols in REQUIRED_SCHEMA.items():
        if sheet not in available:
            st.error(f"Feuille manquante dans le Google Sheet : **{sheet}**.")
            st.stop()
        rows = available[sheet].get_all_records()
        df = pd.DataFrame(rows)
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            st.error(
                f"Colonnes manquantes dans la feuille **{sheet}** : "
                f"{', '.join(missing)}.\nColonnes trouvées : {list(df.columns)}"
            )
            st.stop()
        data[sheet] = _coerce(df, sheet)
    return data

# ---------------------------------------------------------------------------
# Construction des vues jointes & calculs
# ---------------------------------------------------------------------------
def build_sales_full(d: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    sales = d["Sales"].rename(columns={"id": "sale_id", "reference": "sale_reference",
                                       "total": "sale_total", "status": "sale_status",
                                       "created_at": "sale_date"})
    items = d["SaleItems"].rename(columns={"price": "item_price",
                                           "total": "item_total"})
    products = d["Products"][["id", "name", "reference", "price", "category_id"]].rename(
        columns={"id": "product_id", "name": "product_name",
                 "reference": "product_reference", "price": "product_price"}
    )
    cats = d["Categories"][["id", "name"]].rename(columns={"id": "category_id",
                                                           "name": "category_name"})
    clients = d["Clients"][["id", "name"]].rename(columns={"id": "client_id",
                                                           "name": "client_name"})
    df = items.merge(sales, on="sale_id", how="left")
    df = df.merge(products, on="product_id", how="left")
    df = df.merge(cats, on="category_id", how="left")
    df = df.merge(clients, on="client_id", how="left")
    return df

def build_purchases_full(d: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    p = d["Purchases"].rename(columns={"id": "purchase_id", "total": "purchase_total",
                                       "status": "purchase_status",
                                       "created_at": "purchase_date"})
    pi = d["PurchaseItems"].rename(columns={"price": "item_price",
                                            "total": "item_total"})
    sup = d["Suppliers"][["id", "name"]].rename(columns={"id": "supplier_id",
                                                          "name": "supplier_name"})
    prod = d["Products"][["id", "name"]].rename(columns={"id": "product_id",
                                                          "name": "product_name"})
    df = pi.merge(p, on="purchase_id", how="left")
    df = df.merge(sup, on="supplier_id", how="left")
    df = df.merge(prod, on="product_id", how="left")
    return df

def in_period(df: pd.DataFrame, col: str, start: datetime, end: datetime) -> pd.DataFrame:
    s = df[col]
    return df[(s >= pd.Timestamp(start)) & (s <= pd.Timestamp(end))]

# ---------------------------------------------------------------------------
# Sidebar : filtre Mois et Année (remplacement complet)
# ---------------------------------------------------------------------------
st.sidebar.markdown(
    f"<div style='text-align:center;margin-bottom:14px;padding:14px 10px 10px;background:linear-gradient(160deg,rgba(120,53,15,0.2),transparent);border-radius:14px;border:1px solid rgba(245,158,11,0.1);'>"
    f"<div style='background:linear-gradient(135deg,#FBBF24,#D97706,#B45309);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-size:22px;font-weight:900;font-family:Inter,Aptos,sans-serif;letter-spacing:-.5px;text-shadow:none;'>ERP Dashboard</div>"
    f"<div style='width:30px;height:2px;background:linear-gradient(90deg,transparent,#F59E0B,transparent);margin:6px auto 0;border-radius:2px;'></div>"
    f"</div>",
    unsafe_allow_html=True,
)
if st.sidebar.button("🔄 Rafraîchir", key="sidebar_refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
data = load_all_sheets()
sales_full = build_sales_full(data)
purchases_full = build_purchases_full(data)
all_years = sorted(sales_full["sale_date"].dt.year.dropna().unique())
if not all_years:
    st.error("Aucune date de vente trouvée.")
    st.stop()
default_year = max(all_years)
annee = st.sidebar.selectbox("Année", all_years, index=all_years.index(default_year))
mois_options = ["Tous"] + [datetime(2000, m, 1).strftime("%B") for m in range(1, 13)]
mois_selection = st.sidebar.selectbox("Mois", mois_options, index=0)
st.sidebar.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
exclude_refunded = st.sidebar.checkbox("Exclure ventes remboursées", value=False)
st.sidebar.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# Déterminer la période courante (start_dt, end_dt)
if mois_selection == "Tous":
    start_dt = datetime(annee, 1, 1)
    end_dt = datetime(annee, 12, 31, 23, 59, 59)
else:
    mois_num = mois_options.index(mois_selection)
    start_dt = datetime(annee, mois_num, 1)
    if mois_num == 12:
        end_dt = datetime(annee, 12, 31, 23, 59, 59)
    else:
        end_dt = datetime(annee, mois_num + 1, 1) - timedelta(seconds=1)
prev_annee = annee - 1
if mois_selection == "Tous":
    prev_start_dt = datetime(prev_annee, 1, 1)
    prev_end_dt = datetime(prev_annee, 12, 31, 23, 59, 59)
else:
    mois_num = mois_options.index(mois_selection)
    prev_start_dt = datetime(prev_annee, mois_num, 1)
    if mois_num == 12:
        prev_end_dt = datetime(prev_annee, 12, 31, 23, 59, 59)
    else:
        prev_end_dt = datetime(prev_annee, mois_num + 1, 1) - timedelta(seconds=1)

# ===== Affichage des filtres actifs (cross-filtering) =====
_FILTER_LABELS = {
    "region": "Région",
    "mois": "Mois",
    "produit": "Produit",
    "categorie": "Catégorie",
    "paiement": "Paiement",
    "date": "Date",
    "client": "Client",
    "fournisseur": "Fournisseur",
}
filtres = st.session_state.get("filtres", {})
if filtres:
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Filtres actifs**")
    for k, v in list(filtres.items()):
        c1, c2 = st.sidebar.columns([3, 1])
        label = _FILTER_LABELS.get(k, k)
        c1.caption(f"**{label}**: {v}")
        if c2.button("✕", key=f"clear_{k}", help=f"Supprimer filtre {label}"):
            del st.session_state.filtres[k]
            st.rerun()
    if st.sidebar.button("Effacer tous les filtres", type="primary", use_container_width=True):
        st.session_state.filtres = {}
        st.rerun()

# ---------------------------------------------------------------------------
# Filtres période
# ---------------------------------------------------------------------------
sf = sales_full.copy()
if exclude_refunded:
    sf = sf[sf["sale_status"].fillna("").str.lower() != "refunded"]
sf_cur = in_period(sf, "sale_date", start_dt, end_dt)
sf_prev = in_period(sf, "sale_date", prev_start_dt, prev_end_dt)
pay = data["Payments"]
pay_cur = in_period(pay, "created_at", start_dt, end_dt)
pu_cur = in_period(purchases_full, "purchase_date", start_dt, end_dt)

# ===== CROSS-FILTERING (click-to-filter type Power BI) =====
filtres = st.session_state.get("filtres", {})
if "region" in filtres:
    _reg_val = filtres["region"]
    geojson_path = Path(__file__).parent / "maroc.geojson"
    villes_path = Path(__file__).parent / "villes.json"
    if geojson_path.exists() and villes_path.exists():
        import json
        with open(villes_path, "r", encoding="utf-8") as _f:
            _vdata = json.load(_f)
        _vdf = pd.DataFrame(_vdata)
        _vdf["ville_norm"] = (_vdf["ville"].astype(str).str.strip()
                              .str.normalize("NFKD")
                              .str.encode("ascii", "ignore")
                              .str.decode("ascii").str.lower())
        _vdf["region_code"] = _vdf["region"].astype(str)
        _region_mapping = {
            "1": "Tanger-Tétouan-Al Hoceïma",
            "2": "Oriental",
            "3": "Fès-Meknès",
            "4": "Rabat-Salé-Kénitra",
            "5": "Béni Mellal-Khénifra",
            "6": "Casablanca-Settat",
            "7": "Marrakech-Safi",
            "8": "Drâa-Tafilalet",
            "9": "Souss-Massa",
            "10": "Guelmim-Oued Noun",
            "11": "Laâyoune-Sakia El Hamra",
            "12": "Dakhla-Oued Ed-Dahab",
        }
        _vdf["region_nom"] = _vdf["region_code"].astype(str).map(_region_mapping)
        _cli = data["Clients"][["id", "address"]].rename(columns={"id": "client_id", "address": "city_raw"})
        _cli["city_norm"] = (_cli["city_raw"].fillna("").astype(str).str.strip()
                             .str.lower().str.normalize("NFKD")
                             .str.encode("ascii", "ignore").str.decode("ascii"))
        _cm = _cli.merge(_vdf[["ville_norm", "region_nom"]], left_on="city_norm", right_on="ville_norm", how="left")
        _reg_clients = _cm.loc[_cm["region_nom"] == _reg_val, "client_id"].unique()
        sf_cur = sf_cur[sf_cur["client_id"].isin(_reg_clients)]
        sf_prev = sf_prev[sf_prev["client_id"].isin(_reg_clients)]
if "mois" in filtres:
    _mois_val = int(filtres["mois"])
    sf_cur = sf_cur[sf_cur["sale_date"].dt.month == _mois_val]
    sf_prev = sf_prev[sf_prev["sale_date"].dt.month == _mois_val]
if "produit" in filtres:
    _prod_val = filtres["produit"]
    sf_cur = sf_cur[sf_cur["product_name"] == _prod_val]
    sf_prev = sf_prev[sf_prev["product_name"] == _prod_val]
if "categorie" in filtres:
    _cat_val = filtres["categorie"]
    sf_cur = sf_cur[sf_cur["category_name"] == _cat_val]
    sf_prev = sf_prev[sf_prev["category_name"] == _cat_val]
if "paiement" in filtres:
    _pay_val = filtres["paiement"]
    pay_cur = pay_cur[pay_cur["method"].str.strip().str.lower() == _pay_val.strip().lower()]
    _sids = pay_cur["sale_id"].unique()
    sf_cur = sf_cur[sf_cur["sale_id"].isin(_sids)]
    sf_prev = sf_prev[sf_prev["sale_id"].isin(_sids)]
if "client" in filtres:
    _cli_val = filtres["client"]
    sf_cur = sf_cur[sf_cur["client_name"] == _cli_val]
    sf_prev = sf_prev[sf_prev["client_name"] == _cli_val]
if "date" in filtres:
    _d_val = pd.Timestamp(filtres["date"])
    sf_cur = sf_cur[sf_cur["sale_date"].dt.date == _d_val.date()]
    sf_prev = sf_prev[sf_prev["sale_date"].dt.date == _d_val.date()]
_prod_sup_map = {}
if "fournisseur" in filtres:
    _sup_name = filtres["fournisseur"]
    pu_cur = pu_cur[pu_cur["supplier_name"] == _sup_name]
    _sup_prod_ids = pu_cur["product_id"].unique()
    if len(_sup_prod_ids):
        sf_cur = sf_cur[sf_cur["product_id"].isin(_sup_prod_ids)]
        sf_prev = sf_prev[sf_prev["product_id"].isin(_sup_prod_ids)]

def kpi_delta(cur: float, prev: float) -> str:
    if not prev:
        return "—"
    return f"{(cur - prev) / prev * 100:+.1f}%"

# ---------------------------------------------------------------------------
# Header Power BI
# ---------------------------------------------------------------------------
if "section" not in st.session_state:
    st.session_state.section = "Ventes"
section = st.session_state.section
_section_titles = {
    "Ventes": "des ventes",
    "Clients": "des clients",
    "Stock & Achats": "de stock",
    "Trésorerie": "de trésorerie",
    "AI Agent": "d'analyse",
}
_section_sub = _section_titles.get(section, "")
st.markdown(
    f"""
    <div class='vba-header'>
        <div class='icon-circle'>$</div>
        <div class='title'>Tableau de bord{ ' ' + _section_sub if _section_sub else ''}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f"<div style='display:flex;align-items:center;gap:8px;margin:12px 0 8px 8px;'>"
    f"<div style='width:6px;height:6px;border-radius:50%;background:linear-gradient(135deg,#F59E0B,#EC4899,#8B5CF6);'></div>"
    f"<div style='color:#A8A29E;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;'>Sections</div>"
    f"</div>",
    unsafe_allow_html=True,
)
for _label, _key in [("Ventes","nav_v"),("Clients","nav_c"),("Stock & Achats","nav_s"),("Trésorerie","nav_t"),("AI Agent","nav_d")]:
    _active = section == _label
    if st.sidebar.button(_label, key=_key, use_container_width=True, type="primary" if _active else "secondary"):
        st.session_state.section = _label
        st.rerun()

st.sidebar.markdown("---")

# ── Global KPI helpers (shared across all sections) ──
def _delta_html(cur, prev):
    if not prev:
        return "<span class='kpi-delta-neu'>—</span>"
    pct = (cur - prev) / prev * 100
    cls = "kpi-delta-pos" if pct >= 0 else "kpi-delta-neg"
    arrow = "▲" if pct >= 0 else "▼"
    sign = "+" if pct >= 0 else ""
    return f"<span class='{cls}'>{arrow} {sign}{pct:.1f}%</span>"

def _kpi_card(icon, title, value, delta_html=""):
    return f"""
    <div class='kpi-card'>
        <div class='kpi-head'>
            <span class='kpi-icon'>{icon}</span>
            <span class='kpi-title'>{title}</span>
        </div>
        <div class='kpi-value'>{value}</div>
        <div class='kpi-sub'>{delta_html}</div>
    </div>
    """

# ===========================================================================
# 1. VENTES — KPI + graphiques
# ===========================================================================
if section == "Ventes":

    # ---------- Préparation des coûts (pour la marge réelle) -------------
    pi_all = data["PurchaseItems"].copy()
    if not pi_all.empty:
        pi_all["q"] = pd.to_numeric(pi_all["quantity"], errors="coerce").fillna(0)
        pi_all["p"] = pd.to_numeric(pi_all["price"], errors="coerce").fillna(0)
        pi_all["cost_total"] = pi_all["q"] * pi_all["p"]
        pu_status = data["Purchases"]["status"].fillna("").str.lower()
        pu_ok_ids = set(data["Purchases"].loc[pu_status.isin(["confirmed", "received", "completed", "paid", "paye", "recu"]), "id"].unique())
        pi_all = pi_all[pi_all["purchase_id"].isin(pu_ok_ids)]
        _g = pi_all.groupby("product_id").apply(
            lambda g: (g["cost_total"].sum() / g["q"].sum()) if g["q"].sum() > 0 else np.nan
        ).reset_index(name="unit_cost")
        cost_map = dict(zip(_g["product_id"], _g["unit_cost"]))
    else:
        cost_map = {}
    def _enrich_with_cost(df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["unit_cost"] = d["product_id"].map(cost_map).fillna(0)
        d["margin_real"] = ((pd.to_numeric(d["item_price"], errors="coerce").fillna(0)
                            - d["unit_cost"]) * d["quantity"].fillna(0))
        refund_qty = pd.to_numeric(d["refund_quantity"], errors="coerce").fillna(0)
        d["margin_refund"] = ((pd.to_numeric(d["item_price"], errors="coerce").fillna(0)
                             - d["unit_cost"]) * refund_qty)
        d["margin_net"] = d["margin_real"].fillna(0) - d["margin_refund"].fillna(0)
        d["margin_net"] = d["margin_net"].where(d["margin_real"].notna(), float("nan"))
        return d
    sf_cur_v  = _enrich_with_cost(sf_cur)
    sf_prev_v = _enrich_with_cost(sf_prev)
    sales_cur_unique  = sf_cur.drop_duplicates("sale_id")
    sales_prev_unique = sf_prev.drop_duplicates("sale_id")
    sales_cur_unique = sales_cur_unique[sales_cur_unique["sale_total"] > 0]
    sales_prev_unique = sales_prev_unique[sales_prev_unique["sale_total"] > 0]
    revenu_cur   = sales_cur_unique["sale_total"].sum()
    revenu_prev  = sales_prev_unique["sale_total"].sum()
    ca_items_cur   = sf_cur_v["item_total"].fillna(0).sum()
    ca_items_prev  = sf_prev_v["item_total"].fillna(0).sum() if not sf_prev_v.empty else 0
    croissance     = ((ca_items_cur - ca_items_prev) / ca_items_prev * 100) if ca_items_prev else 0.0
    qte_cur        = (sf_cur_v["quantity"].fillna(0) - sf_cur_v["refund_quantity"].fillna(0)).sum()
    marge_cur      = sf_cur_v["margin_net"].sum()
    marge_prev     = sf_prev_v["margin_net"].sum()
    taux_marge     = (marge_cur / ca_items_cur * 100) if ca_items_cur else 0.0
    # --------- PREPARE ALL CHART DATA FOR JS CROSS-FILTERING ----------
    import json as _json
    import base64

    # Build client region and client city mappings for JS
    _client_region_map = {}
    _client_city_map = {}
    _geojson_path = Path(__file__).parent / "maroc.geojson"
    _villes_path = Path(__file__).parent / "villes.json"
    _has_geo = _geojson_path.exists() and _villes_path.exists()
    if _has_geo:
        with open(_villes_path, "r", encoding="utf-8") as _f:
            _vdata = _json.load(_f)
        _vdf = pd.DataFrame(_vdata)
        _vdf["ville_norm"] = (_vdf["ville"].astype(str).str.strip()
                              .str.normalize("NFKD").str.encode("ascii", "ignore")
                              .str.decode("ascii").str.lower())
        _vdf["region_code"] = _vdf["region"].astype(str)
        _region_map = {"1": "Tanger-Tetouan-Hoceima", "2": "Oriental",
                       "3": "Fes-Meknes", "4": "Rabat-Sale-Kenitra",
                       "5": "Beni Mellal-Khenifra", "6": "Casablanca-Settat",
                       "7": "Marrakech-Safi", "8": "Daraa-Tafilelt",
                       "9": "Souss Massa", "10": "Guelmim-Oued Noun",
                       "11": "Laayoune-Saguia Hamra", "12": "Dakhla-Oued Eddahab"}
        _vdf["region_nom"] = _vdf["region_code"].map(_region_map).fillna(_vdf["region"])
        _cli_addr = data["Clients"][["id", "address"]].rename(columns={"id": "client_id", "address": "city_raw"})
        _cli_addr["city_norm"] = (_cli_addr["city_raw"].fillna("").astype(str).str.strip()
                                  .str.lower().str.normalize("NFKD")
                                  .str.encode("ascii", "ignore").str.decode("ascii"))
        _cm = _cli_addr.merge(_vdf[["ville_norm", "region_nom"]], left_on="city_norm", right_on="ville_norm", how="left")
        _client_region_map = _cm.dropna(subset=["region_nom"]).set_index("client_id")["region_nom"].to_dict()
    _cli_city = data["Clients"][["id", "address"]].rename(columns={"id": "client_id"}).copy()
    _cli_city["city"] = _cli_city["address"].fillna("").astype(str).str.split(",").str[-1].str.strip()
    _client_city_map = _cli_city.set_index("client_id")["city"].to_dict()
    # Export raw sales data for JS
    _sf_js = sf_cur_v.copy()
    for _c in _sf_js.select_dtypes(['datetime64[ns]', 'datetime64']).columns:
        _sf_js[_c] = _sf_js[_c].astype(str)
    _sf_js['region'] = _sf_js['client_id'].map(_client_region_map).fillna('')
    _sf_js['city'] = _sf_js['client_id'].map(_client_city_map).fillna('')
    _keep_cols = ['sale_id', 'product_name', 'category_name', 'client_name',
                  'sale_date', 'item_total', 'quantity', 'refund_quantity',
                  'margin_real', 'margin_net', 'product_id', 'client_id', 'region', 'city', 'sale_total']
    _keep_cols = [c for c in _keep_cols if c in _sf_js.columns]
    _sf_json = _sf_js[_keep_cols].to_json(orient='records', date_format='iso').replace('</','<\\/')
    # Export payments
    _pay_js = pay_cur.copy()
    if 'created_at' in _pay_js.columns:
        _pay_js['created_at'] = _pay_js['created_at'].astype(str)
    _pay_json = _pay_js.to_json(orient='records', date_format='iso').replace('</','<\\/') if len(_pay_js) else '[]'
    # GeoJSON for map
    _geojson_json = 'null'
    if _has_geo:
        with open(_geojson_path, "r", encoding="utf-8") as _f:
            _geojson_json = _f.read().replace('</','<\\/')
    # KPI snapshot for JS
    _kpi_json = _json.dumps({
        'revenu': float(revenu_cur) if revenu_cur else 0,
        'croissance': float(croissance) if croissance is not None else 0,
        'qte': float(qte_cur) if qte_cur else 0,
        'marge': float(marge_cur) if marge_cur else 0,
        'taux_marge': float(taux_marge) if taux_marge else 0,
        'revenu_prev': float(revenu_prev) if revenu_prev else 0,
        'revenu_prev_items': float(ca_items_prev) if ca_items_prev else 0,
    })
    
    # ========== REACT APP INTEGRATION ==========
    _react_dist = Path(__file__).parent / "ventes-app" / "dist" / "index.html"
    _react_available = _react_dist.exists()
    if _react_available:
        _prev_js = sf_prev_v.copy()
        for _c in _prev_js.select_dtypes(['datetime64[ns]', 'datetime64']).columns:
            _prev_js[_c] = _prev_js[_c].astype(str)
        if 'client_id' in _prev_js.columns:
            _prev_js['region'] = _prev_js['client_id'].map(_client_region_map).fillna('')
            _prev_js['city'] = _prev_js['client_id'].map(_client_city_map).fillna('')
        _keep_prev = [c for c in _keep_cols if c in _prev_js.columns]
        _prev_json = _prev_js[_keep_prev].to_json(orient='records', date_format='iso').replace('</','<\\/') if len(_prev_js) else '[]'
        _meta_json = _json.dumps({
            'annee': int(annee),
            'annee_selection': str(annee),
            'mois_selection': mois_selection,
            'start_dt': start_dt.isoformat(),
            'end_dt': end_dt.isoformat(),
        })
        _devis_raw = data.get("Devis", pd.DataFrame()).copy()
        _devis_cur = in_period(_devis_raw, "created_at", start_dt, end_dt)
        if not _devis_cur.empty and _devis_cur["total"].sum() > 0:
            _clients_d = data["Clients"][["id", "name"]].rename(columns={"id": "client_id", "name": "client_name"})
            _devis_cur = _devis_cur.merge(_clients_d, on="client_id", how="left")
            _devis_js = _devis_cur.to_json(orient='records', date_format='iso').replace('</','<\\/')
        else:
            _devis_js = '[]'
        _react_html = _react_dist.read_text(encoding='utf-8')
        _pu_js = pu_cur.copy()
        for _c in _pu_js.select_dtypes(['datetime64[ns]', 'datetime64']).columns:
            _pu_js[_c] = _pu_js[_c].astype(str)
        _pu_json = _pu_js.to_json(orient='records', date_format='iso').replace('</','<\\/') if len(_pu_js) else '[]'
        _data_script = (
            f'<script>\n'
            f'window.__DATA__={_sf_json};\n'
            f'window.__PREV_DATA__={_prev_json};\n'
            f'window.__PAY__={_pay_json};\n'
            f'window.__GEOJSON__={_geojson_json};\n'
            f'window.__META__={_meta_json};\n'
            f'window.__SECTION__="ventes";\n'
            f'window.__PURCHASES__={_pu_json};\n'
            f'window.__DEVIS__={_devis_js};\n'
            f'window.__STOCK_PRODUCTS__=[];\n'
            f'window.__STOCK_MOVEMENTS__=[];\n'
            f'window.__STOCK_REFUNDS__=[];\n'
            f'</script>\n'
        )
        _react_html = _react_html.replace(
            '<script type="module" crossorigin>',
            _data_script + '<script type="module" crossorigin>'
        )
    else:
        _react_html = None
    
    # ========== CROSS-FILTERING JS ENGINE ==========
    _js_template = r"""
    (function(){
    'use strict';
    // ---- DATA ----
    const RAW_DATA = %RAW_DATA%;
    const RAW_PAY = %RAW_PAY%;
    const GEOJSON = %GEOJSON%;
    const REGION_NAMES = %REGION_NAMES%;
    const KPI_BASE = %KPI_BASE%;
    const FILTER_LABELS = {"region":"Region","mois":"Mois","produit":"Produit","categorie":"Categorie","paiement":"Paiement","date":"Date"};
    let legend = null;
    // ---- DIMENSION DETECTION ----
    function detectDim(chartEl) {
        const pid = chartEl.closest('[id^="chart-"]')?.id || '';
        const map = {
            'chart-g4': 'categorie', 'chart-g8': 'paiement', 'chart-g5': 'produit',
            'chart-g3': 'region', 'chart-g6': 'mois', 'chart-g9': 'region'
        };
        for (const [prefix, dim] of Object.entries(map)) {
            if (pid.startsWith(prefix)) return dim;
        }
        return 'unknown';
    }
    // ---- DATA HELPERS ----
    function groupSum(data, key, val) {
        const m = {};
        data.forEach(r => { const k = r[key] || '(N/A)'; m[k] = (m[k]||0) + (+r[val]||0); });
        return Object.entries(m).map(([k,v]) => ({[key]:k, [val]:v})).sort((a,b) => b[val]-a[val]);
    }
    function filterData(data, dim, val) {
        if (!dim || !val) return data;
        if (dim === 'region') return data.filter(r => r['region'] === val);
        if (dim === 'categorie') return data.filter(r => (r['category_name']||'') === val);
        if (dim === 'produit') return data.filter(r => (r['product_name']||'') === val);
        if (dim === 'paiement') {
            const payIds = RAW_PAY.filter(p => (p['method']||'').trim().toLowerCase() === val.trim().toLowerCase()).map(p => p['sale_id']);
            return data.filter(r => payIds.includes(r['sale_id']));
        }
        if (dim === 'date') return data.filter(r => String(r['sale_date']||'').startsWith(val));
        if (dim === 'mois') {
            const m = parseInt(val,10);
            return data.filter(r => { const d = new Date(r['sale_date']); return d.getMonth()+1 === m; });
        }
        return data;
    }
    // ---- KPI UPDATE ----
    function updateKPIs(filtered, allSales) {
        const uniq = {};
        filtered.forEach(r => { if (r['sale_id']) uniq[r['sale_id']] = r; });
        const su = Object.values(uniq);
        const rev = su.reduce((s,r) => s + (+r['sale_total']||0), 0);
        const revItems = filtered.reduce((s,r) => s + (+r['item_total']||0), 0);
        const qte = filtered.reduce((s,r) => s + ((+r['quantity']||0) - (+r['refund_quantity']||0)), 0);
        const mrg = filtered.reduce((s,r) => s + (+r['margin_net']||0), 0);
        const rp = KPI_BASE.revenu_prev;
        const croiss = rp ? ((revItems - (KPI_BASE.revenu_prev_items || rp)) / (KPI_BASE.revenu_prev_items || rp) * 100) : 0;
        const tm = revItems ? (mrg / revItems * 100) : 0;
        const cards = document.querySelectorAll('.kpi-card');
        const vals = [
            revItems.toLocaleString('fr-FR', {minimumFractionDigits:0, maximumFractionDigits:0}),
            croiss !== null ? (croiss >= 0 ? '+' : '') + croiss.toFixed(1) + '%' : '0.0%',
            qte.toLocaleString('fr-FR'),
            mrg.toLocaleString('fr-FR'),
            tm.toFixed(1) + '%'
        ];
        cards.forEach((card, i) => {
            if (i < vals.length) {
                const valEl = card.querySelector('.kpi-value');
                if (valEl) valEl.textContent = vals[i];
            }
        });
        if (cards.length > 1) {
            const subEl = cards[1].querySelector('.kpi-sub');
            if (subEl) subEl.innerHTML = 'vs periode prec.';
        }
    }
    // ---- RENDER ALL CHARTS ----
    function renderAll(filtered, dim, val) {
        const all = RAW_DATA;
        const hasFilter = dim && val;
        // G1: Sales by day
        const g1El = document.querySelector('#chart-g1 .js-plotly-plot');
        if (g1El) {
            const dayAgg = {};
            const start = new Date(Math.min(...all.map(r => new Date(r['sale_date']))));
            const end = new Date(Math.max(...all.map(r => new Date(r['sale_date']))));
            const days = [];
            for (let d = new Date(start); d <= end; d.setDate(d.getDate()+1)) {
                const key = d.toISOString().substring(0,10);
                days.push(key);
                dayAgg[key] = 0;
            }
            all.forEach(r => {
                const key = String(r['sale_date']).substring(0,10);
                if (dayAgg[key] !== undefined) dayAgg[key] += (+r['item_total']||0)/1000;
            });
            const fDayAgg = {};
            filtered.forEach(r => {
                const key = String(r['sale_date']).substring(0,10);
                if (fDayAgg[key] === undefined) fDayAgg[key] = 0;
                fDayAgg[key] += (+r['item_total']||0)/1000;
            });
            const x1 = days, y1 = days.map(d => fDayAgg[d] || 0);
            const y1full = days.map(d => dayAgg[d] || 0);
            const g1Data = [{
                type: 'scatter', mode: 'lines', name: 'Filtre',
                x: x1, y: y1, fill: 'tozeroy',
                line: {color: '#D97706', width: 2.5},
                fillcolor: 'rgba(217,119,6,0.2)',
                hovertemplate: '%{x|%d %b %Y}<br>%{y:,.0f}k<extra></extra>',
            }];
            if (dim || val) {
                g1Data.unshift({
                    type: 'scatter', mode: 'lines', name: 'Total',
                    x: x1, y: y1full, line: {color: '#57534E', width: 1.5, dash: 'dot'},
                    hovertemplate: '%{x|%d %b %Y}<br>%{y:,.0f}k<extra></extra>',
                });
            }
            Plotly.react(g1El, g1Data, {
                height: 320, margin: {l:10, r:10, t:40, b:30},
                plot_bgcolor: 'rgba(0,0,0,0)', paper_bgcolor: 'rgba(0,0,0,0)',
                font: {family: 'Inter, sans-serif', size: 11, color: '#FAFAF9'},
                hovermode: 'x unified',
                showlegend: dim || val ? true : false,
                legend: {orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center', yanchor: 'top'},
                xaxis: {tickformat: '%d', showgrid: false, tickangle: 0},
                yaxis: {tickformat: '.0f', showgrid: true, gridcolor: '#3C3528', nticks: 5},
            }, {transition: {duration: 500, easing: 'cubic-in-out'}});
        }
        // G4: Categories pie
        const g4El = document.querySelector('#chart-g4 .js-plotly-plot');
        if (g4El) {
            const catFull = groupSum(all, 'category_name', 'item_total');
            const catFilt = groupSum(filtered, 'category_name', 'item_total');
            const catMap = {};
            catFilt.forEach(c => catMap[c['category_name']] = c['item_total']);
            const labels = catFull.map(c => (c['category_name']||'(N/A)').slice(0,15));
            const values = catFull.map(c => c['item_total']);
            const pulls = catFull.map((c,i) => (catMap[c['category_name']] && i === 0) ? 0.05 : 0);
            const markerColors = ['#F59E0B','#FBBF24','#D97706','#B45309','#92400E','#78350F','#FCD34D','#FDE68A','#FEF3C7','#D4A017'];
            const pieColors = labels.map((l,i) => catMap[catFull[i]['category_name']] ? markerColors[i % markerColors.length] : '#D0D0D0');
            Plotly.react(g4El, [{
                type: 'pie', labels: labels, values: values,
                pull: pulls, hole: 0.0,
                textposition: 'inside', texttemplate: '%{percent:.1%}',
                marker: {colors: pieColors, line: {color: '#292524', width: 2}},
                textfont: {color: pieColors.map(c => c === '#D0D0D0' ? '#999' : '#FFF'), size: 10},
                domain: {x: [0.05, 0.95], y: [0.20, 0.98]},
            }], {
                height: 320, margin: {l:10, r:10, t:10, b:10},
                plot_bgcolor: 'rgba(0,0,0,0)', paper_bgcolor: 'rgba(0,0,0,0)',
                font: {family: 'Inter, sans-serif', size: 11, color: '#FAFAF9'},
                showlegend: true, legend: {orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center', yanchor: 'top'},
            }, {transition: {duration: 500}});
        }
        // G8: Payment methods
        const g8El = document.querySelector('#chart-g8 .js-plotly-plot');
        if (g8El && RAW_PAY.length) {
            const payAll = groupSum(RAW_PAY, 'method', 'amount');
            const payIds = new Set();
            filtered.forEach(r => payIds.add(r['sale_id']));
            const payFilt = RAW_PAY.filter(p => payIds.has(p['sale_id']));
            const payAgg = groupSum(payFilt, 'method', 'amount');
            const payMap = {};
            payAgg.forEach(p => payMap[p['method']] = p['amount']);
            const pLabels = payAll.map(p => (p['method']||'(N/A)').trim());
            const pVals = payAll.map(p => p['amount']/1000);
            const pMarkerColors = ['#F59E0B','#FBBF24','#D97706','#B45309','#92400E','#FCD34D'];
            const pFinalColors = pLabels.map((l,i) => payMap[l] ? pMarkerColors[i % pMarkerColors.length] : '#D0D0D0');
            const totalK = pVals.reduce((s,v) => s+v, 0);
            Plotly.react(g8El, [{
                type: 'pie', labels: pLabels, values: pVals,
                hole: 0.5, textinfo: 'label+percent',
                texttemplate: '%{label}<br>%{percent}',
                marker: {colors: pFinalColors, line: {color: '#292524', width: 2}},
                textfont: {size: 10, color: pFinalColors.map(c => c === '#D0D0D0' ? '#999' : '#FAFAF9')},
            }], {
                height: 320, margin: {l:10, r:10, t:50, b:60},
                plot_bgcolor: 'rgba(0,0,0,0)', paper_bgcolor: 'rgba(0,0,0,0)',
                font: {family: 'Inter, sans-serif', size: 11, color: '#FAFAF9'},
                annotations: [{text: '<b>Total</b><br>'+totalK.toFixed(0)+'k', x:0.5, y:0.5, showarrow:false, font:{size:11,color:'#FAFAF9'}}],
                showlegend: true, legend: {orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center', yanchor: 'top'},
            }, {transition: {duration: 500}});
        }
        // G5: Top products
        const g5El = document.querySelector('#chart-g5 .js-plotly-plot');
        if (g5El) {
            const prodAll = groupSum(all, 'product_name', 'item_total').slice(0,10);
            const prodFilt = groupSum(filtered, 'product_name', 'item_total');
            const prodMap = {};
            prodFilt.forEach(p => prodMap[p['product_name']] = p['item_total']);
            prodAll.sort((a,b) => a['item_total']-b['item_total']);
            const pNames = prodAll.map(p => (p['product_name']||'').slice(0,12));
            const pValsK = prodAll.map(p => p['item_total']/1000);
            const pColorsB = prodAll.map(p => prodMap[p['product_name']] ? '#D97706' : '#D0D0D0');
            const pOpac = prodAll.map(p => prodMap[p['product_name']] ? 1 : 0.35);
            Plotly.react(g5El, [{
                type: 'bar', x: pValsK, y: pNames, orientation: 'h',
                marker: {color: pColorsB, opacity: pOpac},
                text: pValsK.map(v => v.toFixed(0)+'k'),
                textposition: 'inside', insidetextanchor: 'middle',
                textfont: {size: 9, color: pOpac.map(o => o < 0.5 ? '#999' : 'white')},
                width: 0.85,
                hovertemplate: '%{y}<br>%{x:,.0f}k<extra></extra>',
            }], {
                height: 320, margin: {l:5, r:5, t:50, b:40},
                plot_bgcolor: 'rgba(0,0,0,0)', paper_bgcolor: 'rgba(0,0,0,0)',
                font: {family: 'Inter, sans-serif', size: 11, color: '#FAFAF9'},
                hovermode: 'y unified',
                xaxis: {title: null, tickformat: ',.0f', showgrid: true, gridcolor: '#3C3528', zeroline: false},
                yaxis: {title: null, autorange: 'reversed', tickfont: {size: 9}, showgrid: false},
                bargap: 0.05,
            }, {transition: {duration: 500}});
        }
        // G6: Ranking
        const g6El = document.querySelector('#chart-g6 .js-plotly-plot');
        if (g6El) {
            const dayAggAll = {}, dayAggFil = {};
            all.forEach(r => {
                const key = String(r['sale_date']).substring(0,10);
                dayAggAll[key] = (dayAggAll[key]||0) + (+r['item_total']||0);
            });
            filtered.forEach(r => {
                const key = String(r['sale_date']).substring(0,10);
                dayAggFil[key] = (dayAggFil[key]||0) + (+r['item_total']||0);
            });
            const allEntries = Object.entries(dayAggAll).sort((a,b) => b[1]-a[1]).slice(0,10);
            const g6labels = allEntries.map(e => e[0].substring(5));
            const g6full = allEntries.map(e => e[1]/1000);
            const g6filt = allEntries.map(e => (dayAggFil[e[0]]||0)/1000);
            const traces = [];
            if (hasFilter) {
                traces.push({type: 'bar', y: g6labels, x: g6full, orientation: 'h',
                    marker: {color: '#D0D0D0', opacity: 0.3}, width: 0.3,
                    hoverinfo: 'skip', showlegend: false});
            }
            traces.push({type: 'bar', y: g6labels, x: g6filt, orientation: 'h',
                marker: {color: g6filt, colorscale: [[0,'#78350F'],[0.5,'#D97706'],[1,'#FBBF24']]},
                text: g6filt.map(v => v.toFixed(0)+'k'),
                textposition: 'inside', insidetextanchor: 'middle',
                textfont: {size: 10, color: 'white'},
                width: 0.3,
                hovertemplate: '%{y}: %{x:,.0f}k<extra></extra>'});
            Plotly.react(g6El, traces, {
                height: 320, margin: {l:10, r:10, t:40, b:20},
                plot_bgcolor: 'rgba(0,0,0,0)', paper_bgcolor: 'rgba(0,0,0,0)',
                font: {family: 'Inter, sans-serif', size: 11, color: '#FAFAF9'},
                xaxis: {title: null, tickformat: ',.0f', showgrid: true, gridcolor: '#3C3528'},
                yaxis: {title: null, autorange: 'reversed', tickfont: {size: 10}, showgrid: false},
                bargap: 0.02,
            }, {transition: {duration: 500}});
        }
        // G2: Sales/Purchases/Margin
        const g2El = document.querySelector('#chart-g2 .js-plotly-plot');
        if (g2El) {
            const caAll = {}, caFil = {}, maFil = {};
            all.forEach(r => {
                const key = String(r['sale_date']).substring(0,10);
                caAll[key] = (caAll[key]||0) + (+r['item_total']||0)/1000;
            });
            filtered.forEach(r => {
                const key = String(r['sale_date']).substring(0,10);
                caFil[key] = (caFil[key]||0) + (+r['item_total']||0)/1000;
                maFil[key] = (maFil[key]||0) + (+r['margin_net']||0)/1000;
            });
            const allDates = Object.keys(caAll).sort();
            const caFull = allDates.map(d => caAll[d] || 0);
            const caVals = allDates.map(d => caFil[d] || 0);
            const maVals = allDates.map(d => maFil[d] || 0);
            const traces = [];
            if (hasFilter) {
                traces.push({type: 'bar', x: allDates, y: caFull, name: 'Total',
                    marker: {color: '#D0D0D0', opacity: 0.3},
                    hoverinfo: 'skip', showlegend: true});
            }
            traces.push({type: 'bar', x: allDates, y: caVals, name: 'Ventes',
                marker: {color: '#D97706'}, text: caVals.map(v => v.toFixed(0)+'k'),
                textposition: 'inside', insidetextanchor: 'middle', textfont: {size: 9, color: 'white'}});
            if (hasFilter) {
                const maAll = {};
                all.forEach(r => {
                    const key = String(r['sale_date']).substring(0,10);
                    maAll[key] = (maAll[key]||0) + (+r['margin_net']||0)/1000;
                });
                const maFull = allDates.map(d => maAll[d] || 0);
                traces.push({type: 'scatter', x: allDates, y: maFull, mode: 'lines+markers',
                    name: 'Marge (total)', yaxis: 'y2',
                    line: {color: '#D0D0D0', width: 1.5, dash: 'dot'},
                    marker: {symbol: 'circle', size: 4, color: '#D0D0D0'},
                    hoverinfo: 'skip', showlegend: true});
            }
            traces.push({type: 'scatter', x: allDates, y: maVals, mode: 'lines+markers',
                name: 'Marge', yaxis: 'y2',
                line: {color: '#FBBF24', width: 2.5, dash: 'dot'},
                marker: {symbol: 'circle', size: 6},
                hovertemplate: '%{x|%d %b %Y}<br>%{y:,.0f}k<extra></extra>'});
            Plotly.react(g2El, traces, {
                height: 320, margin: {l:5, r:5, t:60, b:30},
                plot_bgcolor: 'rgba(0,0,0,0)', paper_bgcolor: 'rgba(0,0,0,0)',
                font: {family: 'Inter, sans-serif', size: 11, color: '#FAFAF9'},
                hovermode: 'x unified',
                barmode: 'group', bargap: 0.05, bargroupgap: 0.02,
                showlegend: true, legend: {orientation: 'h', y: 1.1, x: 0.5, xanchor: 'center', yanchor: 'top'},
                yaxis: {title: null, tickformat: '.0f', showgrid: true, gridcolor: '#3C3528', nticks: 5},
                yaxis2: {title: null, tickformat: '.0f', showgrid: false, overlaying: 'y', side: 'right', nticks: 5},
                xaxis: {title: null, tickformat: '%d', showgrid: false, tickangle: 0},
            }, {transition: {duration: 500}});
        }
        // G3: Map
        const g3El = document.querySelector('#chart-g3 .js-plotly-plot');
        if (g3El && GEOJSON) {
            const regAll = {}, regFil = {};
            all.forEach(r => { const reg = r['region'] || ''; regAll[reg] = (regAll[reg]||0) + (+r['item_total']||0); });
            filtered.forEach(r => { const reg = r['region'] || ''; regFil[reg] = (regFil[reg]||0) + (+r['item_total']||0); });
            const geojsonRegions = (GEOJSON.features || []).map(f => f.properties?.region || '');
            const regionNames = geojsonRegions.length ? geojsonRegions : Object.keys(regAll);
            const maxCA = Math.max(...regionNames.map(r => regAll[r] || 0), 1);
            const zVals = regionNames.map(reg => {
                const hasData = regFil[reg] && regFil[reg] > 0;
                if (!hasFilter) return (regAll[reg]||0) / maxCA;
                return hasData ? (regAll[reg]||0) / maxCA : 0;
            });
            const mapText = regionNames.map(reg => {
                const ca = (regAll[reg]||0)/1000;
                const fil = (regFil[reg]||0)/1000;
                return reg+'<br>'+ca.toFixed(0)+'k'+(hasFilter ? ' (filtr: '+fil.toFixed(0)+'k)' : '');
            });
            Plotly.react(g3El, [{
                type: 'choropleth', locations: regionNames, z: zVals,
                geojson: GEOJSON, featureidkey: 'properties.region',
                colorscale: hasFilter ? [[0,'#E8E8E8'],[0.001,'#E8E8E8'],[0.001,'#440154'],[0.2,'#3B528B'],[0.5,'#21918C'],[1,'#FDE725']] : 'Viridis',
                text: mapText, hoverinfo: 'text',
                colorbar: {title: 'CA', thickness: 12, len: 0.6, x: 0.92, y: 0.5},
                marker: {line: {color: '#292524', width: 1}},
            }], {
                height: 320, margin: {l:0, r:0, t:0, b:0},
                geo: {bgcolor: 'rgba(0,0,0,0)', fitbounds: 'locations', visible: false,
                      projection: {type: 'mercator'}, lonaxis: {range: [-13,-2]}, lataxis: {range: [27,36]}, resolution: 50},
            }, {transition: {duration: 500}});
        }
    }
    }
    // ---- APPLY FILTER STYLE (Plotly.restyle) ----
    let _activeDim = null, _activeVal = null;
    function applyCrossFilterStyle() {
        const dim = _activeDim;
        const val = _activeVal;
        const isActive = dim && val;
        const filtered = isActive ? filterData(RAW_DATA, dim, val) : RAW_DATA;
        // Gray out all traces in a chart
        function grayOut(el) {
            if (!el || !el.data) return;
            for (let i = 0; i < el.data.length; i++) {
                const tr = el.data[i];
                if (tr.type === 'bar') {
                    Plotly.restyle(el, {'marker.color': ['rgba(120,113,108,0.25)'], 'marker.opacity': [0.5]}, [i]);
                } else if (tr.type === 'scatter' || tr.type === 'scattergl') {
                    Plotly.restyle(el, {'line.color': ['rgba(120,113,108,0.3)'], 'marker.color': ['rgba(120,113,108,0.3)'], 'marker.opacity': [0.4]}, [i]);
                } else if (tr.type === 'pie') {
                    Plotly.restyle(el, {'marker.colors': [tr.labels.map(() => '#A8A29E')]}, [i]);
                }
            }
        }
        // ---- Apply or clear filter for each chart ----
        if (isActive) {
            const chartIds = ['chart-g1','chart-g2','chart-g3','chart-g4','chart-g5','chart-g6','chart-g8','chart-g9'];
            chartIds.forEach(cid => {
                const el = document.querySelector('#' + cid + ' .js-plotly-plot');
                if (el) grayOut(el);
            });
        } else {
            window.location.reload();
            return;
        }
        // ---- Pie charts: selectively color matching slices ----
        if (isActive) {
            // G4: Categories pie
            const g4El = document.querySelector('#chart-g4 .js-plotly-plot');
            if (g4El && g4El.data && g4El.data[0] && g4El.data[0].type === 'pie') {
                const d = g4El.data[0];
                const labels = d.labels || [];
                const activeCats = new Set(filtered.map(r => r['category_name']));
                const colors = labels.map(l => {
                    const match = RAW_DATA.filter(r => (r['category_name']||'').slice(0,15) === l);
                    return match.some(r => activeCats.has(r['category_name'])) ? '#D97706' : '#A8A29E';
                });
                Plotly.restyle(g4El, {'marker.colors': [colors]}, [0]);
            }
            // G8: Payment methods pie
            const g8El = document.querySelector('#chart-g8 .js-plotly-plot');
            if (g8El && g8El.data && g8El.data[0] && g8El.data[0].type === 'pie') {
                const d = g8El.data[0];
                const labels = d.labels || [];
                const saleIds = new Set(filtered.map(r => r['sale_id']));
                const activeMeths = new Set(RAW_PAY.filter(p => saleIds.has(p['sale_id'])).map(p => (p['method']||'').trim()));
                const colors = labels.map(l => activeMeths.has(l) ? '#D97706' : '#A8A29E');
                Plotly.restyle(g8El, {'marker.colors': [colors]}, [0]);
            }
        }
        // Update KPIs
        updateKPIs(filtered, RAW_DATA);
        // Update filter badge
        const root = document.getElementById('_cf_root');
        if (root) {
            if (dim && val) {
                const label = FILTER_LABELS[dim] || dim;
                root.innerHTML = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding:6px 12px;background:#292524;border-radius:8px;font-size:12px;border:1px solid #44403C;">' +
                    '<span style="font-weight:600;color:#D97706;">' + label + ':</span> ' +
                    '<span style="color:#FAFAF9;">' + val + '</span>' +
                    '<span id="_cf_clear" style="margin-left:auto;cursor:pointer;font-weight:700;color:#A8A29E;font-size:14px;">Ã—</span></div>';
                document.getElementById('_cf_clear').onclick = function() {
                    _activeDim = null;
                    _activeVal = null;
                    localStorage.removeItem('_cf_filter');
                    applyCrossFilterStyle();
                };
            } else {
                root.innerHTML = '';
            }
        }
    }
    // ---- HANDLE CLICK ----
    function handleClick(data, chartEl) {
        const pt = data.points[0];
        if (!pt) return;
        const dim = detectDim(chartEl);
        if (dim === 'unknown') return;
        let val = '';
        if (dim === 'region') val = pt.location || pt.label || '';
        else if (dim === 'mois') {
            val = pt.y || pt.label || '';
            const moisFR = ['Janvier','Février','Mars','Avril','Mai','Juin',
                            'Juillet','Aout','Septembre','Octobre','Novembre','Decembre'];
            const idx = moisFR.indexOf(val);
            val = idx >= 0 ? String(idx+1) : val;
        }
        else val = pt.label || pt.x || pt.y || pt.location || '';
        val = String(val).trim();
        if (!val) return;
        // Toggle filter
        if (_activeDim === dim && _activeVal === val) {
            _activeDim = null;
            _activeVal = null;
            localStorage.removeItem('_cf_filter');
        } else {
            _activeDim = dim;
            _activeVal = val;
            localStorage.setItem('_cf_filter', dim + ':' + val);
        }
        const fDim = _activeDim, fVal = _activeVal;
        const filtered = fDim && fVal ? filterData(RAW_DATA, fDim, fVal) : RAW_DATA;
        renderAll(filtered, fDim, fVal);
        updateKPIs(filtered, RAW_DATA);
        const root = document.getElementById('_cf_root');
        if (root) {
            if (fDim && fVal) {
                const label = FILTER_LABELS[fDim] || fDim;
                root.innerHTML = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding:6px 12px;background:#292524;border-radius:8px;font-size:12px;border:1px solid #44403C;">' +
                    '<span style="font-weight:600;color:#D97706;">' + label + ':</span> ' +
                    '<span style="color:#FAFAF9;">' + fVal + '</span>' +
                    '<span id="_cf_clear" style="margin-left:auto;cursor:pointer;font-weight:700;color:#A8A29E;font-size:14px;">\u00d7</span></div>';
                document.getElementById('_cf_clear').onclick = function() {
                    _activeDim = null;
                    _activeVal = null;
                    localStorage.removeItem('_cf_filter');
                    const f2 = RAW_DATA;
                    renderAll(f2, null, null);
                    updateKPIs(f2, RAW_DATA);
                    document.getElementById('_cf_root').innerHTML = '';
                };
            } else {
                root.innerHTML = '';
            }
        }
    }
    // ---- INIT ----
    function initCrossFilter() {
        document.querySelectorAll('[id^="chart-"]').forEach(container => {
            const plotlyEl = container.querySelector('.js-plotly-plot');
            if (plotlyEl) {
                plotlyEl.on('plotly_click', function(data) { handleClick(data, this); });
            }
        });
        // Restore filter from localStorage
        const saved = localStorage.getItem('_cf_filter');
        if (saved && saved.includes(':')) {
            const [dim, val] = saved.split(':');
            _activeDim = dim;
            _activeVal = val;
            const filtered = filterData(RAW_DATA, dim, val);
            renderAll(filtered, dim, val);
            updateKPIs(filtered, RAW_DATA);
        }
    }
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(initCrossFilter, 500);
    } else {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(initCrossFilter, 500); });
    }
    })();
    """
    # Replace placeholders with actual JSON data
    _js_filled = (
        _js_template
        .replace('%RAW_DATA%', _sf_json)
        .replace('%RAW_PAY%', _pay_json)
        .replace('%GEOJSON%', _geojson_json)
        .replace('%REGION_NAMES%', _json.dumps(list(_region_map.values())).replace('</script>','<\\/script>') if _has_geo else '[]')
        .replace('%KPI_BASE%', _kpi_json.replace('</script>','<\\/script>'))
    )
    # Base64-encode to safely pass through Streamlit's React sanitizer
    import base64 as _b64
    _js_b64 = _b64.b64encode(_js_filled.encode('utf-8')).decode('ascii')
    _cf_html = (
        '<div id="_cf_root"></div>'
        '<img src=x onerror="'
        "(function(){"
        "var s=document.createElement('script');"
        "s.textContent=atob('" + _js_b64 + "');"
        "document.body.appendChild(s);"
        "this.remove();"
        "})()"
        '">'
    )

    if _react_html:
        try:
            st.components.v1.html(_react_html, height=1200, scrolling=True)
        except Exception as _e:
            st.error(f"Erreur lors du rendu React : {_e}")
    else:
        st.warning("Application de visualisation non trouvée (ventes-app/dist/index.html).")

# ===========================================================================
# 2. CLIENTS — Premium BI (9 chartes)
# ===========================================================================
if section == "Clients":
    cli = data["Clients"].copy()
    su = sf_cur.drop_duplicates("sale_id") if not sf_cur.empty else pd.DataFrame()

    total_clients = len(cli)
    new_clients = cli["created_at"].between(start_dt, end_dt).sum()
    active = su["client_id"].nunique() if not su.empty else 0
    inactive = total_clients - active
    ca_cli = su["sale_total"].sum() if not su.empty else 0
    nb_cmd = su["sale_id"].nunique() if not su.empty else 0
    panier = (ca_cli / nb_cmd) if nb_cmd else 0

    spacer(14)
    kc = st.columns(5)
    kc_cli = [
        ("👥", "Total clients",  f"{total_clients:,}", ""),
        ("🆕", "Nouveaux",        f"{new_clients:,}",  ""),
        ("✅", "Actifs",          f"{active:,}",       ""),
        ("💰", "CA clients",     _fmt(ca_cli),    ""),
        ("🛒", "Panier moyen",   _fmt(panier),    ""),
    ]
    for col, (ic, t, v, dh) in zip(kc, kc_cli):
        col.markdown(_kpi_card(ic, t, v, dh), unsafe_allow_html=True)

    spacer(10)

    # ── Global client filter ──
    cli_map = dict(zip(cli["name"], cli["id"]))
    cli_opts = ["Tous"] + sorted(k for k in cli_map if k and str(k).strip())
    sel_cli = st.selectbox("Client", cli_opts, key="cli_global_filter")
    cli_fid = None if sel_cli == "Tous" else cli_map[sel_cli]

    spacer(10)

    if sf_cur.empty:
        st.info("Aucune vente sur la période.")
    else:
        # Row 1 ─ Évolution portefeuille | Fidélité | Top 10 clients
        r1c1, r1c2, r1c3 = st.columns([1.0, 0.7, 0.7])
        with r1c1:
            nb_jours = (end_dt - start_dt).days
            freq_c, x_label_c = ("D", "Jour") if nb_jours <= 31 else ("M", "Mois")
            section_title("Évolution du portefeuille clients")
            rows = []
            if freq_c == "D":
                periods = pd.date_range(start_dt, end_dt, freq="D")
                for d in periods:
                    cumul = int((cli["created_at"].dt.date <= d.date()).sum())
                    nouveaux = int((cli["created_at"].dt.date == d.date()).sum())
                    rows.append({"label": d.strftime("%d/%m"), "nouveaux": nouveaux, "cumul": cumul})
            else:
                periods = pd.date_range(start_dt, end_dt, freq="MS")
                for ps in periods:
                    pe = ps + pd.offsets.MonthEnd(0)
                    cumul = int((cli["created_at"] <= pe).sum())
                    nouveaux = int(((cli["created_at"] >= ps) & (cli["created_at"] <= pe)).sum())
                    rows.append({"label": ps.strftime("%b"), "nouveaux": nouveaux, "cumul": cumul})
            agg = pd.DataFrame(rows)
            agg["Total"] = agg["cumul"] - agg["nouveaux"]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=agg["label"], y=agg["Total"],
                                 name="Total", marker_color="#B45309",
                                 hovertemplate="%{x}<br>Total : <b>%{y:,.0f}</b><extra></extra>"))
            fig.add_trace(go.Bar(x=agg["label"], y=agg["nouveaux"],
                                 name="Nouveaux", marker_color="#D97706",
                                 hovertemplate="%{x}<br>Nouveaux : <b>%{y:,.0f}</b><extra></extra>"))
            fig.add_trace(go.Scatter(x=agg["label"], y=agg["cumul"],
                                     name="Évolution", mode="lines+markers",
                                     line=dict(color=ACCENT, width=3),
                                     marker=dict(size=6, color=ACCENT),
                                     hovertemplate="%{x}<br>Cumul : <b>%{y:,.0f}</b><extra></extra>"))
            fig.update_layout(barmode="stack", bargap=0.2)
            st.plotly_chart(style_fig(fig, 220), key="cli_chart_1",
                            use_container_width=True)

        with r1c2:
            section_title("Fidélité client")
            sd = data["Sales"].dropna(subset=["client_id"]).copy()
            sd["mois"] = pd.to_datetime(sd["created_at"]).dt.to_period("M")
            cm = sd.groupby("client_id")["mois"].nunique()
            fideles = int((cm >= 2).sum())
            occasionnels = int((cm == 1).sum())
            jamais = total_clients - fideles - occasionnels
            lbls, vals, colors = [], [], []
            if fideles:
                lbls.append("Fidèles"); vals.append(fideles); colors.append(PRIMARY)
            if occasionnels:
                lbls.append("Occasionnels"); vals.append(occasionnels); colors.append(ACCENT)
            if jamais:
                lbls.append("Jamais acheté"); vals.append(jamais); colors.append(GRID)
            if cli_fid:
                cli_mois = sd[sd["client_id"] == cli_fid]["mois"].nunique()
                if cli_mois >= 2:
                    cat_idx = lbls.index("Fidèles") if "Fidèles" in lbls else -1
                elif cli_mois == 1:
                    cat_idx = lbls.index("Occasionnels") if "Occasionnels" in lbls else -1
                else:
                    cat_idx = lbls.index("Jamais acheté") if "Jamais acheté" in lbls else -1
                colors = [c if i == cat_idx else "rgba(128,128,128,0.15)" for i, c in enumerate(colors)]
            fig = go.Figure(data=[go.Pie(
                labels=lbls, values=vals, hole=0,
                marker_colors=colors, textinfo="value+percent")])
            fig = style_fig(fig, 220, pie=True)
            fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig, key="cli_chart_2",
                            use_container_width=True)

        with r1c3:
            section_title("Top 10 clients — CA")
            agg = (su.groupby(["client_id", "client_name"], dropna=False)
                   .agg(CA=("sale_total", "sum")).reset_index()
                   .sort_values("CA", ascending=False).head(10))
            agg["CA"] = agg["CA"].fillna(0)
            agg["CA_k"] = agg["CA"] / 1000
            agg["CA_k_label"] = agg["CA"].apply(_fmt).tolist()
            fig = go.Figure()
            clr = agg["CA_k"]
            max_k = agg["CA_k"].max()
            fig.add_trace(go.Bar(y=agg["client_name"], x=agg["CA_k"], orientation="h",
                marker=dict(color=clr, colorscale=[[0, '#D97706'], [1, '#FBBF24']], showscale=False),
                text=agg["CA_k_label"], textposition="outside",
                texttemplate="%{text}",
                textfont=dict(size=10, color="#FFFFFF"),
                hovertemplate="%{y}: %{x:,.1f}k<extra></extra>"))
            if cli_fid:
                opacity = [1.0 if c == cli_fid else 0.15 for c in agg["client_id"]]
                fig.update_traces(marker=dict(opacity=opacity))
                cli_name_row = agg.loc[agg["client_id"] == cli_fid, "client_name"]
                if not cli_name_row.empty:
                    fig.update_layout(title=dict(text=f"Top 10 CA — {cli_name_row.iloc[0]}"))
            fig.update_layout(height=220, margin=dict(l=10, r=30, t=35, b=10),
                xaxis=dict(ticksuffix="k", tickformat=",.0f", showgrid=True, gridcolor="#3C3528", tickfont=dict(color="#A8A29E"), range=[0, max_k * 1.25]),
                yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#A8A29E"), showgrid=False),
                plot_bgcolor="#292524", paper_bgcolor="#292524", bargap=0.04, bargroupgap=0.02,
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"))
            fig.update_traces(cliponaxis=False)
            st.plotly_chart(fig, key="cli_chart_3", use_container_width=True)

        spacer(15)

        # Row 2 ─ Répartition géographique | Encaissé vs Impayé | Retours par client
        r2c1, r2c2, r2c3 = st.columns([1.0, 0.8, 0.7])
        with r2c1:
            section_title("Répartition géographique")
            try:
                vp = Path(__file__).parent / "villes.json"
                if vp.exists():
                    import json as _j
                    with open(vp, "r", encoding="utf-8") as _f:
                        _vd = _j.load(_f)
                    _vdf = pd.DataFrame(_vd)
                    _vdf["ville_norm"] = (_vdf["ville"].astype(str).str.strip()
                                          .str.normalize("NFKD")
                                          .str.encode("ascii", "ignore")
                                          .str.decode("ascii").str.lower())
                    _rmap = {"1": "Tanger-Tétouan-Al Hoceïma", "2": "Oriental",
                             "3": "Fès-Meknès", "4": "Rabat-Salé-Kénitra",
                             "5": "Béni Mellal-Khénifra", "6": "Casablanca-Settat",
                             "7": "Marrakech-Safi", "8": "Drâa-Tafilalet",
                             "9": "Souss-Massa", "10": "Guelmim-Oued Noun",
                             "11": "Laâyoune-Sakia El Hamra", "12": "Dakhla-Oued Ed-Dahab"}
                    _vdf["region_nom"] = _vdf["region"].astype(str).map(_rmap)
                    _ct = cli[["id", "address"]].copy()
                    _ct["city_raw"] = (_ct["address"].fillna("").astype(str)
                                       .str.split(",").str[-1].str.strip())
                    _ct["city_norm"] = (_ct["city_raw"].str.lower()
                                        .str.normalize("NFKD")
                                        .str.encode("ascii", "ignore")
                                        .str.decode("ascii"))
                    _mrg = _ct.merge(_vdf[["ville_norm", "region_nom"]],
                                     left_on="city_norm", right_on="ville_norm",
                                     how="left")
                    _rc = _mrg["region_nom"].fillna("Autre").value_counts().head(10)
                    _rc = _rc.reset_index(name="clients")
                    _rc.columns = ["region", "clients"]
                    if cli_fid:
                        _m = _mrg[_mrg["id"] == cli_fid]
                        _cli_region = _m["region_nom"].iloc[0] if not _m.empty else float("nan")
                        if pd.isna(_cli_region) or not str(_cli_region).strip():
                            _cli_region = str(_ct.loc[_ct["id"] == cli_fid, "city_raw"].iloc[0]) if not _ct.loc[_ct["id"] == cli_fid].empty else ""
                else:
                    _ct = cli[["id", "address"]].copy()
                    _ct["city"] = (_ct["address"].fillna("").astype(str)
                                   .str.split(",").str[-1].str.strip())
                    _rc = _ct["city"].value_counts().head(10).reset_index(name="clients")
                    _rc.columns = ["region", "clients"]
                    _cli_region = ""
                    if cli_fid:
                        _cli_region = str(_ct.loc[_ct["id"] == cli_fid, "city"].iloc[0]) if not _ct.loc[_ct["id"] == cli_fid].empty else ""
                _rc = _rc.sort_values("clients", ascending=True)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=_rc["region"], y=_rc["clients"],
                    marker=dict(color=PRIMARY),
                    hovertemplate="%{x}<br>Clients: %{y}<extra></extra>"))
                if cli_fid and str(_cli_region).strip():
                    _mask = _rc["region"].astype(str).str.lower() == str(_cli_region).strip().lower()
                    if any(_mask):
                        fig.update_traces(marker=dict(opacity=[1.0 if m else 0.15 for m in _mask]),
                                          selector=dict(type="bar"))
                st.plotly_chart(style_fig(fig, 220), key="cli_chart_4",
                                use_container_width=True)
            except Exception:
                st.info("Données géographiques non disponibles.")

        with r2c2:
            section_title("Encaissé vs Impayé")
            try:
                sv = su[["client_id", "sale_total"]].dropna(subset=["client_id"]).copy()
                sv["sale_total"] = pd.to_numeric(sv["sale_total"], errors="coerce").fillna(0)
                pa = pay_cur.copy()
                pa["amount"] = pd.to_numeric(pa["amount"], errors="coerce").fillna(0)
                pa = pa[pa["status"] == "approved"]
                if cli_fid:
                    sv = sv[sv["client_id"] == cli_fid]
                    pa = pa[pa["client_id"] == cli_fid]
                total_sales = sv["sale_total"].sum()
                total_paid = pa["amount"].sum()
                total_unpaid = max(0, total_sales - total_paid)
                if total_sales > 0 or total_paid > 0:
                    vals = [total_paid, total_unpaid]
                    lbls = ["Encaissé", "Impayé"]
                    clrs = [PRIMARY, NEGATIVE]
                    total_k = total_sales / 1000
                    fig = go.Figure(data=[go.Pie(labels=lbls, values=vals, hole=0.6,
                                                   marker_colors=clrs,
                                                   textinfo="percent")])
                    fig.add_annotation(text=f"<b>Total</b><br>{_fmt(total_sales)}", showarrow=False,
                                       font=dict(size=11, color=INK, family="Inter, sans-serif"),
                                       x=0.5, y=0.5)
                    fig.update_traces(hovertemplate="%{label}<br>%{value:,.0f} (%{percent})<extra></extra>")
                    fig = style_fig(fig, 220, pie=True)
                    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5))
                    st.plotly_chart(fig, key="cli_chart_8",
                                    use_container_width=True)
                else:
                    st.info("Aucune donnée.")
            except Exception:
                st.info("Données indisponibles.")

        with r2c3:
            section_title("Retours par client")
            if exclude_refunded:
                st.info("Aucun retour.")
            else:
                try:
                    rf = data["Refunds"].copy()
                    sv = sf_cur[["sale_id", "client_id"]].drop_duplicates("sale_id")
                    cn = data["Clients"][["id", "name"]].rename(
                        columns={"id": "client_id"})
                    rr = rf.merge(sv, on="sale_id", how="inner").merge(
                        cn, on="client_id", how="left")
                    rr["name"] = rr["name"].fillna("Client #" + rr["client_id"].astype(str))
                    if cli_fid:
                        rr = rr[rr["client_id"] == cli_fid]
                    if not rr.empty:
                        rr_agg = rr.groupby(["name", "client_id"]).size().reset_index(name="retours")
                        rr_agg = rr_agg.sort_values("retours", ascending=False).head(30)
                        if not rr_agg.empty:
                            fig = px.treemap(rr_agg, path=["name"], values="retours")
                            fig.update_traces(textinfo="label+value", textfont=dict(size=11, color=INK))
                            st.plotly_chart(style_fig(fig, 220), key="cli_chart_5",
                                            use_container_width=True)
                        else:
                            st.info("Aucun retour.")
                    else:
                        st.info("Aucun retour.")
                except Exception as e:
                    st.info(f"Retours non disponibles: {e}")

        spacer(15)

        # Row 3 ─ Délai moyen paiement | Fréquence d'achat
        r3c1, r3c2 = st.columns([1.0, 0.8])
        with r3c1:
            section_title("Délai moyen de paiement")
            try:
                ps = su[["sale_id", "client_id", "sale_date"]].copy()
                pp = pay_cur[["sale_id", "amount", "created_at"]].rename(
                    columns={"created_at": "pay_date"})
                mrg = ps.merge(pp, on="sale_id", how="inner")
                mrg["délai"] = (pd.to_datetime(mrg["pay_date"]) -
                                pd.to_datetime(mrg["sale_date"])).dt.days
                dd = (mrg.groupby("client_id")["délai"].mean()
                      .reset_index(name="délai_moyen").sort_values("délai_moyen", ascending=False))
                ci = data["Clients"][["id", "name"]].rename(
                    columns={"id": "client_id", "name": "client_name"})
                dd = dd.merge(ci, on="client_id", how="left")
                dd = dd.head(10)
                if not dd.empty:
                    dd = dd.sort_values("délai_moyen", ascending=True)
                    fig = px.bar(dd, x="client_name", y="délai_moyen",
                                 color="délai_moyen", color_continuous_scale="Reds_r")
                    if cli_fid:
                        _mask = list(dd["client_id"] == cli_fid)
                        fig.update_traces(marker=dict(opacity=[1.0 if m else 0.15 for m in _mask]),
                                          selector=dict(type="bar"))
                    fig.update_traces(texttemplate="%{y:.0f} j", textposition="outside",
                                      textfont=dict(size=10))
                    fig.update_layout(xaxis=dict(tickangle=45), coloraxis_showscale=False)
                    fig.update_yaxes(ticksuffix=" j")
                    st.plotly_chart(style_fig(fig, 220), key="cli_chart_7",
                                    use_container_width=True)
                else:
                    st.info("Aucune donnée de paiement.")
            except Exception:
                st.info("Délais non disponibles.")

        with r3c2:
            section_title("Fréquence d'achat")
            freq = (su.groupby("client_id")["sale_id"].nunique()
                    .reset_index(name="achats"))
            freq = freq.merge(data["Clients"][["id", "name"]].rename(
                columns={"id": "client_id"}), on="client_id", how="left")
            freq["name"] = freq["name"].fillna("Client #" + freq["client_id"].astype(str))
            freq["achats"] = freq["achats"].fillna(0).astype(int)
            freq = freq.sort_values("achats", ascending=False).head(20)
            fig = go.Figure()
            clr = freq["achats"]
            fig.add_trace(go.Bar(y=freq["name"], x=freq["achats"], orientation="h",
                marker=dict(color=clr, colorscale=[[0, '#D97706'], [1, '#FBBF24']], showscale=False),
                text=freq["achats"], textposition="outside",
                texttemplate="%{text}",
                textfont=dict(size=10, color="#FFFFFF"),
                hovertemplate="%{y}: %{x} cmd<extra></extra>"))
            if cli_fid:
                _mask = list(freq["client_id"] == cli_fid)
                fig.update_traces(marker=dict(opacity=[1.0 if m else 0.15 for m in _mask]))
            fig.update_layout(height=220, margin=dict(l=10, r=10, t=35, b=10),
                xaxis=dict(tickformat="d", showgrid=True, gridcolor="#3C3528", tickfont=dict(color="#A8A29E"), rangemode="tozero"),
                yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#A8A29E"), showgrid=False),
                plot_bgcolor="#292524", paper_bgcolor="#292524", bargap=0.04, bargroupgap=0.02,
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"))
            fig.update_traces(cliponaxis=False)
            st.plotly_chart(fig, key="cli_chart_6", use_container_width=True)

# ===========================================================================
# 3. STOCK & ACHATS — Premium BI Layout (filtre produit entre KPI et graphiques)
# ===========================================================================
if section == "Stock & Achats":
    products = data["Products"].copy()
    stock_view_full = products[["id", "reference", "name", "stock", "min_stock",
                                "security_stock", "alert_stock", "price",
                                "category_id", "supplier_id"]].copy()

    # ---- Données complètes (non filtrées) pour les graphiques de liste ----
    mv_full = in_period(data["StockMovements"], "created_at", start_dt, end_dt)
    pu_full = in_period(purchases_full, "purchase_date", start_dt, end_dt)

    # ---- Statuts et valeurs sur stock_view_full ----
    stock_view_full["statut"] = np.select(
        [stock_view_full["stock"] <= 0,
         (stock_view_full["stock"] > 0) & (stock_view_full["stock"] <= stock_view_full["min_stock"]),
         (stock_view_full["stock"] > stock_view_full["min_stock"]) & (stock_view_full["stock"] <= stock_view_full["security_stock"]),
         (stock_view_full["stock"] > stock_view_full["security_stock"]) & (stock_view_full["stock"] <= stock_view_full["alert_stock"])],
        ["Rupture", "Critique", "Sécurité", "Alerte"], default="Normal",
    )
    stock_view_full["valeur"] = stock_view_full["stock"] * stock_view_full["price"]

    # ---- Jointures catégories et fournisseurs ----
    cats = data["Categories"][["id","name"]].rename(columns={"id":"category_id","name":"category_name"})
    sups = data["Suppliers"][["id","name"]].rename(columns={"id":"supplier_id","name":"supplier_name"})
    stock_view_full = stock_view_full.merge(cats, on="category_id", how="left").merge(sups, on="supplier_id", how="left")

    # ---- Variables pour les données filtrées ----
    stock_view = stock_view_full.copy()
    mv_cur = mv_full.copy()
    pu_cur = pu_full.copy()

    # ---- État du filtre cross-filter (catégorie) ----
    if "stock_cross_filter" not in st.session_state:
        st.session_state.stock_cross_filter = None

    # ========= KPI (conteneur dynamique) =========
    spacer(14)
    kpi_container = st.empty()

    def display_kpis():
        with kpi_container.container():
            refs = len(stock_view)
            rot_kpi = (sf_cur["item_total"].sum() / stock_view["valeur"].sum()) if stock_view["valeur"].sum() else 0
            secu = (stock_view['statut'] == 'Sécurité').sum()
            val_stock = stock_view['valeur'].sum()
            achats = pu_cur['item_total'].sum() if not pu_cur.empty else 0
            fourn = pu_cur['supplier_name'].nunique() if not pu_cur.empty else 0

            kpi_data = [
                {"icon": "📦", "title": "Références", "value": f"{refs:,}", "color": PRIMARY},
                {"icon": "🔄", "title": "Rotation stock", "value": f"{rot_kpi:.1f}x", "color": ACCENT},
                {"icon": "⚠️", "title": "Stock sécurité", "value": f"{secu}", "color": NEGATIVE},
                {"icon": "💰", "title": "Valeur stock", "value": _fmt(val_stock), "color": POSITIVE},
                {"icon": "📋", "title": "Achats période", "value": _fmt(achats), "color": ACCENT2},
                {"icon": "🏭", "title": "Fournisseurs", "value": f"{fourn}", "color": "#EC4899"},
            ]

            cols = st.columns(6)
            for col, kpi in zip(cols, kpi_data):
                col.markdown(_kpi_card(kpi["icon"], kpi["title"], kpi["value"]), unsafe_allow_html=True)

    display_kpis()
    spacer(10)

    # ---- Filtre produit ----
    product_names = ["Tous"] + sorted(products["name"].dropna().unique())
    selected_product = st.selectbox("Filtrer par produit", product_names, key="stock_product_filter")

    if selected_product != "Tous":
        prod_id = products[products["name"] == selected_product]["id"].iloc[0]
        stock_view = stock_view_full[stock_view_full["id"] == prod_id].copy()
        mv_cur = mv_full[mv_full["product_id"] == prod_id].copy() if not mv_full.empty else pd.DataFrame()
        pu_cur = pu_full[pu_full["product_id"] == prod_id].copy() if not pu_full.empty else pd.DataFrame()
    else:
        stock_view = stock_view_full.copy()
        mv_cur = mv_full.copy()
        pu_cur = pu_full.copy()

    display_kpis()
    spacer(10)

    # =========================================================================
    # LIGNE 1 : Mouvements du stock (50%) | Entrées / sorties par catégorie (50%)
    # =========================================================================
    nb_jours = (end_dt - start_dt).days
    freq_s, x_label_s = ("D", "Jour") if nb_jours <= 31 else ("M", "Mois")

    r1 = st.columns([1, 1])
    with r1[0]:
        section_title("Mouvements du stock")
        if not mv_cur.empty:
            if freq_s == "D":
                mv_cur["bucket"] = mv_cur["created_at"].dt.floor("D")
                all_buckets = pd.date_range(start_dt, end_dt, freq="D")
            else:
                mv_cur["bucket"] = mv_cur["created_at"].dt.to_period("M").dt.start_time
                all_buckets = pd.date_range(start_dt, end_dt, freq="MS")
            in_sum  = mv_cur[mv_cur["type"] == "in" ].groupby("bucket")["quantity"].sum()
            out_sum = mv_cur[mv_cur["type"] == "out"].groupby("bucket")["quantity"].sum()
            agg = pd.DataFrame({"bucket": all_buckets}).set_index("bucket")
            agg["Entrées"] = in_sum
            agg["Sorties"] = out_sum
            agg = agg.fillna(0).reset_index()

            if freq_s == "D":
                _labels = [str(d.day) for d in agg["bucket"]]
            else:
                _labels = [d.strftime("%b") for d in agg["bucket"]]

            fig_evo = go.Figure()
            fig_evo.add_trace(go.Bar(
                x=_labels, y=agg["Entrées"],
                name="Entrées",
                marker_color="#D97706",
                text=agg["Entrées"].apply(lambda v: _fmt(v) if v != 0 else ""),
                textposition="inside", insidetextanchor="middle",
                textfont=dict(size=8, color="#FFFFFF"),
                hovertemplate="%{x}<br>Entrées : <b>%{y:,.0f}</b><extra></extra>",
            ))
            fig_evo.add_trace(go.Bar(
                x=_labels, y=agg["Sorties"],
                name="Sorties",
                marker_color="#B45309",
                text=agg["Sorties"].apply(lambda v: _fmt(v) if v != 0 else ""),
                textposition="inside", insidetextanchor="middle",
                textfont=dict(size=8, color="#FFFFFF"),
                hovertemplate="%{x}<br>Sorties : <b>%{y:,.0f}</b><extra></extra>",
            ))
            fig_evo.update_layout(
                barmode="stack", bargap=0.2,
                height=260, margin=dict(l=10, r=10, t=10, b=36),
                plot_bgcolor="#292524", paper_bgcolor="#292524",
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"),
                legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center", font=dict(size=10, color="#A8A29E"), bgcolor="rgba(0,0,0,0)"),
                xaxis=dict(type="category", showgrid=False, tickfont=dict(size=9, color="#A8A29E"),
                           tickangle=-30 if freq_s == "D" else 0,
                           linecolor="#44403C", showline=True),
                yaxis=dict(showgrid=True, gridcolor="#3C3528",
                           tickfont=dict(size=9, color="#A8A29E"), tickformat=",d", rangemode="tozero"),
                hovermode="x unified",
            )
            st.plotly_chart(fig_evo, key="ch_fig_9", use_container_width=True)
        else:
            st.info("Aucun mouvement sur la période.")

    with r1[1]:
        section_title("Entrées et sorties par catégorie")
        all_cats = stock_view_full["category_name"].fillna("(N/A)").unique()
        if not mv_full.empty:
            cat_mv = mv_full.merge(
                stock_view_full[["id", "category_name"]].drop_duplicates("id"),
                left_on="product_id", right_on="id", how="left"
            )
            cat_mv["category_name"] = cat_mv["category_name"].fillna("(N/A)")
            cat_agg = cat_mv.groupby(["category_name", "type"])["quantity"].sum().reset_index()
            pivot_full = cat_agg.pivot_table(index="category_name", columns="type", values="quantity", aggfunc="sum").fillna(0).reset_index()
            pivot_full.columns.name = None
            if "in" not in pivot_full.columns:
                pivot_full["in"] = 0
            if "out" not in pivot_full.columns:
                pivot_full["out"] = 0
            pivot_full = pivot_full[["category_name", "in", "out"]]
        else:
            pivot_full = pd.DataFrame(columns=["category_name", "in", "out"])

        cat_all = pd.DataFrame({"category_name": all_cats})
        pivot = cat_all.merge(pivot_full, on="category_name", how="left").fillna(0)

        selected_cat = None
        if selected_product != "Tous":
            prod_cat_row = stock_view_full[stock_view_full["name"] == selected_product]
            if not prod_cat_row.empty:
                prod_cat = prod_cat_row["category_name"].iloc[0]
                if pd.isna(prod_cat):
                    prod_cat = "(N/A)"
                selected_cat = prod_cat

        if selected_cat is not None:
            pivot["is_selected"] = pivot["category_name"] == selected_cat
        else:
            pivot["is_selected"] = True
        pivot["color_in"] = pivot["is_selected"].map({True: "#D97706", False: "#A8A29E"})
        pivot["opacity_in"] = pivot["is_selected"].map({True: 1.0, False: 0.5})
        pivot["color_out"] = pivot["is_selected"].map({True: "#B45309", False: "#A8A29E"})
        pivot["opacity_out"] = pivot["is_selected"].map({True: 1.0, False: 0.5})

        fig_io = go.Figure()
        fig_io.add_trace(go.Bar(
            x=pivot["category_name"].astype(str),
            y=pivot["in"], name="Entrée",
            marker=dict(color=pivot["color_in"], opacity=pivot["opacity_in"], line=dict(color="#B45309", width=1)),
            width=0.28, offsetgroup="entrees", alignmentgroup="io",
            text=pivot["in"].apply(lambda v: _fmt(v) if v != 0 else ""),
            textposition="outside", textfont=dict(size=8, color="#FFFFFF"),
            hovertemplate="<b>%{x}</b><br>Entrées : <b>%{y:,.0f}</b><extra></extra>",
        ))
        fig_io.add_trace(go.Bar(
            x=pivot["category_name"].astype(str),
            y=pivot["out"], name="Sorties",
            marker=dict(color=pivot["color_out"], opacity=pivot["opacity_out"], line=dict(color="#78350F", width=1)),
            width=0.28, offsetgroup="sorties", alignmentgroup="io",
            text=pivot["out"].apply(lambda v: _fmt(v) if v != 0 else ""),
            textposition="outside", textfont=dict(size=8, color="#FFFFFF"),
            hovertemplate="<b>%{x}</b><br>Sorties : <b>%{y:,.0f}</b><extra></extra>",
        ))
        fig_io.update_layout(
            barmode="group", bargap=0.3, bargroupgap=0.15,
            height=260, margin=dict(l=10, r=10, t=10, b=36),
            plot_bgcolor="#292524", paper_bgcolor="#292524",
            font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"),
            legend=dict(orientation="h", yanchor="bottom", y=1.15,
                        xanchor="center", x=0.5, font=dict(size=10, color="#A8A29E"), bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(type="category", categoryorder="array",
                       categoryarray=pivot["category_name"].astype(str).tolist(),
                       showgrid=False, showline=True, linecolor="#44403C",
                       tickangle=-30, tickfont=dict(size=9, color="#A8A29E")),
            yaxis=dict(rangemode="tozero", showgrid=True, gridcolor="#3C3528",
                       zeroline=True, zerolinecolor="#44403C",
                       tickfont=dict(size=9, color="#A8A29E"), tickformat=",d"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_io, key="ch_fig_11", use_container_width=True)

    spacer(15)

    # =========================================================================
    # LIGNE 2 : Top 10 produits par valeur | Donut (Valeur stock par catégorie) | Rotation des produits
    # =========================================================================
    r2 = st.columns([1.0, 0.8, 0.8])

    with r2[0]:
        section_title("Top 10 produits par valeur")
        top = (stock_view_full.dropna(subset=["valeur"])
               .groupby("name", as_index=False)["valeur"].sum()
               .nlargest(10, "valeur"))
        if not top.empty:
            if selected_product != "Tous":
                top["is_selected"] = top["name"] == selected_product
            else:
                top["is_selected"] = True
            top["color"] = top["is_selected"].map({True: "#D97706", False: "#A8A29E"})
            top["opacity"] = top["is_selected"].map({True: 1.0, False: 0.3})
            top["_txt"] = top["valeur"].apply(lambda v: _fmt(v))
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=top["valeur"], y=top["name"], orientation="h",
                marker=dict(color=top["color"], opacity=top["opacity"]),
                text=top["_txt"], textposition="inside", insidetextanchor="middle",
                textfont=dict(size=9, color=top["opacity"].apply(lambda o: "white" if o==1.0 else "#A8A29E")),
                hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>"
            ))
            fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
            st.plotly_chart(style_fig(fig, 209), key="ch_fig_13", use_container_width=True)
        else:
            st.info("Aucun produit.")

    with r2[1]:
        section_title("Valeur du stock par catégorie")
        val_cat = stock_view.groupby("category_name", dropna=False)["valeur"].sum().reset_index()
        if not val_cat.empty:
            fig_donut = go.Figure(go.Pie(
                labels=val_cat["category_name"].fillna("(N/A)").astype(str),
                values=val_cat["valeur"],
                hole=0,
                marker_colors=["#F59E0B", "#D97706", "#B45309", "#78350F", "#92400E", "#451A03", "#991B1B", "#BE123C", "#1E3A5F", "#065F46"],
                textinfo="percent",
                textfont=dict(size=11, color=INK),
                showlegend=False,
                domain=dict(x=[0.10, 0.90], y=[0.25, 0.98]),
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} — %{percent}<extra></extra>",
            ))
            fig_donut.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=220,
                paper_bgcolor=CARD,
                plot_bgcolor=CARD,
            )
            st.plotly_chart(fig_donut, key="ch_fig_10", use_container_width=True)
        else:
            st.info("Aucune donnée.")

    with r2[2]:
        section_title("Rotation des produits")
        out_qty = (mv_cur[mv_cur["type"] == "out"]
                   .groupby("product_id")["quantity"].sum()
                   if not mv_cur.empty
                   else pd.Series(dtype=float))
        stock_rot = stock_view.copy()
        stock_rot["out_qty"] = stock_rot["id"].map(out_qty).fillna(0)
        stock_rot["rot"] = stock_rot.apply(
            lambda r: r["out_qty"] / r["stock"] if r["stock"] > 0 else 0, axis=1
        )
        stock_rot = stock_rot[stock_rot["rot"] > 0].copy()

        if stock_rot.empty:
            if selected_product != "Tous":
                st.info(f"Aucune donnée de rotation pour le produit **{selected_product}**.")
            else:
                st.info("Aucune donnée de rotation.")
        else:
            stock_rot = stock_rot.nlargest(10, "rot").copy()
            max_rot = stock_rot["rot"].max() if stock_rot["rot"].max() > 0 else 1
            stock_rot["label_short"] = stock_rot["name"].apply(
                lambda n: str(n)[:18] + "…" if len(str(n)) > 18 else str(n)
            )
            values_rot = (stock_rot["rot"].clip(lower=0.01) + 0.05) ** 1.3

            fig_tm = go.Figure(go.Treemap(
                labels=stock_rot["label_short"],
                parents=[""] * len(stock_rot),
                values=values_rot,
                tiling=dict(packing="squarify", pad=0),
                customdata=np.stack([
                    stock_rot["rot"].values,
                    stock_rot["out_qty"].values,
                    stock_rot["stock"].values,
                    stock_rot["name"].values,
                ], axis=-1),
                text=stock_rot["rot"].apply(lambda v: f"{v:.1f}x"),
                textinfo="label+text",
                textfont=dict(size=16, family="Inter, sans-serif", color="white"),
                hovertemplate=(
                    "<b>%{customdata[3]}</b><br>"
                    "Stock : <b>%{customdata[2]:,.0f}</b><br>"
                    "Sorties : <b>%{customdata[1]:,.0f}</b><br>"
                    "Rotation : <b>%{customdata[0]:.2f}x</b>"
                    "<extra></extra>"
                ),
                marker=dict(
                    colors=stock_rot["rot"].clip(lower=0.01).values,
                    colorscale=[
                        [0.0,  "#78350F"],
                        [0.25, "#92400E"],
                        [0.50, "#B45309"],
                        [0.75, "#D97706"],
                        [1.0,  "#F59E0B"],
                    ],
                    cmin=0,
                    cmax=float(max_rot),
                    showscale=False,
                    line=dict(width=1.2, color="#292524"),
                    pad=dict(t=0, l=0, r=0, b=0),
                ),
                pathbar=dict(visible=False),
            ))
            fig_tm.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                height=209,
                font=dict(family="Inter, sans-serif", size=10),
            )
            st.plotly_chart(style_fig(fig_tm, 209), key="ch_fig_12", use_container_width=True)

    spacer(15)

    # ========= LIGNE 3 : Nombre de retours par produit | Produits sous seuil critique | Alertes =========
    r3 = st.columns([1.0, 0.8, 0.8])
    with r3[0]:
        section_title("Nombre de retours par produit")
        sale_items_all = data["SaleItems"].copy()
        products_ref = data["Products"][["id", "name"]].rename(columns={"id": "product_id"})
        refunds_by_prod = (
            sale_items_all[sale_items_all["refund_quantity"].fillna(0) > 0]
            .groupby("product_id", as_index=False)["refund_quantity"]
            .sum()
            .merge(products_ref, on="product_id", how="left")
        )
        refunds_by_prod["name"] = refunds_by_prod["name"].fillna("(Inconnu)")
        refunds_by_prod = refunds_by_prod.sort_values("refund_quantity", ascending=True).tail(15)
        if not refunds_by_prod.empty:
            if selected_product != "Tous":
                refunds_by_prod["is_selected"] = refunds_by_prod["name"] == selected_product
            else:
                refunds_by_prod["is_selected"] = True
            refunds_by_prod["color"] = refunds_by_prod["is_selected"].map({True: "#F59E0B", False: "#A8A29E"})
            refunds_by_prod["opacity"] = refunds_by_prod["is_selected"].map({True: 1.0, False: 0.3})
            refunds_by_prod["name_short"] = refunds_by_prod["name"].apply(
                lambda n: str(n)[:20] + "…" if len(str(n)) > 20 else str(n)
            )
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=refunds_by_prod["refund_quantity"],
                y=refunds_by_prod["name_short"],
                mode="markers+lines",
                marker=dict(
                    symbol="circle",
                    size=14,
                    color=refunds_by_prod["color"],
                    opacity=refunds_by_prod["opacity"],
                    line=dict(color="#D97706", width=2),
                ),
                line=dict(color="#FCD34D", width=3),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Retours : <b>%{x:,.0f}</b>"
                    "<extra></extra>"
                ),
            ))
            fig.update_layout(
                xaxis=dict(
                    title=dict(text="Quantité retournée", font=dict(size=11)),
                    showgrid=True, gridcolor=GRID,
                    tickfont=dict(size=10, color=MUTED),
                    zeroline=False,
                ),
                yaxis=dict(
                    autorange="reversed",
                    showgrid=False,
                    tickfont=dict(size=11, color=INK),
                ),
                margin=dict(l=10, r=20, t=10, b=50),
                hovermode="y",
            )
            st.plotly_chart(style_fig(fig, 220), key="ch_fig_14", use_container_width=True)
        else:
            st.info("Aucun retour sur la période.")

    with r3[1]:
        section_title("Produits sous seuil critique")
        crit_prods = stock_view_full[stock_view_full["statut"].isin(["Rupture", "Critique"])].sort_values("stock").head(15)
        if not crit_prods.empty:
            crit_prods["stock"] = crit_prods["stock"].fillna(0)
            crit_prods["name"] = crit_prods["name"].fillna("(Inconnu)")
            if selected_product != "Tous":
                crit_prods["is_selected"] = crit_prods["name"] == selected_product
            else:
                crit_prods["is_selected"] = True
            crit_prods["color"] = crit_prods["is_selected"].map({True: "#D97706", False: "#A8A29E"})
            crit_prods["opacity"] = crit_prods["is_selected"].map({True: 1.0, False: 0.3})
            crit_prods["_txt"] = crit_prods["stock"].apply(lambda v: _fmt(v))
            max_s = crit_prods["stock"].max()
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=crit_prods["name"], x=crit_prods["stock"], orientation="h",
                marker=dict(color=crit_prods["color"], opacity=crit_prods["opacity"]),
                text=crit_prods["_txt"], textposition="outside",
                texttemplate="%{text}",
                textfont=dict(size=9, color="#FFFFFF"),
                hovertemplate="%{y}: %{x:,.0f}<extra></extra>"
            ))
            fig.update_layout(height=220, margin=dict(l=10, r=30, t=10, b=10),
                xaxis=dict(showgrid=True, gridcolor="#3C3528", tickfont=dict(color="#A8A29E"), range=[0, max_s * 1.3]),
                yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#A8A29E"), showgrid=False),
                plot_bgcolor="#292524", paper_bgcolor="#292524", bargap=0.4,
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"))
            fig.update_traces(cliponaxis=False)
            st.plotly_chart(fig, key="ch_fig_15", use_container_width=True)
        else:
            st.info("Aucun produit critique.")

    with r3[2]:
        section_title("Alertes de réapprovisionnement")
        alert = stock_view_full[stock_view_full["statut"].isin(["Critique", "Sécurité", "Alerte"])].sort_values("stock").head(15)
        if not alert.empty:
            alert["stock"] = alert["stock"].fillna(0)
            alert["name"] = alert["name"].fillna("(Inconnu)")
            if selected_product != "Tous":
                alert["is_selected"] = alert["name"] == selected_product
            else:
                alert["is_selected"] = True
            alert["color"] = alert["is_selected"].map({True: "#D97706", False: "#A8A29E"})
            alert["opacity"] = alert["is_selected"].map({True: 1.0, False: 0.3})
            alert["_txt"] = alert["stock"].apply(lambda v: _fmt(v))
            max_s = alert["stock"].max()
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=alert["name"], x=alert["stock"], orientation="h",
                marker=dict(color=alert["color"], opacity=alert["opacity"]),
                text=alert["_txt"], textposition="outside",
                texttemplate="%{text}",
                textfont=dict(size=9, color="#FFFFFF"),
                hovertemplate="%{y}: %{x:,.0f}<extra></extra>"
            ))
            fig.update_layout(height=220, margin=dict(l=10, r=30, t=10, b=10),
                xaxis=dict(showgrid=True, gridcolor="#3C3528", tickfont=dict(color="#A8A29E"), range=[0, max_s * 1.3]),
                yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#A8A29E"), showgrid=False),
                plot_bgcolor="#292524", paper_bgcolor="#292524", bargap=0.4,
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"))
            fig.update_traces(cliponaxis=False)
            st.plotly_chart(fig, key="ch_fig_16", use_container_width=True)
        else:
            st.info("Aucune alerte de stock.")

# ===========================================================================
# 4. TRÉSORERIE — Analyse financière et budgétaire (8 graphs)
# ===========================================================================
if section == "Trésorerie":
    # ── Data preparation ──
    pay_d = pay_cur.copy() if not pay_cur.empty else pd.DataFrame()
    pu_d = pu_cur.copy() if not pu_cur.empty else pd.DataFrame()

    if not pay_d.empty:
        pay_d["status_l"] = pay_d["status"].fillna("").str.lower()
        pay_ok = pay_d[pay_d["status_l"] == "approved"].copy()
        total_enc = pay_ok["amount"].sum()
    else:
        pay_ok = pd.DataFrame()
        total_enc = 0

    # ── PaymentAllocations : reconciliation paiements → ventes ──
    pay_alloc = data.get("PaymentAllocations")
    if pay_alloc is not None and not pay_alloc.empty and not pay_ok.empty:
        pay_alloc_s = pay_alloc[pay_alloc["payable_type"].str.contains("Sale", case=False, na=False)].copy()
        if not pay_alloc_s.empty:
            pay_alloc_s["amount_applied"] = pd.to_numeric(pay_alloc_s["amount_applied"], errors="coerce").fillna(0)
            alloc_by_pay = pay_alloc_s.groupby("payment_id")["amount_applied"].sum().reset_index()
            pay_ok = pay_ok.merge(alloc_by_pay, left_on="id", right_on="payment_id", how="left").rename(columns={"amount_applied": "alloc_amount"})
            pay_ok["alloc_amount"] = pay_ok["alloc_amount"].fillna(pay_ok["amount"])
            total_enc_raw = total_enc
            total_enc = pay_ok["alloc_amount"].sum()
            if abs(total_enc_raw - total_enc) > 1:
                st.caption(f"Paiements alloués : {_fmt(total_enc)} (brut : {_fmt(total_enc_raw)})")
    # ── CashLogs : vérification des flux ──
    cash_logs = data.get("CashLogs")
    if cash_logs is not None and not cash_logs.empty:
        cl_approved = cash_logs[cash_logs["action"].str.lower() == "approved"]
        if not cl_approved.empty:
            cl_approved = cl_approved.drop_duplicates("payment_id")
            cl_pay_ids = set(pd.to_numeric(cl_approved["payment_id"], errors="coerce").dropna().astype(int))
            pay_ok_ids = set(pay_ok["id"].astype(int)) if not pay_ok.empty else set()
            unmatched = cl_pay_ids - pay_ok_ids
            if unmatched:
                st.caption(f"⚠️ {len(unmatched)} paiements approuvés (CashLogs) sans correspondance dans Payments")

    # ── Décaissements : uniquement les achats réellement payés ──
    pu_dedup = pu_d.drop_duplicates("purchase_id") if not pu_d.empty else pd.DataFrame()
    paid_purchases = pd.DataFrame()
    paid_amount = 0
    if pay_alloc is not None and not pay_alloc.empty:
        alloc_p = pay_alloc[pay_alloc["payable_type"].str.contains("Purchase", case=False, na=False)].copy()
        if not alloc_p.empty:
            alloc_p["amount_applied"] = pd.to_numeric(alloc_p["amount_applied"], errors="coerce").fillna(0)
            alloc_by_pay_p = alloc_p.groupby("payment_id")["amount_applied"].sum().reset_index()
            if not pay_ok.empty:
                dec_pay_ok = pay_ok.merge(alloc_by_pay_p, left_on="id", right_on="payment_id", how="inner")
                paid_amount = dec_pay_ok["amount_applied"].sum()
                alloc_p["purchase_id"] = pd.to_numeric(alloc_p["payable_id"], errors="coerce")
                paid_ids = set(alloc_p["purchase_id"].dropna().unique())
                paid_purchases = pu_dedup[pu_dedup["purchase_id"].isin(paid_ids)].copy() if not pu_dedup.empty else pd.DataFrame()
    if paid_purchases.empty and not pu_dedup.empty:
        statut_paye = pu_dedup["purchase_status"].fillna("").str.lower().isin(["confirmed", "received", "completed", "paid", "paye", "recu"])
        paid_purchases = pu_dedup[statut_paye].copy()
        paid_amount = paid_purchases["purchase_total"].sum()

    rf_cur = in_period(data["Refunds"], "created_at", start_dt, end_dt) if "Refunds" in data else pd.DataFrame()
    total_refunds = rf_cur["total"].sum() if not rf_cur.empty else 0
    total_dec = paid_amount + total_refunds

    solde = total_enc - total_dec

    if mois_selection == "Tous":
        enc_mois = total_enc
        dec_mois = total_dec
    else:
        mois_filtre = start_dt.strftime("%Y-%m")
        if not pay_ok.empty:
            enc_col_m = "alloc_amount" if "alloc_amount" in pay_ok.columns else "amount"
            enc_mois = pay_ok[pay_ok["created_at"].dt.strftime("%Y-%m") == mois_filtre][enc_col_m].sum()
        else:
            enc_mois = 0
        if not paid_purchases.empty:
            dec_mois = paid_purchases[paid_purchases["purchase_date"].dt.strftime("%Y-%m") == mois_filtre]["purchase_total"].sum()
        else:
            dec_mois = 0
        dec_mois += rf_cur[rf_cur["created_at"].dt.strftime("%Y-%m") == mois_filtre]["total"].sum() if not rf_cur.empty else 0
    flux_net = solde

    # ── Taux de variation de la trésorerie ──
    if mois_selection == "Tous":
        prev_var_start = prev_start_dt
        prev_var_end = prev_end_dt
    else:
        mois_num = mois_options.index(mois_selection)
        if mois_num == 1:
            prev_var_start = datetime(annee - 1, 12, 1)
            prev_var_end = datetime(annee - 1, 12, 31, 23, 59, 59)
        else:
            prev_var_start = datetime(annee, mois_num - 1, 1)
            prev_var_end = datetime(annee, mois_num, 1) - timedelta(seconds=1)
    prev_pay = in_period(pay, "created_at", prev_var_start, prev_var_end)
    prev_pu = in_period(purchases_full, "purchase_date", prev_var_start, prev_var_end)
    if not prev_pay.empty:
        prev_pay_ok = prev_pay[prev_pay["status"].fillna("").str.lower() == "approved"].copy()
        prev_enc = prev_pay_ok["amount"].sum()
        if pay_alloc is not None and not pay_alloc.empty and not prev_pay_ok.empty:
            prev_alloc_s = pay_alloc[pay_alloc["payable_type"].str.contains("Sale", case=False, na=False)].copy()
            if not prev_alloc_s.empty:
                prev_alloc_s["amount_applied"] = pd.to_numeric(prev_alloc_s["amount_applied"], errors="coerce").fillna(0)
                prev_alloc_by_pay = prev_alloc_s.groupby("payment_id")["amount_applied"].sum().reset_index()
                prev_pay_ok = prev_pay_ok.merge(prev_alloc_by_pay, left_on="id", right_on="payment_id", how="left").rename(columns={"amount_applied": "alloc_amount"})
                prev_pay_ok["alloc_amount"] = prev_pay_ok["alloc_amount"].fillna(prev_pay_ok["amount"])
                prev_enc = prev_pay_ok["alloc_amount"].sum()
    else:
        prev_pay_ok = pd.DataFrame()
        prev_enc = 0
    # Previous period paid purchases
    prev_pu_dedup = prev_pu.drop_duplicates("purchase_id") if not prev_pu.empty else pd.DataFrame()
    prev_paid_amount = 0
    if pay_alloc is not None and not pay_alloc.empty:
        prev_alloc_p = pay_alloc[pay_alloc["payable_type"].str.contains("Purchase", case=False, na=False)].copy()
        if not prev_alloc_p.empty:
            prev_alloc_p["amount_applied"] = pd.to_numeric(prev_alloc_p["amount_applied"], errors="coerce").fillna(0)
            prev_alloc_by_pay_p = prev_alloc_p.groupby("payment_id")["amount_applied"].sum().reset_index()
            if not prev_pay_ok.empty:
                prev_dec_pay_ok = prev_pay_ok.merge(prev_alloc_by_pay_p, left_on="id", right_on="payment_id", how="inner")
                prev_paid_amount = prev_dec_pay_ok["amount_applied"].sum()
    if prev_paid_amount == 0 and not prev_pu_dedup.empty:
        prev_statut_paye = prev_pu_dedup["purchase_status"].fillna("").str.lower().isin(["confirmed", "received", "completed", "paid", "paye", "recu"])
        prev_paid_amount = prev_pu_dedup.loc[prev_statut_paye, "purchase_total"].sum()
    prev_rf = in_period(data["Refunds"], "created_at", prev_var_start, prev_var_end) if "Refunds" in data else pd.DataFrame()
    prev_refunds = prev_rf["total"].sum() if not prev_rf.empty else 0
    prev_dec = prev_paid_amount + prev_refunds
    prev_solde = prev_enc - prev_dec
    variation_pct = ((solde - prev_solde) / abs(prev_solde)) * 100 if prev_solde != 0 else 0.0

    # ── Monthly aggregation ──
    def build_monthly_balance(enc_df, dec_paid_df, annee):
        if not enc_df.empty:
            enc_col = "alloc_amount" if "alloc_amount" in enc_df.columns else "amount"
            em = enc_df.set_index("created_at").to_period("M").to_timestamp().groupby(level=0)[enc_col].sum()
        else:
            em = pd.Series(dtype=float)
        if not dec_paid_df.empty:
            dm = dec_paid_df.set_index("purchase_date").to_period("M").to_timestamp().groupby(level=0)["purchase_total"].sum()
        else:
            dm = pd.Series(dtype=float)
        refunds_m = rf_cur.set_index("created_at").to_period("M").to_timestamp().groupby(level=0)["total"].sum() if not rf_cur.empty else pd.Series(dtype=float)
        dm = dm.add(refunds_m, fill_value=0)
        all_m = pd.date_range(start=f"{annee}-01-01", end=f"{annee}-12-01", freq="MS")
        rows = []
        cumul = 0
        for m in all_m:
            enc = em.get(m, 0)
            dec = dm.get(m, 0)
            net = enc - dec
            cumul += net
            rows.append({"mois": m.strftime("%Y-%m"), "encaissements": enc, "decaissements": dec, "net": net, "solde": cumul})
        return pd.DataFrame(rows)

    monthly_df = build_monthly_balance(pay_ok, paid_purchases, annee)

    # ── DSO monthly (délai encaissement clients) via PaymentAllocations ──
    sales_dso = in_period(data["Sales"], "created_at", start_dt, end_dt)
    if not sales_dso.empty and pay_alloc is not None and not pay_alloc.empty:
        sd = sales_dso[["id", "created_at", "client_id"]].rename(
            columns={"id": "sale_id", "created_at": "sale_date"})
        pay_all_approved = data["Payments"][
            data["Payments"]["status"].fillna("").str.lower() == "approved"]
        alloc_s = pay_alloc[pay_alloc["payable_type"].str.contains("Sale", case=False, na=False)].copy()
        alloc_s = alloc_s.merge(pay_all_approved[["id", "approved_at"]], left_on="payment_id", right_on="id", how="inner")
        alloc_s["sale_id"] = pd.to_numeric(alloc_s["payable_id"], errors="coerce")
        pdj = sd.merge(alloc_s[["sale_id", "approved_at"]], on="sale_id", how="left")
        pdj["pay_date"] = pdj["approved_at"].fillna(pd.Timestamp(end_dt))
        pdj["delai"] = (pdj["pay_date"] - pdj["sale_date"]).dt.days
        pdj = pdj.dropna(subset=["delai"])
        if not pdj.empty:
            dso_m = pdj.set_index("sale_date").to_period("M").to_timestamp().groupby(level=0)["delai"].mean()
        else:
            dso_m = pd.Series(dtype=float)
    else:
        pdj = pd.DataFrame()
        dso_m = pd.Series(dtype=float)

    # ── DPO monthly (délai paiement fournisseurs) ──
    pu_dpo = in_period(data["Purchases"], "created_at", start_dt, end_dt)
    if not pu_dpo.empty:
        pu_dpo = pu_dpo.copy()
        if pay_alloc is not None and not pay_alloc.empty:
            alloc_p = pay_alloc[pay_alloc["payable_type"].str.contains("Purchase", case=False, na=False)].copy()
            if not alloc_p.empty:
                alloc_p["purchase_id"] = pd.to_numeric(alloc_p["payable_id"], errors="coerce")
                pay_approved_p = data["Payments"][data["Payments"]["status"].fillna("").str.lower() == "approved"]
                alloc_p = alloc_p.merge(pay_approved_p[["id", "approved_at"]], left_on="payment_id", right_on="id", how="inner")
                pu_dpo = pu_dpo.merge(alloc_p[["purchase_id", "approved_at"]], on="purchase_id", how="left")
                pu_dpo["pay_date"] = pu_dpo["approved_at"].fillna(pd.Timestamp(end_dt))
            else:
                paid_status = ["paid", "payé", "payee", "completed", "terminé", "received", "reçu", "confirmed"]
                pu_dpo["est_paye"] = pu_dpo["status"].fillna("").str.lower().isin(paid_status)
                pu_dpo["pay_date"] = pu_dpo["updated_at"].where(pu_dpo["est_paye"], pd.Timestamp(end_dt))
        else:
            paid_status = ["paid", "payé", "payee", "completed", "terminé", "received", "reçu", "confirmed"]
            pu_dpo["est_paye"] = pu_dpo["status"].fillna("").str.lower().isin(paid_status)
            pu_dpo["pay_date"] = pu_dpo["updated_at"].where(pu_dpo["est_paye"], pd.Timestamp(end_dt))
        pu_dpo["delai"] = (pu_dpo["pay_date"] - pu_dpo["created_at"]).dt.days
        pu_dpo = pu_dpo.dropna(subset=["delai"])
        if not pu_dpo.empty:
            dpo_m = pu_dpo.set_index("created_at").to_period("M").to_timestamp().groupby(level=0)["delai"].mean()
        else:
            dpo_m = pd.Series(dtype=float)
    else:
        pu_dpo = pd.DataFrame()
        dpo_m = pd.Series(dtype=float)

    # ═══════════════════════════════════════════════════════════════════════
    # LIGNE 1 : KPIs Trésorerie (5 cartes)
    # ═══════════════════════════════════════════════════════════════════════
    spacer(14)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(_kpi_card("💰", "Solde de trésorerie", _fmt(solde)), unsafe_allow_html=True)
    c2.markdown(_kpi_card("📈", "Encaissements du mois", _fmt(enc_mois)), unsafe_allow_html=True)
    c3.markdown(_kpi_card("📉", "Décaissements du mois", _fmt(dec_mois)), unsafe_allow_html=True)
    dso_moy = dso_m.mean() if not dso_m.empty else 0
    dpo_moy = dpo_m.mean() if not dpo_m.empty else 0
    nb_jours_periode = (end_dt - start_dt).days or 365
    ratio_annuel = 365 / nb_jours_periode
    sales_period = in_period(data["Sales"], "created_at", start_dt, end_dt)
    ca_periode = sales_period[sales_period["total"] > 0]["total"].sum()
    ca_annualise = ca_periode * ratio_annuel
    pu_periode = in_period(data["Purchases"], "created_at", start_dt, end_dt)
    pu_periode_ok = pu_periode[pu_periode["status"].fillna("").str.lower().isin(["confirmed", "received", "completed", "paid", "paye", "recu"])]
    achats_periode = pu_periode_ok["total"].sum()
    achats_annualises = achats_periode * ratio_annuel
    bfr_annuel = (dso_moy * ca_annualise / 365) - (dpo_moy * achats_annualises / 365)
    c4.markdown(_kpi_card("📊", "BFR annuel", _fmt(bfr_annuel)), unsafe_allow_html=True)
    var_icon = "📈" if variation_pct >= 0 else "📉"
    var_sign = "+" if variation_pct >= 0 else ""
    var_txt = f"{var_sign}{variation_pct:.1f}%"
    c5.markdown(_kpi_card(var_icon, "Variation trésorerie", var_txt), unsafe_allow_html=True)

    spacer(10)

    bfr_mois_abrev = {
        1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr",
        5: "Mai", 6: "Juin", 7: "Juil", 8: "Aoû",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc"
    }
    all_months = pd.date_range(start=f"{annee}-01-01", end=f"{annee}-12-01", freq="MS")
    bfr_labels = [bfr_mois_abrev[m.month] for m in all_months]

    def monthly_series_to_df(s, all_m):
        d = s.reindex(all_m, fill_value=0)
        return d.values

    # ═══════════════════════════════════════════════════════════════════════
    # ROW 1 : Pilotage
    # ═══════════════════════════════════════════════════════════════════════
    r1c1, r1c2 = st.columns([1, 1])

    # -- Évolution du solde (Line Chart) --
    with r1c1:
        section_title("Évolution du solde de trésorerie")
        if not monthly_df.empty:
            if mois_selection == "Tous":
                x_vals = monthly_df["mois"].apply(
                    lambda x: bfr_mois_abrev.get(int(x.split("-")[1]), x))
            else:
                x_vals = monthly_df["mois"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_vals, y=monthly_df["solde"],
                mode="lines+markers",
                line=dict(color=POSITIVE, width=3, shape="spline"),
                fill="tozeroy", fillcolor="rgba(217,119,6,0.15)",
                marker=dict(size=8, color=POSITIVE, line=dict(color=CARD, width=1)),
                hovertemplate="%{x}<br>Solde : <b>%{y:,.0f}</b><extra></extra>"
            ))
            fig.add_hline(y=0, line_dash="dot", line_color=NEGATIVE, opacity=0.5)
            fig.update_layout(yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(style_fig(fig, 260), key="tr_chart_1", use_container_width=True)
        else:
            st.info("Aucune donnée de trésorerie.")

    # -- Encaissements vs Décaissements (Grouped Bar) --
    with r1c2:
        section_title("Encaissements vs Décaissements")
        if not monthly_df.empty:
            mois_abrev = {
                1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr",
                5: "Mai", 6: "Juin", 7: "Juil", 8: "Aoû",
                9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc"
            }
            monthly_df["mois_abr"] = monthly_df["mois"].apply(
                lambda x: mois_abrev.get(int(x.split("-")[1]), x))
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly_df["mois_abr"], y=monthly_df["encaissements"],
                name="Encaissements",
                marker=dict(color="#F59E0B", line=dict(color="#B45309", width=1)),
                width=0.28, offsetgroup="enc", alignmentgroup="ed",
                text=monthly_df["encaissements"].fillna(0).apply(
                    lambda v: _fmt(v)),
                textposition="outside", textfont=dict(size=8, color="#FFFFFF"),
                hovertemplate="<b>%{x}</b><br>Encaissements : <b>%{y:,.0f}</b><extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=monthly_df["mois_abr"], y=monthly_df["decaissements"],
                name="Décaissements",
                marker=dict(color="#B45309", line=dict(color="#78350F", width=1)),
                width=0.28, offsetgroup="dec", alignmentgroup="ed",
                text=monthly_df["decaissements"].fillna(0).apply(
                    lambda v: _fmt(v)),
                textposition="outside", textfont=dict(size=8, color="#FFFFFF"),
                hovertemplate="<b>%{x}</b><br>Impayé : <b>%{y:,.0f}</b><extra></extra>",
            ))
            fig.update_layout(
                barmode="group", bargap=0.3, bargroupgap=0.15,
                height=260, margin=dict(l=10, r=10, t=40, b=36),
                plot_bgcolor="#292524", paper_bgcolor="#292524",
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"),
                legend=dict(orientation="h", yanchor="bottom", y=1.04,
                            xanchor="center", x=0.5, font=dict(size=10, color="#A8A29E")),
                xaxis=dict(type="category", categoryorder="array",
                           categoryarray=monthly_df["mois_abr"].tolist(),
                           showgrid=False, showline=True, linecolor="#44403C",
                           tickangle=0, tickfont=dict(size=9, color="#A8A29E")),
                yaxis=dict(rangemode="tozero", showgrid=True, gridcolor="#3C3528",
                           zeroline=True, zerolinecolor="#44403C",
                           tickfont=dict(size=9, color="#A8A29E"), tickformat=",.0f"),
                hovermode="x unified",
            )
            st.plotly_chart(fig, key="tr_chart_2", use_container_width=True)
        else:
            st.info("Aucune donnée.")

    spacer(15)

    # ═══════════════════════════════════════════════════════════════════════
    # ROW 3 : Analyse des flux
    # ═══════════════════════════════════════════════════════════════════════
    r3c1, r3c2, r3c3 = st.columns([1.0, 0.8, 0.8])

    # -- Classement des sorties d'argent (Horizontal Bar) --
    with r3c1:
        section_title("Classement des sorties d'argent")
        pu_spend = pu_cur.copy() if not pu_cur.empty else pd.DataFrame()
        if not pu_spend.empty:
            pu_spend["purchase_total"] = pd.to_numeric(pu_spend["purchase_total"], errors="coerce")
            pu_spend = pu_spend.dropna(subset=["purchase_total"])
            sup_names = data["Suppliers"][["id", "name"]].rename(
                columns={"id": "supplier_id", "name": "supplier_name"})
            spend = pu_spend.groupby("supplier_id", as_index=False)["purchase_total"].sum()
            spend = spend.merge(sup_names, on="supplier_id", how="left")
            spend["supplier_name"] = spend["supplier_name"].fillna(
                "Fourn. #" + spend["supplier_id"].astype(str))
            spend["supplier_name"] = spend["supplier_name"].astype(str).str.strip()
            spend = spend.sort_values("purchase_total", ascending=False).head(10)
            if spend.empty:
                st.info("Aucune dépense valide sur la période.")
                st.stop()
            names_clean = spend["supplier_name"].tolist()
            vals = spend["purchase_total"].tolist()
            labels_k = [_fmt(v) for v in vals]
            fig_spend = go.Figure()
            fig_spend.add_trace(go.Bar(
                x=vals,
                y=names_clean,
                orientation="h",
                marker=dict(color="#D97706", line=dict(width=0)),
                text=labels_k,
                textposition="outside",
                texttemplate="%{text}",
                textfont=dict(size=11, color="#FAFAF9"),
                hovertemplate="<b>%{y}</b> : %{x:,.0f}<extra></extra>",
                cliponaxis=False,
            ))
            fig_spend.update_layout(
                height=220,
                margin=dict(l=8, r=80, t=10, b=36),
                paper_bgcolor="#292524",
                plot_bgcolor="#292524",
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"),
                xaxis=dict(
                    tickformat="~s",
                    range=[0, max(vals) * 1.45 if vals else 1],
                    showgrid=True,
                    gridcolor="#3C3528",
                    zeroline=True,
                    zerolinecolor="#44403C",
                    tickfont=dict(size=9, color="#A8A29E"),
                ),
                yaxis=dict(
                    autorange="reversed",
                    showgrid=False,
                    tickfont=dict(size=10, color="#FAFAF9"),
                ),
                hovermode="y unified",
                bargap=0.35,
            )
            st.plotly_chart(fig_spend, key="tr_chart_3_spend", use_container_width=True)
        else:
            st.info("Aucune dépense sur la période.")

    # -- Répartition des flux (Donut) --
    with r3c2:
        section_title("Répartition des flux")
        sales_uniq = sf_cur.drop_duplicates("sale_id") if not sf_cur.empty else pd.DataFrame()
        tva_tot = sales_uniq["tax_amount"].sum() if not sales_uniq.empty else 0
        solde_net = total_enc - total_dec
        labels = ["Encaissements", "Décaissements", "TVA"]
        values = [total_enc, total_dec, tva_tot]
        if abs(solde_net) > 0.01 * max(total_enc, 1):
            labels.append("Solde net")
            values.append(abs(solde_net))
        total_flux = sum(values)
        if total_flux > 0:
            pulls = [0.0] * len(labels); pulls[0] = 0.05
            fig6 = go.Figure(go.Pie(
                labels=labels, values=values,
                hole=0.45, textposition="outside",
                texttemplate="%{label}<br>%{percent:.1%}",
                marker=dict(colors=BI_PALETTE, line=dict(color="#292524", width=2)),
                showlegend=False,
                domain=dict(x=[0.02, 0.98], y=[0.25, 0.98]),
                textfont=dict(size=10),
                hovertemplate="%{label}<br>%{value:,.0f}<extra></extra>",
                pull=pulls,
            ))
            fig6.update_layout(margin=dict(l=5, r=5, t=5, b=5))
            st.markdown('<div id="chart-tr6">', unsafe_allow_html=True)
            st.plotly_chart(style_fig(fig6, height=220, pie=True), key="tr_chart_6", on_select="ignore", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Pas assez de données.")

    # -- BFR par mois (Barres) --
    with r3c3:
        section_title("Besoin en Fonds de Roulement (BFR) par mois")
        if not monthly_df.empty:
            sales_mois = sales_period[sales_period["total"] > 0].copy()
            if not sales_mois.empty:
                sales_mois["mois_ts"] = pd.to_datetime(sales_mois["created_at"]).dt.to_period("M").dt.start_time
                ca_par_mois = sales_mois.groupby("mois_ts")["total"].sum()
            else:
                ca_par_mois = pd.Series(dtype=float)
            pu_mois = pu_periode_ok.copy() if not pu_periode_ok.empty else pd.DataFrame()
            if not pu_mois.empty:
                pu_mois["mois_ts"] = pd.to_datetime(pu_mois["created_at"]).dt.to_period("M").dt.start_time
                achats_par_mois = pu_mois.groupby("mois_ts")["total"].sum()
            else:
                achats_par_mois = pd.Series(dtype=float)
            bfr_vals = []
            for m_ts in all_months:
                ca_m = ca_par_mois.get(m_ts, 0)
                achats_m = achats_par_mois.get(m_ts, 0)
                bfr = (dso_moy * ca_m / m_ts.days_in_month) - (dpo_moy * achats_m / m_ts.days_in_month)
                bfr_vals.append(bfr)

            bar_color = [ACCENT if v >= 0 else NEGATIVE for v in bfr_vals]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=bfr_labels, y=bfr_vals,
                marker=dict(color=bar_color, line=dict(color=CARD, width=1)),
                text=[_fmt(v) for v in bfr_vals],
                textposition="inside", textangle=-90, textfont=dict(size=8, color="#FAFAF9"),
                hovertemplate="%{x}<br>BFR : <b>%{y:,.0f}</b><extra></extra>"
            ))
            fig.add_hline(y=0, line_dash="dot", line_color="#A8A29E", opacity=0.5)
            fig.update_layout(
                height=220, margin=dict(l=10, r=10, t=10, b=36),
                plot_bgcolor="#292524", paper_bgcolor="#292524",
                font=dict(family="Inter, sans-serif", size=11, color="#FAFAF9"),
                legend=dict(orientation="h", yanchor="bottom", y=1.04,
                            xanchor="center", x=0.5, font=dict(size=10, color="#A8A29E")),
                xaxis=dict(type="category", categoryorder="array", categoryarray=bfr_labels,
                           showgrid=False, showline=True, linecolor="#44403C",
                           tickangle=0, tickfont=dict(size=9, color="#A8A29E")),
                yaxis=dict(rangemode="tozero", showgrid=True, gridcolor="#3C3528",
                           zeroline=True, zerolinecolor="#44403C",
                           tickfont=dict(size=9, color="#A8A29E"), tickformat=",.0f"),
                hovermode="x unified",
            )
            st.plotly_chart(fig, key="tr_chart_5", use_container_width=True)
        else:
            st.info("Pas assez de données pour le BFR.")

    spacer(15)

    # ═══════════════════════════════════════════════════════════════════════
    # ROW 4 : Prévision
    # ═══════════════════════════════════════════════════════════════════════
    r4c1, r4c2, r4c3 = st.columns([1.0, 0.8, 0.8])

    # -- Créances impayées cumulées --
    with r4c1:
        section_title("Créances impayées cumulées")
        sales_uniq = sf_cur.drop_duplicates("sale_id") if not sf_cur.empty else pd.DataFrame()
        if not sales_uniq.empty and not pay_ok.empty:
            sales_uniq = sales_uniq[["sale_id", "sale_date", "sale_total"]].copy()
            sales_m = sales_uniq.set_index("sale_date").to_period("M").to_timestamp().groupby(level=0)["sale_total"].sum()
            pay_m = pay_ok.set_index("created_at").to_period("M").to_timestamp().groupby(level=0)["amount"].sum()
            if mois_selection == "Tous":
                unpaid = []
                cumul = 0
                for m in all_months:
                    s = sales_m.get(m, 0)
                    p = pay_m.get(m, 0)
                    cumul += max(0, s - p)
                    unpaid.append(cumul)
            else:
                mois_num = mois_options.index(mois_selection)
                month_start = datetime(annee, mois_num, 1)
                month_end = datetime(annee, mois_num + 1, 1) - timedelta(seconds=1) if mois_num < 12 else datetime(annee, 12, 31, 23, 59, 59)
                sales_mois = sales_uniq[(sales_uniq["sale_date"] >= month_start) & (sales_uniq["sale_date"] <= month_end)]
                pay_mois = pay_ok[(pay_ok["created_at"] >= month_start) & (pay_ok["created_at"] <= month_end)]
                sales_daily = sales_mois.set_index("sale_date").resample("D")["sale_total"].sum()
                pay_daily = pay_mois.set_index("created_at").resample("D")["amount"].sum()
                all_days = pd.date_range(month_start, month_end, freq="D")
                unpaid = []
                cumul = 0
                for d in all_days:
                    s = sales_daily.get(d, 0)
                    p = pay_daily.get(d, 0)
                    cumul += max(0, s - p)
                    unpaid.append(cumul)
            x_labels = bfr_labels if mois_selection == "Tous" else [str(d.day) for d in all_days]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_labels, y=unpaid,
                mode="lines+markers",
                line=dict(color=ACCENT, width=2.5, shape="spline"),
                marker=dict(size=7, color=ACCENT, symbol="diamond",
                            line=dict(color=CARD, width=1)),
                fill="tozeroy", fillcolor="rgba(217,119,6,0.15)",
                hovertemplate="%{x}<br>Cumul créances : <b>%{y:,.0f}</b><extra></extra>"
            ))
            st.plotly_chart(style_fig(fig, 220), key="tr_chart_3", use_container_width=True)
        else:
            st.info("Pas assez de données.")

    # -- Prévision de trésorerie (Régression linéaire) --
    with r4c2:
        section_title("Prévision de trésorerie")
        if len(monthly_df) >= 3:
            ts = monthly_df.copy()
            ts["t"] = np.arange(len(ts))
            y = ts["solde"].values.astype(float)
            t = ts["t"].values.astype(float)
            n = len(t)
            tm, ym = t.mean(), y.mean()
            denom = ((t - tm) ** 2).sum()
            if denom > 0:
                slope = ((t - tm) * (y - ym)).sum() / denom
                intercept = ym - slope * tm
                y_hat = intercept + slope * t
                horizon = 6
                future_t = np.arange(n, n + horizon)
                last_dt = pd.Timestamp(ts["mois"].iloc[-1] + "-01")
                future_dates = pd.date_range(last_dt + pd.DateOffset(months=1), periods=horizon, freq="MS")
                y_fore = intercept + slope * future_t
                mois_abrev7 = {
                    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr",
                    5: "Mai", 6: "Juin", 7: "Juil", 8: "Aoû",
                    9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc"
                }
                hist_dates = [mois_abrev7[d.month] for d in all_months]
                fore_labels = [mois_abrev7.get(d.month, d.strftime("%m")) + "*" for d in future_dates]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist_dates, y=y, mode="markers",
                    marker=dict(size=8, color=PRIMARY, line=dict(color=CARD, width=1)),
                    name="Solde réel      ",
                    hovertemplate="%{x}<br>Solde : <b>%{y:,.0f}</b><extra></extra>"))
                fig.add_trace(go.Scatter(
                    x=hist_dates, y=y_hat, mode="lines",
                    line=dict(color=ACCENT, width=2),
                    name="Tendance linéaire      ",
                    hovertemplate="%{x}<br>Tendance : <b>%{y:,.0f}</b><extra></extra>"))
                fig.add_trace(go.Scatter(
                    x=fore_labels, y=y_fore,
                    mode="lines+markers",
                    line=dict(color=ACCENT2, width=3),
                    marker=dict(size=8, color=ACCENT2, symbol="diamond",
                                line=dict(color=CARD, width=1)),
                    name="Prévision",
                    hovertemplate="%{x}<br>Prévision : <b>%{y:,.0f}</b><extra></extra>"))
                fig.add_hline(y=0, line_dash="dot", line_color=NEGATIVE, opacity=0.4)
                fig.update_layout(
                    height=220,
                    xaxis=dict(type="category", categoryorder="array",
                               categoryarray=hist_dates + fore_labels,
                               tickangle=-30, tickfont=dict(size=8)),
                    yaxis=dict(rangemode="tozero", tickformat=",.0f",
                               zeroline=True, zerolinecolor=GRID),
                )
                fig_custom = style_fig(fig, 220)
                fig_custom.update_layout(
                    margin=dict(t=70),
                    legend=dict(orientation="h", yanchor="bottom", y=1.9,
                                xanchor="center", x=0.5,
                                font=dict(size=9),
                                itemsizing="constant"),
                )
                st.plotly_chart(fig_custom, key="tr_chart_7", use_container_width=True)
            else:
                st.info("Pas assez de variabilité pour la prévision.")
        else:
            st.info("Minimum 3 mois d'historique requis.")

    # -- Jauge de trésorerie (Angulaire) --
    with r4c3:
        section_title("Jauge de trésorerie")
        seuil_rouge = 100_000
        seuil_vert = 300_000
        max_range = max(seuil_vert * 2, abs(solde) * 1.5, 500_000)
        gauge_val = max(solde, 0)
        if solde < seuil_rouge:
            bar_couleur = NEGATIVE
        elif solde < seuil_vert:
            bar_couleur = PRIMARY
        else:
            bar_couleur = ACCENT
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=gauge_val,
            number={"suffix": "", "valueformat": ",.0f",
                    "font": {"size": 22, "color": INK,
                    "family": "Inter, sans-serif"}},
            delta={"reference": seuil_rouge, "position": "top",
                   "increasing": {"color": ACCENT},
                   "decreasing": {"color": NEGATIVE},
                   "font": {"size": 16}},
            gauge={
                "shape": "angular",
                "axis": {"range": [0, max_range], "tickwidth": 1,
                         "tickcolor": MUTED, "tickformat": ",.0f",
                         "tickfont": {"size": 9, "color": MUTED,
                                      "family": "Inter, sans-serif"}},
                "bar": {"color": bar_couleur, "thickness": 0.3},
                "bgcolor": CARD,
                "borderwidth": 1,
                "bordercolor": GRID,
                "steps": [
                    {"range": [0, seuil_rouge], "color": "#451A03"},
                    {"range": [seuil_rouge, seuil_vert], "color": "#78350F"},
                    {"range": [seuil_vert, max_range], "color": "#292524"},
                ],
                "threshold": {
                    "line": {"color": ACCENT2, "width": 3},
                    "thickness": 0.8, "value": seuil_rouge
                }
            }
        ))
        fig.update_layout(
            height=220, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor=CARD,
            font=dict(family="Inter, sans-serif", size=11, color=INK),
        )
        st.plotly_chart(fig, key="tr_chart_8", use_container_width=True,
                        config={"displayModeBar": False})

# ===========================================================================
# 5. DATA LAB — Assistant IA (100 % noir, bouton jaune)
# ===========================================================================
if section == "AI Agent":

    import requests
    import json
    from datetime import datetime
    import streamlit.components.v1 as components

    # ---- Clé API ----
    OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")

    # ---- État de session ----
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = []
    if "ai_loading" not in st.session_state:
        st.session_state.ai_loading = False

    # ---- Palette de couleurs ----
    PRIMARY = "#F59E0B"
    ACCENT = "#FBBF24"
    POSITIVE = "#D97706"
    DARK = "#0B0E14"
    CARD = "#1A1F2A"
    GRID = "#2A2F3A"
    INK = "#E8EDF5"
    MUTED = "#8A92A6"

    PRIMARY_RGB = "245,158,11"
    ACCENT_RGB = "251,191,36"
    POSITIVE_RGB = "217,119,6"

    # ============================================================
    # 1. CSS PRINCIPAL (fond noir, messages, top bar, logo)
    # ============================================================
    st.markdown(
        f"""
        <style>
            /* ---------- FORCER TOUS LES FONDS EN NOIR ---------- */
            html, body, .stApp, .main, .block-container,
            .element-container, .stMarkdown, .stChatInput,
            .stTextInput, .stTextArea, div[data-testid="stChatInput"],
            div[data-testid="stTextArea"], .stForm, .stForm > div,
            .stChatMessage, .stChatMessage > div,
            .stChatInput > div, .stChatInput textarea,
            .stChatInput button, .stButton, .stButton > button,
            .stColumns, .stColumn, .stContainer, .stExpander,
            .stTabs, .stTab, .stSidebar, .stSidebar > div,
            .stHeader, .stFooter, .stException, .stAlert,
            .stProgress, .stSpinner, .stSlider, .stCheckbox,
            .stRadio, .stSelectbox, .stMultiselect, .stDateInput,
            .stTimeInput, .stFileUploader, .stCameraInput,
            .stColorPicker, .stNumberInput, .stTextInput > div,
            .stTextArea > div, .stSelectbox > div, .stMultiselect > div,
            .stDateInput > div, .stTimeInput > div, .stColorPicker > div {{
                background-color: {DARK} !important;
                background: {DARK} !important;
                color: {INK} !important;
            }}

            /* ---------- SUPPRIMER LES ESPACES BLANCS ---------- */
            .block-container {{
                padding-top: 0 !important;
                padding-bottom: 0 !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
                max-width: 100% !important;
            }}
            .stApp {{
                margin-top: 0 !important;
            }}
            .element-container:first-child {{
                margin-top: 0 !important;
                padding-top: 0 !important;
            }}

            /* ---------- LOGO ANIMÉ ---------- */
            .nx-logo {{
                position: relative;
                width: 34px;
                height: 34px;
                display: inline-block;
                flex-shrink: 0;
                vertical-align: middle;
            }}
            .nx-logo > i {{
                position: absolute;
                inset: 0;
                border-radius: 50%;
                display: block;
            }}
            .nx-logo .nx-ring-1 {{
                background: conic-gradient(from 0deg,
                    transparent 0deg, {PRIMARY} 70deg, {ACCENT} 170deg,
                    {POSITIVE} 250deg, transparent 330deg);
                -webkit-mask: radial-gradient(circle, transparent 58%, #000 60%);
                mask: radial-gradient(circle, transparent 58%, #000 60%);
                transition: filter 0.3s;
            }}
            .nx-logo .nx-ring-2 {{
                inset: 18%;
                background: conic-gradient(from 180deg,
                    {POSITIVE} 0deg, transparent 80deg, {ACCENT} 200deg, transparent 320deg);
                -webkit-mask: radial-gradient(circle, transparent 48%, #000 52%);
                mask: radial-gradient(circle, transparent 48%, #000 52%);
                opacity: .3;
                transition: opacity 0.3s;
            }}
            .nx-logo .nx-core {{
                inset: 32%;
                background: radial-gradient(circle at 32% 30%, #ffffff 0%, #C9BFFF 25%, {PRIMARY} 65%, {ACCENT} 100%);
                box-shadow: 0 0 14px rgba({PRIMARY_RGB},.85), inset 0 0 6px rgba(255,255,255,.55);
            }}
            .nx-logo .nx-orbit {{
                inset: 6%;
                background: transparent;
            }}
            .nx-logo .nx-orbit::before {{
                content: "";
                position: absolute;
                top: -2px;
                left: 50%;
                width: 5px;
                height: 5px;
                margin-left: -2.5px;
                border-radius: 50%;
                background: {POSITIVE};
                box-shadow: 0 0 8px {POSITIVE}, 0 0 14px rgba({POSITIVE_RGB},.6);
            }}

            .nx-logo.thinking .nx-ring-1 {{
                animation: nx-spin 1.1s linear infinite;
                filter: drop-shadow(0 0 12px rgba({PRIMARY_RGB},.95));
            }}
            .nx-logo.thinking .nx-ring-2 {{
                animation: nx-spin 1.5s linear infinite reverse;
                opacity: 1;
            }}
            .nx-logo.thinking .nx-orbit {{
                animation: nx-spin 0.9s linear infinite;
            }}
            .nx-logo.thinking .nx-core {{
                animation: nx-pulse 0.85s ease-in-out infinite;
            }}
            .nx-logo.thinking::after {{
                content: "";
                position: absolute;
                inset: -6px;
                border-radius: 50%;
                border: 1px solid rgba({PRIMARY_RGB},.4);
                animation: nx-halo 1.6s ease-out infinite;
            }}

            @keyframes nx-spin {{
                to {{ transform: rotate(360deg); }}
            }}
            @keyframes nx-pulse {{
                0%, 100% {{ transform: scale(1); filter: brightness(1); }}
                50% {{ transform: scale(1.12); filter: brightness(1.25); }}
            }}
            @keyframes nx-halo {{
                0% {{ transform: scale(.85); opacity: .9; }}
                100% {{ transform: scale(1.45); opacity: 0; }}
            }}

            /* ---------- TOP BAR ---------- */
            .ai-topbar {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 6px 16px;
                border-bottom: 1px solid {GRID};
                background: linear-gradient(180deg, {CARD}, transparent) !important;
                backdrop-filter: blur(12px);
                margin-bottom: 4px;
            }}
            .ai-topbar-left {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .ai-live-dot {{
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: {POSITIVE};
                box-shadow: 0 0 10px {POSITIVE};
                animation: pulse-dot 2s infinite;
            }}
            @keyframes pulse-dot {{
                50% {{ opacity: .4; }}
            }}
            .ai-topbar-title {{
                font-family: 'Inter', 'Aptos', sans-serif;
                font-size: 11px;
                letter-spacing: 1.5px;
                text-transform: uppercase;
                color: {MUTED};
            }}
            .ai-topbar-title b {{
                color: {INK};
                font-weight: 600;
            }}
            .ai-pill {{
                padding: 2px 10px;
                border-radius: 20px;
                font-size: 9px;
                background: {CARD};
                border: 1px solid {GRID};
                color: {MUTED};
                font-family: 'Inter', sans-serif;
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }}
            .ai-pill b {{
                color: {POSITIVE};
                font-weight: 500;
            }}

            /* ---------- GREETING ---------- */
            .ai-greeting {{
                padding: 8px 20px 4px;
                text-align: left;
            }}
            .ai-greeting h1 {{
                font-family: 'Inter', 'Aptos', sans-serif;
                font-weight: 400;
                font-size: clamp(20px, 2.5vw, 30px);
                line-height: 1.1;
                letter-spacing: -0.5px;
                margin: 0 0 2px;
                color: {INK};
            }}
            .ai-greeting h1 .accent {{
                background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 50%, {POSITIVE} 100%);
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
                font-style: italic;
            }}
            .ai-greeting p {{
                color: {MUTED};
                font-size: 13px;
                margin: 0;
                max-width: 600px;
            }}
            .moving-cta {{
                display: inline-block;
                background: linear-gradient(135deg, #ffffff, {PRIMARY}, {ACCENT}, {POSITIVE}, #ffffff);
                background-size: 300% auto;
                -webkit-background-clip: text;
                background-clip: text;
                color: transparent;
                animation: shimmerMove 6s ease infinite;
                font-weight: 500;
            }}
            @keyframes shimmerMove {{
                0% {{ background-position: 0% 50%; }}
                50% {{ background-position: 100% 50%; }}
                100% {{ background-position: 0% 50%; }}
            }}

            /* ---------- MESSAGES WRAP ---------- */
            .ai-messages-wrap {{
                flex: 1;
                overflow-y: auto;
                padding: 8px 16px 8px;
                max-height: 420px;
                min-height: 160px;
                background: transparent !important;
            }}
            .ai-messages-wrap::-webkit-scrollbar {{
                width: 6px;
            }}
            .ai-messages-wrap::-webkit-scrollbar-thumb {{
                background: {GRID};
                border-radius: 4px;
            }}

            /* ---------- MESSAGES (bulles) ---------- */
            .ai-msg {{
                display: flex;
                gap: 12px;
                margin-bottom: 16px;
                animation: fadeUp .35s ease-out;
            }}
            .ai-msg.user {{
                justify-content: flex-end;
            }}
            .ai-msg .avatar {{
                width: 32px;
                height: 32px;
                border-radius: 50%;
                flex-shrink: 0;
                display: grid;
                place-items: center;
                font-size: 13px;
                font-weight: 700;
                background: {CARD};
                border: 1px solid {GRID};
                color: {INK};
            }}
            .ai-msg.bot .avatar {{
                background: transparent;
                border: none;
                padding: 0;
                font-size: 0;
            }}
            .ai-msg.bot .avatar .nx-logo {{
                width: 32px;
                height: 32px;
            }}
            .ai-msg.user .avatar {{
                order: 2;
                background: linear-gradient(135deg, {PRIMARY}, {ACCENT});
                color: {DARK};
                border: none;
            }}
            .ai-msg .body {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                max-width: 78%;
            }}
            .ai-msg.user .body {{
                align-items: flex-end;
            }}
            .ai-msg .meta {{
                font-size: 10px;
                color: {MUTED};
                padding: 0 4px;
                font-family: 'Inter', sans-serif;
                letter-spacing: 0.3px;
            }}
            .ai-msg .bubble {{
                padding: 12px 18px;
                border-radius: 16px;
                background: {CARD};
                border: 1px solid {GRID};
                line-height: 1.6;
                font-size: 14px;
                color: {INK} !important;
                word-wrap: break-word;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            }}
            .ai-msg.bot .bubble {{
                border-top-left-radius: 4px;
                background: {CARD};
                border-color: rgba({PRIMARY_RGB},0.15);
            }}
            .ai-msg.user .bubble {{
                border-top-right-radius: 4px;
                background: linear-gradient(135deg, rgba({PRIMARY_RGB},0.2), rgba({ACCENT_RGB},0.12));
                border-color: rgba({PRIMARY_RGB},0.3);
                color: {INK} !important;
            }}
            .ai-msg .bubble code {{
                background: {DARK};
                color: {ACCENT};
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.9em;
            }}
            .ai-msg .bubble pre {{
                background: {DARK};
                padding: 10px;
                border-radius: 8px;
                overflow-x: auto;
                color: {INK};
                border: 1px solid {GRID};
            }}
            .ai-msg .bubble p {{
                margin: 0 0 6px 0;
            }}
            .ai-msg .bubble p:last-child {{
                margin-bottom: 0;
            }}
            .ai-msg .bubble ul,
            .ai-msg .bubble ol {{
                margin: 4px 0 4px 18px;
            }}

            /* ---------- TYPING ---------- */
            .typing {{
                display: flex;
                gap: 5px;
                padding: 6px 0;
            }}
            .typing span {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: {PRIMARY};
                animation: bounce 1.2s infinite;
            }}
            .typing span:nth-child(2) {{
                animation-delay: .15s;
                background: {ACCENT};
            }}
            .typing span:nth-child(3) {{
                animation-delay: .3s;
                background: {POSITIVE};
            }}
            @keyframes bounce {{
                0%, 60%, 100% {{ transform: scale(.6); opacity: .4; }}
                30% {{ transform: scale(1); opacity: 1; }}
            }}
            @keyframes fadeUp {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ============================================================
    # 2. JAVASCRIPT : cible uniquement la barre du bas (stBottom)
    # ============================================================
    components.html(
        f"""
        <script>
        (function() {{
            var DARK     = "{DARK}";
            var GRID     = "{GRID}";
            var INK      = "{INK}";
            var PRIMARY  = "{PRIMARY}";
            var ACCENT   = "{ACCENT}";
            var POSITIVE = "{POSITIVE}";

            function fixBottom() {{
                var doc = window.parent.document;
                if (doc.getElementById('aurora-bottom-fix')) return;
                var s = doc.createElement('style');
                s.id = 'aurora-bottom-fix';
                s.textContent = `
                    [data-testid="stBottom"] {{
                        background: ${{DARK}} !important;
                        background-color: ${{DARK}} !important;
                        border-top: 1px solid ${{GRID}} !important;
                        box-shadow: none !important;
                    }}
                    [data-testid="stBottom"] > div,
                    [data-testid="stBottom"] > div > div {{
                        background: ${{DARK}} !important;
                        background-color: ${{DARK}} !important;
                    }}
                    [data-testid="stChatInput"] > div {{
                        background: ${{DARK}} !important;
                        border: 1px solid ${{GRID}} !important;
                        border-radius: 20px !important;
                    }}
                    [data-testid="stChatInput"] textarea {{
                        background: transparent !important;
                        color: ${{INK}} !important;
                    }}
                    [data-testid="stChatInput"] textarea::placeholder {{
                        color: rgba(138,146,166,0.7) !important;
                    }}
                    [data-testid="stChatInput"] button {{
                        background: linear-gradient(135deg, ${{PRIMARY}}, ${{ACCENT}}, ${{POSITIVE}}) !important;
                        border-radius: 14px !important;
                        border: none !important;
                        color: ${{DARK}} !important;
                        box-shadow: 0 4px 14px rgba(245,158,11,.4) !important;
                    }}
                `;
                doc.head.appendChild(s);
            }}

            setTimeout(fixBottom, 100);
            setTimeout(fixBottom, 500);
            setTimeout(fixBottom, 1500);
        }})();
        </script>
        """,
        height=0,
        scrolling=False,
    )

    # ============================================================
    # 3. FONCTIONS MÉTIER (contexte + appel API)
    # ============================================================
    def build_context() -> str:
        context_parts = []

        if not sf_cur.empty:
            ca_total = sf_cur["item_total"].sum()
            nb_ventes = sf_cur["sale_id"].nunique()
            nb_lignes = len(sf_cur)
            ca_moyen = sf_cur["item_total"].mean() if nb_lignes else 0

            top5 = sf_cur.groupby("product_name")["item_total"].sum().nlargest(5)
            top5_str = ", ".join(
                [f"{p} ({_fmt(v)})" for p, v in top5.items()]
            ) if not top5.empty else "Aucun"

            top5_clients = sf_cur.groupby("client_name")["item_total"].sum().nlargest(5)
            top5_clients_str = ", ".join(
                [f"{c} ({_fmt(v)})" for c, v in top5_clients.items()]
            ) if not top5_clients.empty else "Aucun"

            status_counts = sf_cur["sale_status"].value_counts().to_dict()
            status_str = ", ".join(
                [f"{k}: {v}" for k, v in status_counts.items()]
            ) if status_counts else "Aucun"

            context_parts.append(
                f"**Ventes** : CA total {_fmt(ca_total)}, {nb_ventes} commandes, "
                f"{nb_lignes} lignes, panier moyen {_fmt(ca_moyen)} par ligne.\n"
                f"Top 5 produits : {top5_str}.\nTop 5 clients : {top5_clients_str}.\n"
                f"Statuts : {status_str}."
            )

        nb_clients = len(data["Clients"])
        context_parts.append(f"**Clients** : {nb_clients} clients actifs.")

        if 'stock_view_full' in globals() and not stock_view_full.empty:
            val_stock = (stock_view_full["stock"] * stock_view_full["price"]).sum()
            nb_produits = len(stock_view_full)
            rupture = stock_view_full[stock_view_full["stock"] <= 0]
            critique = stock_view_full[
                (stock_view_full["stock"] > 0) &
                (stock_view_full["stock"] <= stock_view_full["min_stock"])
            ]
            context_parts.append(
                f"**Stock** : {nb_produits} références, valeur {_fmt(val_stock)}.\n"
                f"Rupture : {len(rupture)}, Critique : {len(critique)}."
            )

        if 'solde' in locals():
            context_parts.append(f"**Trésorerie** : solde {_fmt(solde)}.")
            if 'enc_mois' in locals():
                context_parts.append(f"Encaissements du mois : {_fmt(enc_mois)}.")
            if 'dec_mois' in locals():
                context_parts.append(f"Décaissements du mois : {_fmt(dec_mois)}.")

        if not pay_cur.empty:
            pay_methods = pay_cur["method"].value_counts().to_dict()
            pay_str = ", ".join([f"{k}: {v}" for k, v in pay_methods.items()])
            context_parts.append(f"**Paiements** : {pay_str}.")

        return "\n\n".join(context_parts)

    def ask_ai(question: str, context: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aurora-dashboard.com",
            "X-OpenRouter-Title": "Aurora ERP Dashboard",
        }
        models = [
            "deepseek/deepseek-r1:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mixtral-8x7b-instruct:free",
            "openrouter/free"
        ]

        last_error = None
        for model in models:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es un expert en analyse financière et ERP. "
                            "Utilise les données suivantes pour répondre avec précision. "
                            "Effectue les calculs étape par étape et donne des résultats chiffrés. "
                            "Si une information manque, indique-le clairement.\n\n"
                            "=== DONNÉES ===\n" + context
                        )
                    },
                    {"role": "user", "content": question},
                ],
                "temperature": 0.2,
                "max_tokens": 4096,
            }
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=90)
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error_detail = response.json().get("error", {})
                    last_error = f"{response.status_code} : {error_detail.get('message', response.text)}"
                    continue
            except Exception as e:
                last_error = str(e)
                continue

        return f"❌ Erreur : {last_error}"

    # ============================================================
    # 4. INTERFACE UTILISATEUR
    # ============================================================

    # ---- Logo animé (statique ou en "thinking") ----
    logo_class = "nx-logo" + (" thinking" if st.session_state.ai_loading else "")

    # ---- Top bar ----
    st.markdown(
        f"""
        <div class="ai-topbar">
            <div class="ai-topbar-left">
                <div class="{logo_class}">
                    <i class="nx-ring-1"></i>
                    <i class="nx-ring-2"></i>
                    <i class="nx-orbit"></i>
                    <i class="nx-core"></i>
                </div>
                <div class="ai-live-dot"></div>
                <div class="ai-topbar-title"><b>Data Analyst</b></div>
            </div>
            <div class="ai-pill"><b>●</b> online</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Zone des messages ----
    st.markdown('<div class="ai-messages-wrap">', unsafe_allow_html=True)

    # Message de bienvenue
    if not st.session_state.ai_messages:
        st.markdown(
            f"""
            <div class="ai-greeting">
                <h1>Bonjour, je suis votre <span class="accent">analyste de données</span>.</h1>
                <p><span class="moving-cta">✨ Posez une question, demandez un rapport ou lancez une analyse ✨</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Historique des messages (HTML personnalisé)
    for msg in st.session_state.ai_messages:
        is_user = msg["role"] == "user"
        avatar_html = (
            '<div class="avatar">👤</div>'
            if is_user
            else '<div class="avatar"><div class="nx-logo"><i class="nx-ring-1"></i><i class="nx-ring-2"></i><i class="nx-orbit"></i><i class="nx-core"></i></div></div>'
        )
        msg_html = f"""
        <div class="ai-msg {msg['role']}">
            {avatar_html}
            <div class="body">
                <div class="meta">{'Vous' if is_user else 'Assistant'} · {datetime.now().strftime('%H:%M')}</div>
                <div class="bubble">{msg['content']}</div>
            </div>
        </div>
        """
        st.markdown(msg_html, unsafe_allow_html=True)

    # Indicateur de chargement (typing)
    if st.session_state.ai_loading:
        st.markdown(
            """
            <div class="ai-msg bot">
                <div class="avatar">
                    <div class="nx-logo thinking">
                        <i class="nx-ring-1"></i>
                        <i class="nx-ring-2"></i>
                        <i class="nx-orbit"></i>
                        <i class="nx-core"></i>
                    </div>
                </div>
                <div class="body">
                    <div class="meta">Assistant · analyse en cours</div>
                    <div class="bubble">
                        <div class="typing"><span></span><span></span><span></span></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ---- Zone de saisie (st.chat_input) ----
    user_input = st.chat_input("Posez votre question…")

    # ---- Traitement du message ----
    if user_input:
        st.session_state.ai_messages.append({"role": "user", "content": user_input})
        st.session_state.ai_loading = True
        st.rerun()

    if (
        st.session_state.ai_loading
        and st.session_state.ai_messages
        and st.session_state.ai_messages[-1]["role"] == "user"
    ):
        last_question = st.session_state.ai_messages[-1]["content"]
        context = build_context()
        answer = ask_ai(last_question, context)
        st.session_state.ai_messages.append({"role": "assistant", "content": answer})
        st.session_state.ai_loading = False
        st.rerun()