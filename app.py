import os
import streamlit as st
from dotenv import load_dotenv

# Charger les variables d'environnement (.env)
load_dotenv()

# Importer les modules du projet
from ingest import load_project_graph
from context_builder import build_context, ContextTooLargeError
from prompts import SYSTEM_PROMPT
from gemini_client import ask_gemini

# Configuration de la page Streamlit
st.set_page_config(
    page_title="CISO RAG Assistant - Graphify",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injection de styles CSS personnalisés pour une esthétique premium et moderne (Style Dark Mode Épuré / Glassmorphic)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;600&display=swap');
    
    /* Variables de design et typographie */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 600;
    }
    
    /* En-tête principal stylisé */
    .header-container {
        background: linear-gradient(135deg, #1e1b4b 0%, #311042 50%, #0f172a 100%);
        padding: 2.5rem;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    
    .header-container::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, transparent 60%);
        pointer-events: none;
    }

    .header-title {
        color: #ffffff;
        font-size: 2.5rem;
        margin: 0;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(to right, #a5b4fc, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .header-subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 0.5rem;
        margin-bottom: 0;
    }

    /* Cartes de statistiques */
    .metric-card {
        background: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.15);
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #6366f1;
        margin-bottom: 0.2rem;
        font-family: 'Space Grotesk', sans-serif;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: inherit;
        opacity: 0.75;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Sidebar stylisée */
    section[data-testid="stSidebar"] {
        background-color: #0b0f19;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Boutons personnalisés */
    div.stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
        color: white;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
        width: 100%;
    }
    
    div.stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }
    
    /* Bouton reset */
    .reset-btn button {
        background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
    }
    
    .reset-btn button:hover {
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4) !important;
    }

    /* Style des cartes techniques unifiées */
    .tech-card {
        background-color: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);
    }
    
    .tech-card-header {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 1.15rem;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    
    /* Variantes de couleurs par catégorie */
    .tech-card.languages {
        border-left: 5px solid #6366f1;
    }
    .tech-card.languages .tech-card-header {
        color: #6366f1;
    }
    
    .tech-card.databases {
        border-left: 5px solid #10b981;
    }
    .tech-card.databases .tech-card-header {
        color: #10b981;
    }
    
    .tech-card.frameworks {
        border-left: 5px solid #ec4899;
    }
    .tech-card.frameworks .tech-card-header {
        color: #ec4899;
    }
    
    .tech-card.devops {
        border-left: 5px solid #fbbf24;
    }
    .tech-card.devops .tech-card-header {
        color: #fbbf24;
    }

    .tech-card.packages {
        border-left: 5px solid #64748b;
    }
    .tech-card.packages .tech-card-header {
        color: #64748b;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation de l'état de la session
if "project_graph" not in st.session_state:
    st.session_state.project_graph = None
if "context_text" not in st.session_state:
    st.session_state.context_text = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Barre latérale (Sidebar) - Configuration générale
with st.sidebar:
    st.image("https://img.icons8.com/nolan/128/security-shield.png", width=64)
    st.markdown("### ⚙️ CONFIGURATION")
    
    # 1. Gestion de la clé API
    api_key_env = os.environ.get("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "Clé API Gemini",
        value=api_key_env,
        type="password",
        help="Clé API Gemini (chargée depuis .env si définie)."
    )
    
    # 2. Sélection du modèle
    model_name_env = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    model_name = st.selectbox(
        "Modèle Gemini",
        options=["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0 if model_name_env == "gemini-2.5-flash" else 1,
        help="Sélectionnez le modèle Gemini à utiliser."
    )
    os.environ["GEMINI_MODEL"] = model_name

    st.markdown("---")
    st.markdown("### ℹ️ À PROPOS")
    st.markdown(
        "Cet assistant RAG permet aux RSSI d'analyser la surface d'attaque d'une application "
        "à partir du graphe de dépendances généré par **Graphify**."
    )
    st.markdown("⚠️ *Aucune lecture directe du code source n'est effectuée.*")
    
    # TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe

# En-tête principal de la page
st.markdown("""
<div class="header-container">
    <h1 class="header-title">🛡️ RSSI RAG Assistant</h1>
    <p class="header-subtitle">Analyse architecturale & audit de sécurité logicielle local alimenté par Gemini</p>
</div>
""", unsafe_allow_html=True)

# Étape 1 : Chargement du projet
if st.session_state.project_graph is None:
    st.subheader("📁 Sélectionner un projet à analyser")
    
    # Initialisation de la navigation de fichiers dans st.session_state
    if "current_browse_dir" not in st.session_state:
        default_start = r"C:\Users\axjui\Downloads\projet_stage"
        if not os.path.exists(default_start):
            default_start = os.getcwd()
        st.session_state.current_browse_dir = os.path.abspath(default_start)

    current_dir = st.session_state.current_browse_dir

    # Layout ergonomique en deux colonnes : Chemin absolu + Bouton Parcourir
    col1, col2 = st.columns([4, 1])
    
    with col1:
        path_input = st.text_input(
            "Chemin absolu du dossier :", 
            value=current_dir,
            placeholder="Saisissez, collez ou sélectionnez un chemin..."
        )
        if path_input != current_dir:
            if os.path.exists(path_input) and os.path.isdir(path_input):
                st.session_state.current_browse_dir = os.path.abspath(path_input)
                st.rerun()
            elif path_input.strip():
                st.caption("⚠️ Dossier introuvable ou invalide")
                
    with col2:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True) # Alignement vertical
        if st.button("Parcourir 📂", use_container_width=True):
            try:
                import subprocess
                import sys
                
                # Script avec retours à la ligne explicites pour éviter la SyntaxError des points-virgules
                code = (
                    "import tkinter as tk\n"
                    "from tkinter import filedialog\n"
                    "import sys\n"
                    "root = tk.Tk()\n"
                    "root.withdraw()\n"
                    "root.attributes('-topmost', True)\n"
                    "selected = filedialog.askdirectory(initialdir=sys.argv[1] if len(sys.argv) > 1 else '')\n"
                    "root.destroy()\n"
                    "if selected:\n"
                    "    sys.stdout.buffer.write(selected.encode('utf-8'))\n"
                )
                
                # Lancement du sous-processus de sélection
                result = subprocess.run(
                    [sys.executable, "-c", code, current_dir],
                    capture_output=True
                )
                
                if result.returncode == 0:
                    if result.stdout:
                        selected_dir = result.stdout.decode('utf-8').strip()
                        if selected_dir and os.path.exists(selected_dir):
                            st.session_state.current_browse_dir = os.path.abspath(selected_dir)
                            st.rerun()
                else:
                    err_msg = result.stderr.decode('utf-8', errors='ignore')
                    st.error(f"Erreur du sélecteur : {err_msg}")
            except Exception as e:
                st.error(f"Impossible d'ouvrir l'explorateur : {e}")

    # Bouton d'action unique et toujours visible
    st.markdown(" ")
    if st.button("⚡ Charger ce projet et démarrer l'analyse RAG ⚡", type="primary", use_container_width=True):
        with st.spinner("Analyse et chargement du graphe en cours..."):
            try:
                project = load_project_graph(current_dir)
                context_text = build_context(project)
                st.session_state.project_graph = project
                st.session_state.context_text = context_text
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": (
                            f"Bonjour ! Le projet a été chargé avec succès à partir de **{project.source_path}**.\n\n"
                            f"Le graphe contient **{len(project.nodes)} nœuds** et **{len(project.links)} relations**."
                            " Vous pouvez maintenant me poser vos questions orientées sécurité ou architecture."
                        )
                    }
                ]
                st.rerun()
            except ValueError as e:
                st.error(f"❌ Impossible de charger le projet : {str(e)}")
            except Exception as e:
                st.error(f"❌ Une erreur inattendue est survenue : {str(e)}")

# Étape 2 : Projet chargé, affichage du dashboard et du chat
else:
    project = st.session_state.project_graph
    
    # Bannière récapitulative
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(project.nodes)}</div>
            <div class="metric-label">Nœuds du Graphe</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(project.links)}</div>
            <div class="metric-label">Relations (Liens)</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        # stack
        detect = project.stack_detection
        total_files = detect.get("total_files", len(project.manifest)) if detect else len(project.manifest)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_files}</div>
            <div class="metric-label">Fichiers Scannés</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        # Top god node
        top_god = project.god_nodes[0].get("label", "Aucun") if project.god_nodes else "Aucun"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="font-size: 1.2rem; padding: 0.6rem 0; color: #ec4899; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{top_god}</div>
            <div class="metric-label">Point Critique Principal</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    # Contrôles du projet
    col_path, col_reset = st.columns([4, 1])
    with col_path:
        st.info(f"📂 **Projet actif** : `{project.source_path}` (Commit : `{project.built_at_commit[:8] if project.built_at_commit else 'aucun'}`)")
    with col_reset:
        st.markdown('<div class="reset-btn">', unsafe_allow_html=True)
        reset = st.button("Changer de projet 🔄")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if reset:
            st.session_state.project_graph = None
            st.session_state.context_text = None
            st.session_state.messages = []
            st.rerun()

    tab1, tab2, tab3 = st.tabs([
        "💬 Assistant RAG (Dialogue)",
        "🔍 Surface d'Attaque (Audit)",
        "🛠️ Stack Technique & Dépendances"
    ])

    with tab1:
        st.markdown("### 💬 Espace de Dialogue Sécurité")
        
        # Zone d'affichage des messages
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Zone d'entrée utilisateur
        user_input = st.chat_input("Posez votre question sur la sécurité ou la stack technique...")
        
        if user_input:
            # Afficher la question de l'utilisateur
            with st.chat_message("user"):
                st.markdown(user_input)
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # Obtenir la réponse de Gemini
            with st.chat_message("assistant"):
                with st.spinner("Analyse du graphe en cours..."):
                    # Remplir le prompt système avec le contexte sérialisé
                    prompt_with_context = SYSTEM_PROMPT.format(context=st.session_state.context_text)
                    
                    # Appeler l'API Gemini via notre client
                    response = ask_gemini(
                        system_prompt=prompt_with_context,
                        conversation_history=st.session_state.messages[:-1], # Exclure le dernier message utilisateur
                        user_question=user_input,
                        api_key=api_key
                    )
                    st.markdown(response)
            
            # Enregistrer la réponse
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

    with tab2:
        st.markdown("### 🔍 Audit de la Surface d'Attaque")
        st.markdown(
            "Ces fichiers ont été identifiés comme critiques pour la sécurité de l'application. "
            "Leur criticité est calculée en fonction de leur connectivité globale dans l'architecture, "
            "de leur rôle (point d'entrée ou orchestration) et de la détection sémantique d'opérations sensibles "
            "(accès DB, authentification, cryptographie, réseau)."
        )
        
        if not project.critical_files:
            st.info("Aucun fichier critique n'a été détecté dans ce graphe.")
        else:
            for cf in project.critical_files:
                # Couleur et emoji selon le risque
                if cf["risk_level"] == "Élevé":
                    risk_badge = "🔴 RISQUE ÉLEVÉ"
                elif cf["risk_level"] == "Moyen":
                    risk_badge = "🟠 RISQUE MOYEN"
                else:
                    risk_badge = "🟡 RISQUE FAIBLE"
                    
                expander_title = f"📁 {cf['file']} — Score : {cf['score']} | {risk_badge}"
                
                with st.expander(expander_title):
                    st.markdown("#### ⚠️ Raisons de la criticité :")
                    for reason in cf["reasons"]:
                        st.markdown(f"- **{reason}**")
                        
                    st.markdown("---")
                    st.markdown("#### 💻 Composants clés dans ce fichier (classés par connectivité) :")
                    
                    nodes_list = cf["nodes"]
                    if not nodes_list:
                        st.write("Aucun composant de code extrait.")
                    else:
                        cols = st.columns([3, 1, 1])
                        with cols[0]:
                            st.markdown("**Nom du composant**")
                        with cols[1]:
                            st.markdown("**Connexions (Degré)**")
                        with cols[2]:
                            st.markdown("**Type**")
                            
                        for n in nodes_list[:10]: # Limite à 10 pour la lisibilité
                            with st.container():
                                c1, c2, c3 = st.columns([3, 1, 1])
                                type_emoji = "🧩 Code" if n["file_type"] == "code" else "📝 Rationale"
                                c1.markdown(f"`{n['label']}`")
                                c2.write(f"{n['degree']}")
                                c3.write(f"{type_emoji}")
                        if len(nodes_list) > 10:
                            st.caption(f"*Et {len(nodes_list) - 10} autres composants secondaires dans ce fichier...*")

    with tab3:
        st.markdown("### 🛠️ Stack Technique & Dépendances")
        st.markdown(
            "Voici les technologies et dépendances extraites automatiquement de l'analyse du projet. "
            "Elles sont classées par rôle au sein de l'architecture."
        )
        
        techs = project.detected_technologies
        if not techs:
            st.info("Aucune technologie n'a pu être extraite automatiquement de ce graphe.")
        else:
            col_left, col_right = st.columns(2)
            
            with col_left:
                if "Langages" in techs:
                    lang_items = "".join([f"<li style='margin-bottom:0.4rem;'>{l}</li>" for l in techs["Langages"]])
                    st.markdown(f"""
                    <div class="tech-card languages">
                        <div class="tech-card-header">🔤 Langages de programmation</div>
                        <ul style="margin: 0; padding-left: 1.2rem; font-weight: 500;">
                            {lang_items}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                        
                if "Bases de données & ORM" in techs:
                    db_items = "".join([f"<li style='margin-bottom:0.4rem;'>{d}</li>" for d in techs["Bases de données & ORM"]])
                    st.markdown(f"""
                    <div class="tech-card databases">
                        <div class="tech-card-header">🗄️ Stockage & Bases de données / ORM</div>
                        <ul style="margin: 0; padding-left: 1.2rem; font-weight: 500;">
                            {db_items}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)

            with col_right:
                if "Frameworks & UI" in techs:
                    fw_items = "".join([f"<li style='margin-bottom:0.4rem;'>{fw}</li>" for fw in techs["Frameworks & UI"]])
                    st.markdown(f"""
                    <div class="tech-card frameworks">
                        <div class="tech-card-header">🌐 Frameworks & Moteurs UI</div>
                        <ul style="margin: 0; padding-left: 1.2rem; font-weight: 500;">
                            {fw_items}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                        
                if "Infrastructure & DevOps" in techs:
                    dev_items = "".join([f"<li style='margin-bottom:0.4rem;'>{dev}</li>" for dev in techs["Infrastructure & DevOps"]])
                    st.markdown(f"""
                    <div class="tech-card devops">
                        <div class="tech-card-header">🐳 DevOps, Conteneurs & CI/CD</div>
                        <ul style="margin: 0; padding-left: 1.2rem; font-weight: 500;">
                            {dev_items}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
            
            if "Bibliothèques & Dépendances" in techs:
                packages = techs["Bibliothèques & Dépendances"]
                badges_html = "".join([
                    f"<span style='display:inline-block; background-color:rgba(128, 128, 128, 0.08); color:inherit; border: 1px solid rgba(128, 128, 128, 0.2); border-radius:6px; padding:3px 10px; margin:4px; font-family:monospace; font-size:0.85rem; font-weight:500;'>{p}</span>"
                    for p in packages
                ])
                st.markdown(f"""
                <div class="tech-card packages" style="margin-top: 1rem;">
                    <div class="tech-card-header">📦 Autres Dépendances & Bibliothèques tierces (NPM)</div>
                    <div style="margin-top: 0.5rem; line-height: 1.8;">
                        {badges_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
