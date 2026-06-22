# Spécification d'implémentation — RAG sécurité/techno pour RSSI (basé sur Graphify)

## À l'attention de l'IA qui va implémenter ce projet

Ce document est une spécification d'exécution, pas une simple idée. Il est découpé en **étapes séquentielles**. Chaque étape se termine par une **section "VALIDATION"** : tu dois t'arrêter, exécuter les vérifications listées, et confirmer explicitement leur résultat avant de passer à l'étape suivante. Ne saute jamais une étape, ne fusionne jamais deux étapes pour aller plus vite. Si une validation échoue, corrige avant de continuer.

Si une information te manque ou qu'une instruction est ambiguë, **arrête-toi et signale-le explicitement** plutôt que de deviner. Le coût d'une mauvaise supposition ici est élevé : ce projet traite des données envoyées à un RSSI sur la sécurité d'un système, il vaut mieux une question qu'une fausse certitude.

---

## 0. Contexte produit (à lire avant de coder quoi que ce soit)

**Objectif final** : une application Streamlit locale où l'utilisateur saisit le chemin d'un dossier `graphify-out` (sortie de l'outil `graphify`, qui scanne un projet de code et produit un graphe de dépendances), et peut ensuite poser des questions en langage naturel sur ce projet, orientées **sécurité** (surface d'attaque, points critiques, dépendances à risque) et **techno** (stack, architecture, dette technique). Les réponses sont générées par l'API Gemini, en s'appuyant sur le contenu du graphe.

**Périmètre du PoC** :
- Exécution 100% locale (poste de développement)
- Un seul projet chargé à la fois (pas de multi-projet pour le PoC)
- Le RAG s'appuie **uniquement sur la structure du graphe**, pas sur le code source complet. C'est un choix délibéré : l'analyse est architecturale (qui appelle quoi, qui dépend de quoi, quels sont les nœuds critiques), pas un scan de vulnérabilités ligne par ligne. Ne tente pas d'ouvrir ou de lire les fichiers de code source du projet analysé — seuls les fichiers produits par Graphify sont des entrées valides.
- Pas de vector store / embeddings pour le PoC : tout le contexte structuré du graphe est injecté directement dans le prompt système envoyé à Gemini (voir section 3 pour la justification et les limites de cette approche).
- L'anonymisation des données sensibles (chemins systèmes, etc.) n'est **pas requise pour le PoC**, mais chaque endroit du code qui pourrait en avoir besoin en production doit être marqué par un commentaire `# TODO sécurité prod:`.

---

## 1. Schéma exact des fichiers d'entrée

Ne suppose jamais le format de ces fichiers : il a été vérifié sur un cas réel et est documenté ci-dessous de façon exhaustive. Si les fichiers que tu rencontres en pratique diffèrent de ce schéma, signale-le avant d'adapter le code.

Le dossier `graphify-out/` contient :

```
graphify-out/
├── cache/                      # À ignorer totalement, jamais lu
├── .graphify_analysis.json     # Communautés, god nodes, connexions surprenantes
├── .graphify_detect.json       # Détection stack technique + liste fichiers scannés
├── .graphify_labels.json       # Libellés humains des communautés (souvent juste "Community N")
├── .graphify_python            # Fichier interne Graphify, non structuré, à ignorer
├── .graphify_root              # Fichier interne Graphify, non structuré, à ignorer
├── GRAPH_REPORT.md             # Rapport de synthèse déjà généré, lisible humain
├── graph.html                  # Visualisation interactive, jamais lu par le RAG
├── graph.json                  # LE GRAPHE COMPLET — fichier central
└── manifest.json               # Hash/mtime des fichiers source, pour la fraîcheur
```

### 1.1 `graph.json` — structure exacte

C'est un graphe au format "node-link" (compatible NetworkX `json_graph.node_link_data`). Structure racine :

```json
{
  "directed": true,
  "multigraph": true,
  "graph": {},
  "nodes": [ ... ],
  "links": [ ... ],
  "hyperedges": [],
  "built_at_commit": "7d8b7a3bc2cd..."
}
```

**Champ `nodes`** — liste d'objets, chacun avec :

```json
{
  "label": "get_db_connection()",
  "file_type": "code",
  "source_file": "db.py",
  "source_location": "L50",
  "_origin": "ast",
  "id": "db_get_db_connection",
  "community": 1,
  "norm_label": "get_db_connection()"
}
```

- `id` : identifiant unique du nœud, utilisé dans les `links` pour référencer ce nœud
- `label` : nom lisible (nom de fonction, de fichier, de variable...)
- `file_type` : observé avec deux valeurs possibles : `"code"` (un élément de code réel) ou `"rationale"` (un commentaire/explication extrait du code, souvent du texte en français dans les exemples observés — contient de l'info métier précieuse, à ne pas ignorer)
- `source_file` : chemin relatif du fichier où se trouve cet élément
- `source_location` : ligne dans le fichier source (ex: `"L50"`)
- `community` : entier, référence vers une clé du dictionnaire `communities` dans `.graphify_analysis.json`
- `_origin` : observé avec la valeur `"ast"` (extraction par analyse syntaxique) — peut potentiellement avoir d'autres valeurs sur d'autres projets, ne pas filtrer dessus sauf si nécessaire
- `norm_label` : version normalisée du label, souvent identique à `label`

**Champ `links`** — liste d'objets, chacun avec :

```json
{
  "relation": "calls",
  "confidence": "EXTRACTED",
  "source_file": "app/app.py",
  "source_location": "L556",
  "weight": 1.0,
  "confidence_score": 1.0,
  "source": "app_app",
  "target": "app_app_api_age_distribution"
}
```

- `source` / `target` : les `id` des nœuds reliés (PAS le label — bien utiliser `id`)
- `relation` : type de relation. Valeurs observées : `contains`, `calls`, `imports`, `imports_from`, `references`, `method`, `rationale_for`. **Ne pas supposer que cette liste est exhaustive** — code défensif : toute valeur inconnue doit être affichée telle quelle, jamais provoquer d'erreur.
- `confidence` : observé avec la seule valeur `"EXTRACTED"` dans l'exemple de référence, mais la documentation Graphify mentionne aussi `INFERRED` et `AMBIGUOUS` (visibles dans le résumé de `GRAPH_REPORT.md` : *"100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS"*). Le code doit gérer ces trois valeurs.
- `confidence_score` : float, a priori entre 0 et 1
- `weight` : float, poids de la relation (utilité exacte non garantie, à traiter comme une métadonnée informative, pas comme un signal critique)

**Champs `hyperedges`** : observé vide (`[]`) dans l'exemple de référence. Code défensif : prévoir le cas où cette liste contient des éléments, mais ne pas développer de logique dessus tant qu'aucun exemple réel n'en contient.

**Champ `built_at_commit`** : hash de commit git, string.

### 1.2 `.graphify_analysis.json` — structure exacte

```json
{
  "communities": {
    "0": ["id_node_1", "id_node_2", ...],
    "1": [...]
  },
  "cohesion": {
    "0": 0.0698,
    "1": 0.0803
  },
  "gods": [
    {"id": "db_get_db_connection", "label": "get_db_connection()", "degree": 25}
  ],
  "surprises": [
    {
      "source": "api_cleanup_scan()",
      "target": "run_cleaner()",
      "source_files": ["app/app.py", "cleaner.py"],
      "confidence": "EXTRACTED",
      "relation": "calls",
      "why": "connects across different repos/directories; ..."
    }
  ],
  "tokens": {"input": 0, "output": 0}
}
```

- `communities` : dictionnaire `id_communauté (string) -> liste d'ids de nœuds`
- `cohesion` : dictionnaire `id_communauté (string) -> score de cohésion (float entre 0 et 1)`. Un score bas (< 0.15 environ dans l'exemple) signale une communauté faiblement reliée — candidate à un refactoring, donc pertinent pour l'angle "dette technique"
- `gods` : liste des nœuds les plus connectés (god nodes), triée par `degree` décroissant. **Ce sont les candidats prioritaires pour l'analyse sécurité** (un point de défaillance dans un god node impacte tout ce qui s'y connecte)
- `surprises` : connexions inattendues entre composants éloignés du projet (souvent un signe d'architecture à auditer)
- `tokens` : coût en tokens consommé par Graphify lui-même pour produire ce rapport — sans usage pour le RAG

### 1.3 `.graphify_detect.json` — structure exacte

```json
{
  "files": {
    "code": ["chemin/absolu/fichier1.py", "..."],
    "document": [],
    "paper": [],
    "image": [],
    "video": []
  },
  "total_files": 53,
  "total_words": 20171,
  "needs_graph": false,
  "warning": "Corpus is ~20,171 words - fits in a single context window. You may not need a graph.",
  "skipped_sensitive": ["chemin/absolu/.env.example"],
  "graphifyignore_patterns": 12,
  "scan_root": "chemin/absolu/racine/du/projet"
}
```

**Attention identifiée** : les chemins dans `files.code`, `skipped_sensitive` et `scan_root` peuvent être des **chemins absolus du système de fichiers de la machine où Graphify a été exécuté** (ex: `C:\Users\nom_utilisateur\...`), ce qui peut révéler un nom d'utilisateur ou une arborescence interne. Pour le PoC, ces chemins peuvent être affichés tels quels. Marquer ce point d'un commentaire `# TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe`.

`skipped_sensitive` liste les fichiers exclus par Graphify lui-même (ex: `.env`) — c'est une information positive à afficher à l'utilisateur (« Graphify a déjà exclu ces fichiers sensibles de l'analyse »).

### 1.4 `.graphify_labels.json` — structure exacte

Dictionnaire simple `id_communauté (string) -> libellé humain (string)`. Dans l'exemple de référence, tous les libellés sont génériques (`"Community 0"`, `"Community 1"`...) — ne pas supposer que ces libellés sont toujours descriptifs, le code doit fonctionner même si ce fichier est purement générique.

### 1.5 `GRAPH_REPORT.md`

Fichier Markdown déjà rédigé par Graphify, structuré en sections (`## Summary`, `## Community Hubs`, `## God Nodes`, `## Surprising Connections`, `## Communities`, `## Knowledge Gaps`, `## Suggested Questions`). C'est un résumé de très haute qualité déjà prêt à être consommé par un LLM : **à injecter en grande partie tel quel dans le contexte**, sans chercher à le reparser finement en première version. Une stratégie de parsing par sections (split sur les `##`) est suffisante si besoin de le découper.

### 1.6 `manifest.json`

Dictionnaire `chemin_fichier (string) -> {mtime, ast_hash, semantic_hash}`. Utile uniquement pour informer l'utilisateur de la fraîcheur du graphe (comparer la date du scan à la date actuelle), pas pour l'analyse sécurité elle-même. `semantic_hash` peut être une chaîne vide — gérer ce cas.

---

### VALIDATION — Étape 1

Avant de continuer, l'IA exécutante doit :
1. Confirmer qu'elle a bien accès à un exemple réel de `graphify-out` (au moins `graph.json` et `.graphify_analysis.json`) pour tester le parsing — si aucun exemple n'est disponible, le signaler avant de continuer, car coder un parser sans jamais le tester sur un fichier réel est un risque majeur d'erreur silencieuse.
2. Écrire un script de chargement minimal qui ouvre chaque fichier et affiche son type Python racine (`dict`/`list`) et ses clés de premier niveau — pas de logique métier encore, juste vérifier que chaque fichier est lisible et correspond au schéma ci-dessus.
3. Si un fichier réel diverge du schéma documenté ici (champ manquant, type différent), s'arrêter et documenter précisément la différence avant d'adapter le code.

**Ne pas passer à l'étape 2 sans avoir validé ces trois points.**

---

## 2. Architecture du projet

Structure de fichiers à créer :

```
rag-rssi/
├── .env.example              # Variable GEMINI_API_KEY (vide, juste le nom)
├── .gitignore                 # Doit inclure .env, __pycache__, *.pyc
├── requirements.txt
├── app.py                     # Point d'entrée Streamlit
├── ingest.py                  # Chargement et parsing des fichiers graphify-out
├── context_builder.py         # Sérialisation du graphe en texte pour le prompt
├── gemini_client.py            # Appel à l'API Gemini
├── prompts.py                  # Prompt système et templates
└── tests/
    └── test_ingest.py          # Tests sur un exemple réel de graphify-out
```

**Dépendances (`requirements.txt`)** :
```
streamlit
google-genai
python-dotenv
```

Note : utiliser le SDK Python officiel le plus récent pour l'API Gemini (le nom du package a changé dans le passé entre `google-generativeai` et `google-genai` — vérifier sur la documentation officielle Google au moment de l'implémentation quel est le SDK actuellement recommandé, car cette information peut avoir évolué).

### VALIDATION — Étape 2

1. Confirmer que la structure de dossiers est créée.
2. Confirmer que `requirements.txt` s'installe sans erreur dans un environnement virtuel propre (`pip install -r requirements.txt`).
3. Si le SDK Gemini a changé de nom de package depuis la rédaction de ce document, le signaler explicitement et utiliser le nom à jour.

**Ne pas passer à l'étape 3 sans avoir validé ces points.**

---

## 3. Module `ingest.py`

**Objectif** : charger un dossier `graphify-out` et le transformer en objet Python structuré, en respectant strictement le schéma de la section 1.

### Spécification fonctionnelle

```python
@dataclass
class ProjectGraph:
    nodes: list[dict]          # tous les nœuds de graph.json, tels quels
    links: list[dict]          # tous les liens de graph.json, tels quels
    communities: dict          # depuis .graphify_analysis.json
    cohesion: dict              # depuis .graphify_analysis.json
    god_nodes: list[dict]       # depuis .graphify_analysis.json -> "gods"
    surprises: list[dict]       # depuis .graphify_analysis.json -> "surprises"
    stack_detection: dict        # contenu brut de .graphify_detect.json
    labels: dict                 # contenu de .graphify_labels.json
    summary_md: str              # contenu brut de GRAPH_REPORT.md
    manifest: dict                # contenu de manifest.json
    built_at_commit: str          # depuis graph.json
    source_path: str              # chemin graphify-out fourni par l'utilisateur

def load_project_graph(graphify_out_path: str) -> ProjectGraph:
    """
    Charge tous les fichiers nécessaires depuis graphify_out_path.
    Lève une exception explicite et lisible si :
    - le chemin n'existe pas
    - graph.json est absent (fichier obligatoire, sans lui rien n'est possible)
    - graph.json n'est pas un JSON valide ou ne respecte pas le schéma minimal (clés "nodes" et "links" présentes)

    Pour les autres fichiers (.graphify_analysis.json, .graphify_detect.json,
    .graphify_labels.json, GRAPH_REPORT.md, manifest.json) : s'ils sont absents,
    ne PAS lever d'exception, remplir le champ correspondant avec une valeur
    vide cohérente (dict vide, liste vide, chaîne vide) et logger un avertissement
    clair à l'utilisateur. Le projet doit rester utilisable en mode dégradé.
    """
```

**Exigences précises** :
- Ne jamais utiliser de regex pour parser le JSON — utiliser le module `json` standard.
- Le chemin fourni par l'utilisateur doit être validé avant ouverture (existe, est un dossier).
- Les erreurs doivent être des exceptions Python explicites avec un message destiné à un humain non-développeur (le RSSI verra peut-être ce message dans l'UI) — éviter les stack traces brutes affichées dans l'interface finale.

### VALIDATION — Étape 3

1. Exécuter `load_project_graph()` sur l'exemple réel de `graphify-out` disponible. Confirmer que :
   - `len(project.nodes) == 297` et `len(project.links) == 501` (valeurs attendues sur l'exemple de référence — si l'exemple utilisé est différent, vérifier les comptes annoncés dans `GRAPH_REPORT.md` à la place)
   - `project.god_nodes` contient bien `get_db_connection()` en première position
   - `project.summary_md` n'est pas vide
2. Tester volontairement le mode dégradé : renommer temporairement `.graphify_labels.json`, relancer le chargement, confirmer qu'aucune exception n'est levée et que le programme continue.
3. Tester le cas d'erreur : appeler `load_project_graph()` avec un chemin inexistant, confirmer qu'une exception claire et explicite est levée (pas une erreur Python générique du type `FileNotFoundError` brute sans contexte).

**Ne pas passer à l'étape 4 sans avoir validé ces trois points et montré les résultats (mêmes valeurs en sortie de test).**

---

## 4. Module `context_builder.py`

**Objectif** : transformer un `ProjectGraph` en un bloc de texte structuré, lisible, et raisonnablement compact, destiné à être injecté dans le prompt système de Gemini.

### Pourquoi pas de vector store / embeddings pour ce PoC

Ce choix est délibéré et documenté ici pour que l'IA exécutante ne le remette pas en question sans raison : le fichier `.graphify_detect.json` indique explicitement `needs_graph: false` avec le commentaire *"Corpus fits in single context window"* sur le projet de référence. Les modèles Gemini disposent de fenêtres de contexte large (plusieurs centaines de milliers de tokens selon le modèle choisi). Sérialiser le graphe entier en texte structuré et l'injecter directement dans le prompt système est plus simple, plus fiable (aucune perte de relations entre nœuds liée à un mauvais découpage en chunks), et suffisant pour des projets de cette taille.

**Limite à respecter** : si un projet futur génère un `graph.json` trop gros pour rentrer dans la fenêtre de contexte du modèle Gemini choisi, ce module doit lever une exception claire plutôt que de tronquer silencieusement les données (une troncature silencieuse fausserait l'analyse sécurité sans que l'utilisateur le sache — c'est inacceptable pour ce cas d'usage). Ne pas implémenter de vector store en remplacement à ce stade : juste détecter et signaler le dépassement.

### Spécification fonctionnelle

```python
def build_context(project: ProjectGraph, max_chars: int = 400_000) -> str:
    """
    Construit le contexte texte à injecter dans le prompt système.

    Doit inclure, dans cet ordre :
    1. Métadonnées générales : nombre de nœuds, nombre de liens, commit source,
       stack technique détectée (depuis stack_detection)
    2. La liste des god nodes avec leur degré et leur fichier source
    3. La liste des communautés avec leur score de cohésion et un échantillon
       de leurs nœuds (pas la liste complète si elle est longue — limiter
       pour rester lisible, par exemple 10 nœuds max par communauté affichés,
       avec mention du nombre total)
    4. Les connexions surprenantes (surprises)
    5. Le contenu de GRAPH_REPORT.md, en entier si possible
    6. Pour CHAQUE nœud marqué comme un point d'entrée probable (heuristique :
       label commençant par "api_" ou présent dans un fichier nommé app.py/main.py/routes,
       à affiner selon les vrais patterns observés) : ses relations directes
       (quels liens partent de lui ou arrivent vers lui), pour donner au LLM
       de quoi répondre aux questions de surface d'attaque.

    Si la sérialisation dépasse max_chars caractères, lever une exception
    explicite (ContextTooLargeError) plutôt que de tronquer.

    Retourne une chaîne de texte simple (pas du JSON brut — du texte
    structuré avec des titres, à la manière d'un rapport, pour que le LLM
    l'exploite naturellement).
    """
```

**Important** : ne jamais coller le JSON brut de `graph.json` dans le prompt. Le LLM exploite mieux du texte structuré que du JSON dense — reformuler chaque section en phrases ou listes lisibles, à la manière de `GRAPH_REPORT.md` qui est déjà un bon modèle de référence pour le style attendu.

### VALIDATION — Étape 4

1. Exécuter `build_context()` sur l'exemple réel chargé à l'étape 3. Confirmer que le texte produit :
   - Mentionne bien `get_db_connection()` avec son degré de connexion
   - Mentionne la stack technique détectée
   - Contient le contenu de `GRAPH_REPORT.md`
2. Afficher la longueur en caractères du contexte produit, pour avoir une référence concrète de volumétrie sur ce projet.
3. Tester volontairement le cas de dépassement : appeler `build_context(project, max_chars=100)` et confirmer qu'une exception explicite `ContextTooLargeError` est levée (pas un crash générique).

**Ne pas passer à l'étape 5 sans avoir montré un extrait du texte produit et confirmé les trois points.**

---

## 5. Module `prompts.py`

**Objectif** : définir le prompt système qui cadre le rôle de l'IA, ses limites, et le format de réponse attendu.

### Exigences du prompt système

Le prompt système DOIT explicitement :
1. Définir le rôle : assistant d'analyse d'architecture et de sécurité logicielle, destiné à un RSSI.
2. Préciser que l'analyse s'appuie **uniquement sur la structure du graphe de dépendances** fourni en contexte, pas sur une lecture du code source réel — donc que l'IA ne peut pas détecter de vulnérabilité précise dans une ligne de code (ex: une injection SQL spécifique), mais peut identifier des zones d'attention architecturales (points d'entrée non isolés, dépendances critiques, composants fortement couplés).
3. Demander d'indiquer le niveau de confiance des affirmations en s'appuyant sur le champ `confidence` des relations (`EXTRACTED` = confirmé par analyse syntaxique réelle, `INFERRED` = déduit, `AMBIGUOUS` = incertain) quand cette information est disponible et pertinente pour la question posée.
4. Interdire explicitement d'inventer des informations qui ne sont pas dans le contexte fourni (pas de nom de fichier, de fonction, ou de vulnérabilité non présente dans le graphe).
5. Demander des réponses structurées et concises plutôt que de longs pavés de texte, avec citation du nom exact du nœud/fichier concerné quand pertinent (pour que le RSSI puisse vérifier dans le code réel si besoin).
6. Définir le comportement hors-sujet : si une question n'a aucun rapport avec le projet analysé, le rappeler poliment et recentrer sur le rôle de l'outil.

### VALIDATION — Étape 5

1. Faire relire ce prompt système par un humain (l'utilisateur de ce document) avant de l'utiliser en production — l'IA exécutante doit présenter le texte du prompt complet et attendre une validation explicite, ne pas l'enterrer dans le code sans le montrer séparément.
2. Vérifier que le prompt mentionne explicitement la limite "pas de lecture du code source réel" — point non négociable pour éviter toute fausse attente du RSSI.

**Ne pas passer à l'étape 6 sans avoir présenté le prompt complet pour validation humaine.**

---

## 6. Module `gemini_client.py`

**Objectif** : encapsuler les appels à l'API Gemini.

### Spécification fonctionnelle

```python
def ask_gemini(system_prompt: str, conversation_history: list[dict], user_question: str, api_key: str) -> str:
    """
    Envoie la question à l'API Gemini avec le prompt système et l'historique
    de conversation, retourne la réponse texte.

    Doit gérer explicitement, avec des messages d'erreur clairs destinés
    à être affichés dans l'UI Streamlit :
    - clé API absente ou invalide
    - dépassement de quota
    - timeout réseau
    - réponse vide ou bloquée par les filtres de sécurité du modèle

    Ne JAMAIS faire planter l'application sur une erreur API : toujours
    retourner un message d'erreur utilisateur lisible, jamais une exception
    non gérée qui remonterait jusqu'à l'UI.
    """
```

**Important** : vérifier la documentation officielle Google au moment de l'implémentation pour le nom exact du modèle à utiliser (les noms de modèles Gemini évoluent régulièrement) et la syntaxe exacte du SDK actuel — ne pas se fier uniquement à un nom de modèle mentionné dans une documentation antérieure sans vérifier qu'il est toujours valide.

### VALIDATION — Étape 6

1. Tester un appel réel avec une clé API valide et une question simple (ex: "Bonjour, peux-tu confirmer que tu as bien reçu le contexte du projet ?"), confirmer qu'une réponse cohérente est retournée.
2. Tester volontairement avec une clé API invalide, confirmer que le message d'erreur retourné est clair et ne contient pas de stack trace brute.
3. Confirmer qu'aucune exception non gérée ne remonte dans les trois cas d'erreur listés dans la spec.

**Ne pas passer à l'étape 7 sans avoir validé ces trois points.**

---

## 7. Module `app.py` (Streamlit)

**Objectif** : interface utilisateur finale.

### Spécification fonctionnelle

- Champ de saisie texte pour le chemin `graphify-out`, avec bouton de chargement.
- Au chargement réussi : afficher un résumé immédiat (nombre de nœuds, nombre de liens, stack détectée, top 3 god nodes) — confirmation visuelle que le projet est bien chargé, avant même de poser une question.
- En cas d'erreur de chargement : afficher le message d'erreur de `ingest.py` de façon lisible, ne jamais afficher de stack trace Python brute à l'utilisateur final.
- Zone de chat (`st.chat_message` / `st.chat_input`) pour les questions, avec conservation de l'historique en `st.session_state` pendant la session.
- Champ de saisie de la clé API Gemini en `type="password"`, ou lecture depuis une variable d'environnement si déjà définie (`.env` via `python-dotenv`) — ne jamais écrire la clé API en dur dans le code source.
- Bouton "Changer de projet" qui réinitialise l'état de session (nouveau chargement, historique de chat vidé).

### VALIDATION — Étape 7

1. Lancer `streamlit run app.py`, charger l'exemple réel de `graphify-out`, confirmer que le résumé s'affiche correctement.
2. Poser une question simple liée au projet (ex: "Quelle est la fonction la plus connectée du projet ?") et confirmer que la réponse mentionne bien `get_db_connection()` si l'exemple de référence est utilisé.
3. Tester le cas d'erreur volontaire (chemin invalide) et confirmer qu'aucune stack trace n'apparaît dans l'UI.
4. Tester le bouton "Changer de projet" et confirmer que l'historique de chat est bien vidé.

**Ne pas considérer le PoC comme terminé sans avoir validé ces quatre points.**

---

## 8. Validation finale globale (avant de présenter le PoC au RSSI)

Checklist finale, à parcourir une dernière fois intégralement :

- [ ] L'application se lance sans erreur depuis un environnement Python propre (`pip install -r requirements.txt` puis `streamlit run app.py`)
- [ ] Le chargement d'un dossier `graphify-out` réel fonctionne et affiche un résumé correct
- [ ] Au moins 5 questions différentes ont été testées manuellement, couvrant : un god node, une communauté, la stack technique, une connexion surprenante, et une question hors-sujet (pour vérifier le comportement de recentrage)
- [ ] Aucune clé API n'est présente en dur dans le code source (vérifier avec `grep -ri "AIza" .` ou équivalent selon le format réel des clés Gemini)
- [ ] Le fichier `.env` est bien dans `.gitignore`
- [ ] Tous les `# TODO sécurité prod:` sont regroupés et listés dans un fichier `TODO_PROD.md` à part, pour ne pas les perdre avant un futur passage en production
- [ ] Le prompt système a été présenté à l'utilisateur humain et validé explicitement par lui (pas seulement écrit dans le code)

**Si un seul de ces points n'est pas vérifié, le PoC n'est pas prêt à être montré au RSSI.**

---

## Rappel final pour l'IA exécutante

Ne jamais inventer un détail du schéma de données qui ne figure pas dans la section 1 de ce document. Si un fichier réel rencontré pendant l'implémentation diverge de ce qui est documenté ici, l'écart doit être signalé explicitement avant d'être traité — ne pas corriger silencieusement le code pour s'adapter sans le mentionner. Ce projet alimente des décisions de sécurité ; la traçabilité des écarts entre la spec et la réalité est aussi importante que le code lui-même.
