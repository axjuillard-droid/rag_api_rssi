# 🛡️ CISO RAG Assistant — Graphify & Gemini

> **Assistant RAG d'analyse d'architecture logicielle & d'audit de sécurité pour RSSI et équipes Cybersécurité.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Gemini API](https://img.shields.io/badge/Google%20Gemini-API-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)

---

## 📌 Présentation

**CISO RAG Assistant** est une application web locale qui permet aux responsables de la sécurité des systèmes d'information (RSSI), auditeurs et architectes logiciels d'analyser la surface d'attaque, la stack technique et la dette architecturale d'une application à partir du graphe de dépendances généré par **[Graphify](https://github.com/graphify)**.

### 🔒 Approche Privacy-First
L'assistant s'appuie **uniquement sur la structure du graphe de dépendances** (`graphify-out/`) et le rapport synthétique `GRAPH_REPORT.md`. **Aucune lecture directe du code source n'est effectuée**, garantissant une analyse haut niveau centrée sur l'architecture sans exposer le code ligne par ligne.

---

## 🌟 Fonctionnalités Principales

- **💬 Espace de Dialogue RAG** : Posez vos questions en langage naturel sur l'architecture, les dépendances critiques ou les risques potentiels. Réponses générées par **Google Gemini** (`gemini-2.5-flash` / `gemini-2.5-pro`).
- **🔍 Audit de Surface d'Attaque** : Détection automatique des fichiers critiques basés sur :
  - La centralité dans le graphe (*God Nodes* / nœuds hautement connectés)
  - La présence d'opérations sensibles (Accès Base de données, Authentification, Réseau, Cryptographie)
  - Le calcul d'un score de criticité et d'un niveau de risque (Élevé 🔴, Moyen 🟠, Faible 🟡).
- **🛠️ Cartographie de la Stack Technique** : Identification et catégorisation automatique :
  - Langages de programmation
  - Bases de données & ORM
  - Frameworks & UI
  - Infrastructure & DevOps
  - Dépendances et bibliothèques tierces (NPM / PyPI)
- **📊 Tableaux de Bord & Métriques** : Visualisation instantanée du nombre de nœuds, liens, fichiers scannés et composants pivots (*God Nodes*).
- **🎨 Design Premium & Glassmorphic** : Interface sombre moderne développée sous Streamlit avec typographies Google Fonts (*Outfit* / *Space Grotesk*).

---

## 🏗️ Architecture du Projet

```text
rag_api_rssi/
├── app.py                 # Application principale Streamlit (UI & Navigation)
├── ingest.py              # Parsage et validation des sorties Graphify
├── context_builder.py     # Sérialisation du graphe en contexte pour le LLM
├── gemini_client.py       # Client d'intégration Gemini avec gestion d'erreurs
├── prompts.py             # Prompt système et cadrage du rôle RSSI
├── requirements.txt       # Dépendances Python du projet
├── .env.example           # Modèle de variables d'environnement
├── .gitignore             # Fichiers et répertoires ignorés par Git
└── tests/
    └── test_ingest.py     # Suite de tests unitaires pour l'ingestion de données
```

---

## 🚀 Démarrage Rapide

### 1. Prérequis
- **Python 3.10+** installé.
- Une clé API Google Gemini (obtenable gratuitement sur [Google AI Studio](https://aistudio.google.com/)).

### 2. Installation

1. **Cloner le dépôt Git :**
   ```bash
   git clone https://github.com/axjuillard-droid/rag_api_rssi.git
   cd rag_api_rssi
   ```

2. **Créer et activer un environnement virtuel :**
   - **Windows (PowerShell) :**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS :**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Installer les dépendances :**
   ```bash
   pip install -r requirements.txt
   ```

### 3. Configuration de la Clé API

Vous pouvez configurer la clé API de deux manières :
- **Fichier `.env`** *(Recommandé)* :
  Copiez `.env.example` en `.env` et ajoutez votre clé :
  ```env
  GEMINI_API_KEY=AIzaSy...votre_cle_api...
  GEMINI_MODEL=gemini-2.5-flash
  ```
- **Interface Streamlit** : Saisissez votre clé directement dans le panneau latéral (Sidebar) au lancement.

### 4. Lancement de l'Application

```bash
streamlit run app.py
```
L'application s'ouvrira automatiquement à l'adresse : `http://localhost:8501`.

---

## 📁 Entrées Graphify attendues

Pour analyser un projet, indiquez dans l'application le chemin d'un dossier contenant les fichiers générés par **Graphify** (`graphify-out/`) :

- `graph.json` *(Obligatoire)* : Structure du graphe (nœuds et liens de dépendances).
- `.graphify_analysis.json` : Communautés et *God Nodes*.
- `.graphify_detect.json` : Détection de la stack technique.
- `GRAPH_REPORT.md` : Rapport de synthèse du projet.

---

## 🛡️ Sécurité & Confidentialité

- La clé API Gemini n'est **jamais stockée en dur** ni transmise à des tiers.
- Les fichiers `.env`, `.venv` et les sorties brutes de scans (`graphify-out/`) sont systématiquement ignorés par `.gitignore`.

---

## 📜 Licence

Projet développé dans le cadre d'un audit de sécurité et d'analyse architecturale logicielle RAG.
