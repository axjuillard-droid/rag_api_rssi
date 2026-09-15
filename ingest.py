import os
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("rag_rssi.ingest")

@dataclass
class ProjectGraph:
    nodes: list[dict]          # tous les nœuds de graph.json, tels quels
    links: list[dict]          # tous les liens de graph.json, tels quels
    communities: dict          # depuis .graphify_analysis.json
    cohesion: dict             # depuis .graphify_analysis.json
    god_nodes: list[dict]      # depuis .graphify_analysis.json -> "gods"
    surprises: list[dict]      # depuis .graphify_analysis.json -> "surprises"
    stack_detection: dict      # contenu brut de .graphify_detect.json
    labels: dict               # contenu de .graphify_labels.json
    summary_md: str            # contenu brut de GRAPH_REPORT.md
    manifest: dict             # contenu de manifest.json
    built_at_commit: str       # depuis graph.json
    source_path: str           # chemin graphify-out fourni par l'utilisateur
    detected_technologies: dict[str, list[str]] = field(default_factory=dict) # stack détectée
    critical_files: list[dict] = field(default_factory=list) # fichiers critiques pour la sécurité


def read_json_file(filepath: str) -> dict | list:
    """
    Lit un fichier JSON avec une gestion robuste de l'encodage (UTF-8 et UTF-16).
    """
    for encoding in ["utf-8", "utf-16", "latin1"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
            return json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            last_err = e
            continue
    raise ValueError(f"Impossible de lire le fichier JSON {filepath} : {last_err}")


def load_project_graph(graphify_out_path: str) -> ProjectGraph:
    """
    Charge tous les fichiers nécessaires depuis graphify_out_path.
    Lève une exception explicite et lisible si :
    - le chemin n'existe pas ou n'est pas un dossier
    - graph.json est absent (fichier obligatoire, sans lui rien n'est possible)
    - graph.json n'est pas un JSON valide ou ne respecte pas le schéma minimal (clés "nodes" et "links" présentes)

    Pour les autres fichiers (.graphify_analysis.json, .graphify_detect.json,
    .graphify_labels.json, GRAPH_REPORT.md, manifest.json) : s'ils sont absents,
    ne PAS lever d'exception, remplir le champ correspondant avec une valeur
    vide cohérente (dict vide, liste vide, chaîne vide) et logger un avertissement
    clair à l'utilisateur. Le projet doit rester utilisable en mode dégradé.
    """
    if not os.path.exists(graphify_out_path):
        raise ValueError(f"Le chemin spécifié n'existe pas : '{graphify_out_path}'")
    
    if not os.path.isdir(graphify_out_path):
        raise ValueError(f"Le chemin spécifié n'est pas un dossier : '{graphify_out_path}'")

    graph_file = os.path.join(graphify_out_path, "graph.json")
    if not os.path.exists(graph_file):
        raise ValueError(f"Le fichier obligatoire 'graph.json' est absent du dossier '{graphify_out_path}'. Le graphe ne peut pas être chargé.")

    try:
        graph_data = read_json_file(graph_file)
    except Exception as e:
        raise ValueError(f"Erreur lors du chargement de 'graph.json' : {str(e)}")

    if not isinstance(graph_data, dict) or "nodes" not in graph_data or "links" not in graph_data:
        raise ValueError("Le fichier 'graph.json' est invalide : il doit être un objet JSON contenant les clés 'nodes' et 'links'.")

    nodes = graph_data.get("nodes", [])
    links = graph_data.get("links", [])
    built_at_commit = graph_data.get("built_at_commit", "")

    # TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe

    # Chargement de .graphify_analysis.json
    analysis_file = os.path.join(graphify_out_path, ".graphify_analysis.json")
    communities = {}
    cohesion = {}
    god_nodes = []
    surprises = []
    if os.path.exists(analysis_file):
        try:
            analysis_data = read_json_file(analysis_file)
            if isinstance(analysis_data, dict):
                communities = analysis_data.get("communities", {})
                cohesion = analysis_data.get("cohesion", {})
                god_nodes = analysis_data.get("gods", [])
                surprises = analysis_data.get("surprises", [])
        except Exception as e:
            logger.warning(f"Impossible de charger .graphify_analysis.json (mode dégradé activé) : {e}")
    else:
        logger.warning(".graphify_analysis.json absent, chargement en mode dégradé.")

    # Chargement de .graphify_detect.json
    detect_file = os.path.join(graphify_out_path, ".graphify_detect.json")
    stack_detection = {}
    if os.path.exists(detect_file):
        try:
            stack_detection = read_json_file(detect_file)
        except Exception as e:
            logger.warning(f"Impossible de charger .graphify_detect.json (mode dégradé activé) : {e}")
    else:
        logger.warning(".graphify_detect.json absent, chargement en mode dégradé.")

    # Chargement de .graphify_labels.json
    labels_file = os.path.join(graphify_out_path, ".graphify_labels.json")
    labels = {}
    if os.path.exists(labels_file):
        try:
            labels = read_json_file(labels_file)
        except Exception as e:
            logger.warning(f"Impossible de charger .graphify_labels.json (mode dégradé activé) : {e}")
    else:
        logger.warning(".graphify_labels.json absent, chargement en mode dégradé.")

    # Chargement de GRAPH_REPORT.md
    report_file = os.path.join(graphify_out_path, "GRAPH_REPORT.md")
    summary_md = ""
    if os.path.exists(report_file):
        # We also want to support UTF-8 / UTF-16 for Markdown report if needed
        for encoding in ["utf-8", "utf-16", "latin1"]:
            try:
                with open(report_file, "r", encoding=encoding) as f:
                    summary_md = f.read()
                break
            except UnicodeDecodeError:
                continue
        if not summary_md:
            logger.warning("Impossible de lire GRAPH_REPORT.md correctement (problème d'encodage).")
    else:
        logger.warning("GRAPH_REPORT.md absent, chargement en mode dégradé.")

    # Chargement de manifest.json
    manifest_file = os.path.join(graphify_out_path, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_file):
        try:
            manifest = read_json_file(manifest_file)
        except Exception as e:
            logger.warning(f"Impossible de charger manifest.json (mode dégradé activé) : {e}")
    else:
        logger.warning("manifest.json absent, chargement en mode dégradé.")

    # Détection automatique de la stack technique et calcul de criticité
    detected_technologies = _detect_technologies(nodes, manifest)
    critical_files = _calculate_critical_files(nodes, links, god_nodes, surprises)

    return ProjectGraph(
        nodes=nodes,
        links=links,
        communities=communities,
        cohesion=cohesion,
        god_nodes=god_nodes,
        surprises=surprises,
        stack_detection=stack_detection,
        labels=labels,
        summary_md=summary_md,
        manifest=manifest,
        built_at_commit=built_at_commit,
        source_path=graphify_out_path,
        detected_technologies=detected_technologies,
        critical_files=critical_files
    )


def _detect_technologies(nodes: list[dict], manifest: dict) -> dict[str, list[str]]:
    """
    Détecte les technologies utilisées dans le projet.
    """
    techs = {
        "Langages": set(),
        "Frameworks & UI": set(),
        "Bases de données & ORM": set(),
        "Bibliothèques & Dépendances": set(),
        "Infrastructure & DevOps": set()
    }
    
    # 1. Analyse des fichiers du manifest et des nœuds
    files = set()
    if manifest:
        files.update(manifest.keys())
    for n in nodes:
        src = n.get("source_file")
        if src:
            files.add(src)
            
    for f in files:
        f_lower = f.lower()
        if f_lower.endswith(".py"):
            techs["Langages"].add("Python")
        elif f_lower.endswith(".ts"):
            techs["Langages"].add("TypeScript")
        elif f_lower.endswith(".tsx"):
            techs["Langages"].add("TypeScript")
            techs["Frameworks & UI"].add("React")
        elif f_lower.endswith(".js"):
            techs["Langages"].add("JavaScript")
        elif f_lower.endswith(".jsx"):
            techs["Langages"].add("JavaScript")
            techs["Frameworks & UI"].add("React")
        elif f_lower.endswith(".go"):
            techs["Langages"].add("Go")
        elif f_lower.endswith(".rs"):
            techs["Langages"].add("Rust")
        elif f_lower.endswith(".java"):
            techs["Langages"].add("Java")
        elif f_lower.endswith(".sh"):
            techs["Langages"].add("Shell Bash")
        elif f_lower.endswith(".ps1"):
            techs["Langages"].add("PowerShell")
            
        if "dockerfile" in f_lower:
            techs["Infrastructure & DevOps"].add("Docker")
        elif "docker-compose" in f_lower:
            techs["Infrastructure & DevOps"].add("Docker Compose")
        elif ".github/workflows" in f_lower:
            techs["Infrastructure & DevOps"].add("GitHub Actions")
        elif "jenkinsfile" in f_lower:
            techs["Infrastructure & DevOps"].add("Jenkins CI")

    # 2. Analyse des labels et rationales des nœuds
    for n in nodes:
        label = n.get("label", "")
        label_lower = label.lower()
        source_file = n.get("source_file", "").lower()
        
        # Dépendances npm dans package.json
        if "package.json" in source_file:
            if label not in ["package.json", "dependencies", "devDependencies", "scripts", "name", "version", "private"]:
                if label in ["react", "react-dom"]:
                    techs["Frameworks & UI"].add("React")
                elif "vue" in label:
                    techs["Frameworks & UI"].add("Vue.js")
                elif "angular" in label:
                    techs["Frameworks & UI"].add("Angular")
                elif "svelte" in label:
                    techs["Frameworks & UI"].add("Svelte")
                elif "next" in label:
                    techs["Frameworks & UI"].add("Next.js")
                elif "vite" in label:
                    techs["Frameworks & UI"].add("Vite")
                elif "tailwindcss" in label or "tailwind" in label:
                    techs["Frameworks & UI"].add("Tailwind CSS")
                elif "express" in label:
                    techs["Frameworks & UI"].add("Express")
                elif "prisma" in label:
                    techs["Bases de données & ORM"].add("Prisma ORM")
                elif "mongoose" in label or "mongodb" in label:
                    techs["Bases de données & ORM"].add("MongoDB / Mongoose")
                elif label in ["pg", "pg-pool", "postgres"]:
                    techs["Bases de données & ORM"].add("PostgreSQL")
                else:
                    techs["Bibliothèques & Dépendances"].add(label)
                    
        # Mots-clés dans les autres types de nœuds
        if n.get("file_type") in ["rationale", "code"]:
            if any(x in label_lower for x in ["postgresql", "postgres", "psycopg"]):
                techs["Bases de données & ORM"].add("PostgreSQL")
            if "sqlite" in label_lower:
                techs["Bases de données & ORM"].add("SQLite")
            if "mysql" in label_lower:
                techs["Bases de données & ORM"].add("MySQL")
            if "mongodb" in label_lower or "mongo" in label_lower:
                techs["Bases de données & ORM"].add("MongoDB")
            if "redis" in label_lower:
                techs["Bases de données & ORM"].add("Redis")
            if "sqlalchemy" in label_lower:
                techs["Bases de données & ORM"].add("SQLAlchemy (Python)")
            if "flask" in label_lower:
                techs["Frameworks & UI"].add("Flask")
            if "fastapi" in label_lower:
                techs["Frameworks & UI"].add("FastAPI")
            if "streamlit" in label_lower:
                techs["Frameworks & UI"].add("Streamlit")
            if "django" in label_lower:
                techs["Frameworks & UI"].add("Django")

    # Nettoyage et tri
    result = {}
    for cat, items in techs.items():
        if items:
            result[cat] = sorted(list(items))
            
    return result


def _calculate_critical_files(nodes: list[dict], links: list[dict], god_nodes: list[dict], surprises: list[dict]) -> list[dict]:
    """
    Calcule la criticité de chaque fichier pour la sécurité.
    """
    file_data = {}
    
    # Mapper des god nodes
    god_ids = {g.get("id") for g in god_nodes if g.get("id")}
    god_labels = {g.get("label") for g in god_nodes if g.get("label")}
    
    # Fichiers impliqués dans les surprises
    surprise_files = set()
    for s in surprises:
        for sf in s.get("source_files", []):
            surprise_files.add(sf)
            
    # Calcul des degrés de connexion des nœuds
    node_degrees = {}
    for link in links:
        src = link.get("source")
        tgt = link.get("target")
        if src:
            node_degrees[src] = node_degrees.get(src, 0) + 1
        if tgt:
            node_degrees[tgt] = node_degrees.get(tgt, 0) + 1

    for n in nodes:
        filename = n.get("source_file")
        if not filename:
            continue
            
        f_lower = filename.lower()
        # Ignorer les fichiers de configuration de build / styles dans l'audit de code critique
        if any(ignored in f_lower for ignored in ["package.json", "tsconfig", "vite.config", "postcss.config", "tailwind.config", ".gitignore"]):
            continue
            
        if filename not in file_data:
            file_data[filename] = {
                "file": filename,
                "score": 0,
                "reasons": set(),
                "nodes": [],
                "total_degree": 0
            }
            
        n_id = n.get("id")
        n_label = n.get("label", "")
        n_label_lower = n_label.lower()
        
        degree = node_degrees.get(n_id, 0)
        file_data[filename]["total_degree"] += degree
        file_data[filename]["nodes"].append({
            "id": n_id,
            "label": n_label,
            "degree": degree,
            "file_type": n.get("file_type")
        })
        
        # 1. Présence de God Nodes
        if n_id in god_ids or n_label in god_labels:
            file_data[filename]["reasons"].add("Contient un composant critique (God Node)")
            file_data[filename]["score"] += 50
            
        # 2. Rôle de point d'entrée / API
        is_api = n_label_lower.startswith("api_") or n_label_lower.startswith("/api/")
        is_entry = any(entry in f_lower for entry in ["app.py", "main.py", "routes.py", "start.py", "server.js", "index.ts", "main.tsx"])
        if is_api:
            file_data[filename]["reasons"].add("Contient des points d'entrée d'API")
            file_data[filename]["score"] += 30
        if is_entry:
            file_data[filename]["reasons"].add("Fichier d'entrée / orchestration principal")
            file_data[filename]["score"] += 20
            
        # 3. Opérations sensibles détectées sémantiquement
        sensitive_terms = {
            "db": ("Gestion / Persistance base de données", 25),
            "sql": ("Requêtes SQL / Accès base de données", 25),
            "postgres": ("Accès PostgreSQL", 25),
            "sqlite": ("Accès SQLite", 20),
            "auth": ("Gestion de l'authentification", 35),
            "login": ("Gestion de l'authentification", 35),
            "jwt": ("Gestion de jetons d'accès (JWT)", 30),
            "token": ("Gestion de jetons / API tokens", 25),
            "crypt": ("Opérations de cryptographie", 30),
            "password": ("Gestion de mots de passe / informations sensibles", 35),
            "cipher": ("Opérations de cryptographie / chiffrement", 30),
            "fetch": ("Appels réseau / Clients HTTP", 15),
            "request": ("Appels réseau / Clients HTTP", 15),
            "connect": ("Connexions réseau / socket", 15)
        }
        
        for term, (desc, points) in sensitive_terms.items():
            if term in n_label_lower:
                file_data[filename]["reasons"].add(desc)
                file_data[filename]["score"] += points

    # 4. Connexions inattendues
    for filename in file_data:
        if filename in surprise_files:
            file_data[filename]["reasons"].add("Impliqué dans des couplages architecturaux inattendus (Surprises)")
            file_data[filename]["score"] += 25
            
        # Ajustement du score selon la connectivité globale du fichier
        deg_score = min(30, file_data[filename]["total_degree"] // 2)
        file_data[filename]["score"] += deg_score
        
    # Formatage et tri par score décroissant
    sorted_files = []
    for filename, data in file_data.items():
        if data["score"] > 0:
            score = data["score"]
            if score >= 80:
                risk_level = "Élevé"
            elif score >= 35:
                risk_level = "Moyen"
            else:
                risk_level = "Faible"
                
            data["nodes"] = sorted(data["nodes"], key=lambda x: x["degree"], reverse=True)
            
            sorted_files.append({
                "file": filename,
                "score": score,
                "risk_level": risk_level,
                "reasons": sorted(list(data["reasons"])),
                "nodes": data["nodes"]
            })
            
    return sorted(sorted_files, key=lambda x: x["score"], reverse=True)
