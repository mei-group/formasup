import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from fpdf import FPDF
import os

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Simulateur Coût Rupture Alternance | Formasup", layout="wide", initial_sidebar_state="expanded")

# --- 2. CSS "PREMIUM+" ---
custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    .st-emotion-cache-1dp5vir {display: none !important;} 
    .st-emotion-cache-1aege4i {display: none !important;} 

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #0B192C !important;
    }

    h1 { font-weight: 800; font-size: 2.5rem; letter-spacing: -0.03em; margin-bottom: 0.5rem; color: #0B192C; }
    h2 { font-weight: 700; font-size: 1.8rem; letter-spacing: -0.02em; margin-top: 2rem; color: #0B192C; }
    h3 { font-weight: 600; font-size: 1.4rem; }

    [data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0;
    }
    
    .stDownloadButton button {
        background-color: #0077B6 !important; /* Bleu Formasup */
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        box-shadow: 0 4px 14px rgba(0, 119, 182, 0.3) !important;
        transition: all 0.2s ease;
        width: 100%;
    }
    .stDownloadButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 119, 182, 0.4) !important;
    }

    [data-testid="stForm"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 30px;
        box-shadow: 0 10px 30px rgba(11, 25, 44, 0.05);
    }
    .stTextInput input {
        border-radius: 8px !important;
        border: 1px solid #CBD5E1 !important;
        padding: 12px 16px !important;
        font-size: 1rem !important;
        background-color: #F8FAFC !important;
        transition: border-color 0.2s;
    }
    .stTextInput input:focus {
        border-color: #0077B6 !important;
        box-shadow: 0 0 0 1px #0077B6 !important;
    }
    [data-testid="stFormSubmitButton"] button {
        background-color: #0B192C !important; 
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        width: 100% !important;
        font-size: 1.1rem !important;
        margin-top: 10px !important;
    }
    [data-testid="stFormSubmitButton"] button:hover {
        background-color: #1a3c5e !important;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- 3. INITIALISATION ÉTAT ---
if 'acces_debloque' not in st.session_state:
    st.session_state.acces_debloque = False
if 'user_prenom' not in st.session_state:
    st.session_state.user_prenom = ""
if 'user_nom' not in st.session_state:
    st.session_state.user_nom = ""

# Bypass Token URL
if "token" in st.query_params:
    if st.query_params["token"] == "formasup_vip":
        st.session_state.acces_debloque = True
        if "name" in st.query_params:
            st.session_state.user_prenom = st.query_params["name"].capitalize()
        elif "firstname" in st.query_params:
            st.session_state.user_prenom = st.query_params["firstname"].capitalize()
        elif not st.session_state.user_prenom:
            st.session_state.user_prenom = "Manager"

def logout():
    st.session_state.acces_debloque = False
    st.session_state.user_prenom = ""
    st.session_state.user_nom = ""

# --- 4. MOTEUR DE CALCUL (LOGIQUE RH & FINANCIERE 2026) ---
def calculer_impact_rupture(salaire, mois_rupture, motif, conges_restants):
    # 1. ICCP (Indemnité Compensatrice Congés Payés) - 26 jours ouvrés moyens
    iccp = (salaire / 26) * conges_restants
    
    # 2. Aides de l'Etat perdues (Aide exceptionnelle 2026 : 6000€ la première année = 500€/mois)
    aides_perdues = 0
    if mois_rupture < 12:
        aides_perdues = (12 - mois_rupture) * 500
        
    # 3. Coûts RH Cachés (Sunk Costs : Onboarding, temps équipe, perte de productivité, nouveau recrutement)
    # Plus la rupture est tardive, plus le coût de remplacement et la perte de savoir sont élevés
    couts_caches = salaire * 1.5 + (mois_rupture * 150)
    
    # 4. Ajustement selon le motif
    if motif == "Rupture pendant les 45 premiers jours":
        # Période d'essai : pas ou peu de congés, pas d'indemnité, coûts RH plus faibles car constat d'échec rapide
        couts_caches = salaire * 0.5 
    
    total_impact = iccp + aides_perdues + couts_caches
    
    return {
        "ICCP": iccp,
        "Aides_Perdues": aides_perdues,
        "Couts_Caches": couts_caches,
        "Total": total_impact
    }

def ajouter_contact_getresponse(prenom, nom, email):
    return True 

# --- 5. GENERATION DU PDF PREMIUM ---
def generer_pdf_formasup(prenom, nom, salaire, mois_rupture, motif, resultats):
    class PDF(FPDF):
        def header(self):
            self.set_fill_color(11, 25, 44) 
            self.rect(0, 0, 210, 30, 'F')
            self.set_font('Arial', 'B', 18)
            self.set_text_color(255, 255, 255)
            self.cell(10, 10) 
            self.cell(40, 10, 'FORMASUP', 0, 0, 'L')
            self.set_font('Arial', '', 11)
            self.cell(140, 10, 'AUDIT - COUT RUPTURE ALTERNANCE', 0, 1, 'R')
            self.ln(10)

        def footer(self):
            self.set_y(-25)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(11, 25, 44)
            self.multi_cell(0, 4, txt="Ce document est une simulation a but informatif. Les montants sont des estimations basees sur la legislation de l'alternance en vigueur. Confiez vos recrutements a Formasup pour securiser vos contrats.", align='C')
            self.ln(1)
            self.cell(0, 5, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_margins(15, 30, 15)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(11, 25, 44)
    pdf.cell(0, 10, txt=f"Rapport d'Impact Financier genere pour : {prenom} {nom}", ln=True, align='C')
    pdf.ln(5)
    
    # Bloc d'informations
    pdf.set_fill_color(246, 249, 252)
    pdf.rect(15, pdf.get_y(), 180, 25, 'F') 
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(180, 8, txt=f"  Salaire Brut Mensuel : {salaire:,.0f} EUR", ln=True)
    pdf.cell(180, 8, txt=f"  Moment de la rupture : M{mois_rupture} | Motif : {motif}", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(180, 8, txt=f"  IMPACT FINANCIER GLOBAL ESTIME : {resultats['Total']:,.0f} EUR", ln=True)
    pdf.ln(15)

    # Titre Détails
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(0, 119, 182) # Bleu Cyan Formasup
    pdf.cell(0, 10, txt="Details de l'impact financier", ln=True)
    pdf.set_draw_color(11, 25, 44)
    pdf.set_line_width(0.3)
    pdf.line(pdf.get_x(), pdf.get_y(), 195, pdf.get_y()) 
    pdf.ln(5)

    # Détail des coûts
    col_w = 120
    
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(col_w, 8, txt="Decaissement Immediat (Solde de tout compte - ICCP) :", align='L')
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 8, txt=f"{resultats['ICCP']:,.0f} EUR", ln=True, align='R')
    
    pdf.set_font("Arial", "", 10)
    pdf.cell(col_w, 8, txt="Manque a gagner (Aides de l'Etat non percues) :", align='L')
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 8, txt=f"{resultats['Aides_Perdues']:,.0f} EUR", ln=True, align='R')

    pdf.set_font("Arial", "", 10)
    pdf.cell(col_w, 8, txt="Couts RH et de Remplacement (Sourcing, formation) :", align='L')
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 8, txt=f"{resultats['Couts_Caches']:,.0f} EUR", ln=True, align='R')
    
    pdf.ln(5)
    pdf.set_fill_color(11, 25, 44)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(col_w, 10, txt="  COUT TOTAL ESTIME :", align='L', fill=True)
    pdf.cell(50, 10, txt=f"{resultats['Total']:,.0f} EUR  ", ln=True, align='R', fill=True)

    return pdf.output(dest="S").encode("latin-1")

# ==========================================
# HEADER UI
# ==========================================
col_header1, col_header2 = st.columns([0.8, 0.2])

with col_header1:
    st.markdown("<h1 style='margin:0; font-size: 2.2rem; margin-top: -10px;'>Simulateur Coût de Rupture</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; margin: 5px 0 20px 0; font-size: 1.1rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 15px;'>Calculez l'impact financier réel et les coûts cachés liés à la rupture d'un contrat en alternance.</p>", unsafe_allow_html=True)

with col_header2:
    if os.path.exists("logo.webp"):
        st.image("logo.webp", use_container_width=True)
    else:
        st.markdown("""
        <div style="background-color: #0077B6; color: white; padding: 10px 20px; border-radius: 8px; font-weight: 800; font-size: 1.2rem; letter-spacing: 2px; text-align: center; margin-top: -10px;">
            FORMASUP
        </div>
        """, unsafe_allow_html=True)


# ==========================================
# ETAPE 1 : FORMULAIRE DE CAPTURE
# ==========================================
if not st.session_state.acces_debloque:
    col_espace1, col_form, col_espace2 = st.columns([1, 2, 1])
    
    with col_form:
        st.markdown("<h3 style='text-align: center; margin-bottom: 5px;'>Accédez à votre audit financier</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748B; margin-bottom: 25px;'>Découvrez le coût réel d'une rupture en alternance pour votre entreprise.</p>", unsafe_allow_html=True)
        
        with st.form("lead_capture_form"):
            col1, col2 = st.columns(2)
            prenom_input = col1.text_input("Prénom")
            nom_input = col2.text_input("Nom")
            email_input = st.text_input("Adresse e-mail professionnelle")
            
            submitted = st.form_submit_button("Calculer le coût de la rupture")
            
            if submitted:
                if prenom_input and email_input:
                    ajouter_contact_getresponse(prenom_input, nom_input, email_input)
                    st.session_state.acces_debloque = True
                    st.session_state.user_prenom = prenom_input
                    st.session_state.user_nom = nom_input
                    st.rerun()
                else:
                    st.error("Veuillez remplir votre prénom et votre email.")

# ==========================================
# ETAPE 2 : SIMULATEUR PREMIUM (Débloqué)
# ==========================================
else:
    # --- SIDEBAR ---
    st.sidebar.markdown(f"<div style='background-color:#0B192C; color:white; padding:15px; border-radius:8px; margin-bottom:20px; text-align:center;'>👋 Bienvenue <b>{st.session_state.user_prenom}</b></div>", unsafe_allow_html=True)
    st.sidebar.markdown("### Les paramètres de l'alternant")
    
    salaire_sb = st.sidebar.slider("Salaire brut mensuel (€)", min_value=800, max_value=2200, value=1200, step=50)
    mois_rupture_sb = st.sidebar.slider("Mois de la rupture (ex: 6 = au bout de 6 mois)", min_value=1, max_value=24, value=6, step=1)
    conges_sb = st.sidebar.slider("Solde de congés payés non pris (Jours)", min_value=0, max_value=30, value=5, step=1)
    motif_sb = st.sidebar.radio("Motif de la rupture", [
        "Accord commun / Démission", 
        "Licenciement pour faute",
        "Rupture pendant les 45 premiers jours"
    ])

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    if st.sidebar.button("🔄 Refaire une simulation / Déconnexion"):
        logout()
        st.rerun()

    # --- CALCULS ---
    res = calculer_impact_rupture(salaire_sb, mois_rupture_sb, motif_sb, conges_sb)

    # --- METRIQUES ---
    st.markdown("<h2>Résultat de votre audit financier</h2>", unsafe_allow_html=True)
    metrics_html = f"""
    <div style="display: flex; gap: 20px; margin-bottom: 40px; flex-wrap: wrap;">
        <div style="flex: 1; background: white; padding: 25px; border-radius: 12px; border: 1px solid #E2E8F0; border-top: 4px solid #F39C12; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <p style="color: #64748B; font-size: 0.85rem; margin: 0 0 5px 0; font-weight: 600; text-transform: uppercase;">Aides perdues & Décaissement</p>
            <h3 style="color: #0B192C; font-size: 1.8rem; margin: 0; font-weight: 700;">{(res['ICCP'] + res['Aides_Perdues']):,.0f} €</h3>
        </div>
        <div style="flex: 1; background: white; padding: 25px; border-radius: 12px; border: 1px solid #E2E8F0; border-top: 4px solid #E74C3C; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <p style="color: #64748B; font-size: 0.85rem; margin: 0 0 5px 0; font-weight: 600; text-transform: uppercase;">Coûts RH cachés (Est.)</p>
            <h3 style="color: #0B192C; font-size: 1.8rem; margin: 0; font-weight: 700;">{res['Couts_Caches']:,.0f} €</h3>
        </div>
        <div style="flex: 1; background: #0B192C; padding: 25px; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(11, 25, 44, 0.2);">
            <p style="color: #94A3B8; font-size: 0.85rem; margin: 0 0 5px 0; font-weight: 600; text-transform: uppercase;">Impact Financier Total</p>
            <h3 style="color: white; font-size: 2.2rem; margin: 0; font-weight: 800;">{res['Total']:,.0f} €</h3>
        </div>
    </div>
    """
    st.markdown(metrics_html, unsafe_allow_html=True)

    # --- GRAPHIQUE DONUT & SYNTHESE ---
    col_g1, col_g2 = st.columns([0.5, 0.5], gap="large")
    
    with col_g1:
        st.markdown("<h3>Répartition de l'impact financier</h3>", unsafe_allow_html=True)
        
        # Préparation des données pour le Donut
        labels = ['Solde de tout compte (ICCP)', 'Aides d\'État Perdues', 'Coûts de remplacement RH']
        values = [res['ICCP'], res['Aides_Perdues'], res['Couts_Caches']]
        colors = ['#0077B6', '#F39C12', '#E74C3C']

        fig = px.pie(names=labels, values=values, hole=0.6)
        
        fig.update_traces(
            textinfo='percent', 
            textfont_size=14,
            marker=dict(colors=colors, line=dict(color='#FFFFFF', width=2)),
            hovertemplate="<b>%{label}</b><br>Montant: <b>%{value:,.0f} €</b><extra></extra>"
        )

        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
            font=dict(family="Plus Jakarta Sans, sans-serif", size=12, color="#475569"),
            margin=dict(l=0, r=0, t=20, b=0),
            height=350,
            hoverlabel=dict(bgcolor="white", font_size=13, font_family="Plus Jakarta Sans")
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col_g2:
        st.markdown("<h3>Analyse Formasup</h3>", unsafe_allow_html=True)
        
        st.info(f"**💡 Décryptage de votre situation :**\n\nEn rompant le contrat au mois {mois_rupture_sb}, votre entreprise fait face à **{res['Aides_Perdues']:,.0f} €** de manque à gagner sur les aides à l'embauche. À cela s'ajoute l'obligation légale de régler les congés non pris ({res['ICCP']:,.0f} €).\n\nCependant, la véritable perte réside dans le temps investi et le coût d'un nouveau recrutement pour remplacer l'alternant.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        pdf_bytes = generer_pdf_formasup(st.session_state.user_prenom, st.session_state.user_nom, salaire_sb, mois_rupture_sb, motif_sb, res)
        st.download_button("📄 Télécharger le rapport financier (PDF)", data=pdf_bytes, file_name="Audit_Rupture_Formasup.pdf", mime="application/pdf")

    # --- BANDEAU FORMASUP ---
    st.markdown("<br><hr style='border-color: #E2E8F0;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 30px; border-radius: 12px; text-align: center;">
        <h3 style="margin-top:0; color: #0B192C;">Une rupture coûte cher. Anticipez avec Formasup.</h3>
        <p style="color: #475569; font-size: 1.05rem; max-width: 700px; margin: 0 auto 20px auto;">
        Le secret d'une alternance réussie réside dans un sourcing millimétré et un suivi académique rigoureux. Confiez-nous vos prochains recrutements pour sécuriser vos investissements RH et garantir le succès de vos alternants.
        </p>
        <a href="https://formasup-arl.fr/contact/" target="_blank" style="background-color: #0077B6; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; display: inline-block;">Prendre rendez-vous avec un conseiller</a>
    </div>
    """, unsafe_allow_html=True)
