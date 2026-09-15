import os
from ingest import ProjectGraph

class ContextTooLargeError(Exception):
    """
    Exception levée lorsque le contexte généré dépasse la taille maximale autorisée.
    """
    pass

def build_context(project: ProjectGraph, max_chars: int = 400_000) -> str:
    """
    Construit le contexte texte à injecter dans le prompt système.

    Doit inclure, dans cet ordre :
    1. Métadonnées générales : nombre de nœuds, nombre de liens, commit source,
       stack technique détectée (depuis stack_detection)
    2. La liste des god nodes avec leur degré et leur fichier source
    3. La liste des communautés avec leur score de cohésion et un échantillon
       de leurs nœuds (limité à 10 max par communauté, avec mention du total)
    4. Les connexions surprenantes (surprises)
    5. Le contenu de GRAPH_REPORT.md, en entier
    6. Pour CHAQUE nœud marqué comme un point d'entrée probable (heuristique :
       label/norm_label commençant par "api_" ou "/api/" ou présent dans un fichier 
       nommé app.py/main.py/routes) : ses relations directes (liens entrants et sortants), 
       pour donner au LLM la surface d'attaque précise.
    
    Lève ContextTooLargeError si le contexte dépasse max_chars.
    """
    # TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe

    lines = []
    
    # 1. Métadonnées générales
    lines.append("# METADONNÉES GÉNÉRALES DU PROJET")
    lines.append(f"- Dossier analysé : {project.source_path}")
    lines.append(f"- Commit de build : {project.built_at_commit if project.built_at_commit else 'Inconnu'}")
    lines.append(f"- Nombre total de nœuds : {len(project.nodes)}")
    lines.append(f"- Nombre total de relations (liens) : {len(project.links)}")
    
    detect = project.stack_detection
    if detect:
        total_files = detect.get("total_files", "Inconnu")
        total_words = detect.get("total_words", "Inconnu")
        lines.append(f"- Nombre de fichiers de code analysés : {total_files}")
        lines.append(f"- Nombre estimé de mots : {total_words}")
        
        # Liste des fichiers sensibles ignorés
        skipped = detect.get("skipped_sensitive", [])
        if skipped:
            lines.append("- Fichiers sensibles détectés et exclus de l'analyse (par précaution) :")
            for f in skipped:
                lines.append(f"  * {f}")
        else:
            lines.append("- Aucun fichier sensible exclu (ou liste non définie).")
    lines.append("")

    # 1b. Technologies détectées
    lines.append("## STACK TECHNIQUE DÉTECTÉE")
    if project.detected_technologies:
        for category, list_techs in project.detected_technologies.items():
            lines.append(f"- **{category}** : {', '.join(list_techs)}")
    else:
        lines.append("- Aucune technologie spécifique détectée.")
    lines.append("")

    # 1c. Fichiers critiques pour la sécurité
    lines.append("## FICHIERS CRITIQUES À AUDITER POUR LA SÉCURITÉ")
    lines.append("Ces fichiers ont été identifiés comme critiques en raison de leur connectivité élevée, "
                 "de leur rôle de point d'entrée ou de la détection d'opérations sensibles (DB, Auth, Crypto, Réseau) :")
    if project.critical_files:
        for idx, cf in enumerate(project.critical_files[:15], 1): # Top 15 max dans le prompt pour garder le contexte compact
            reasons_str = ", ".join(cf["reasons"])
            lines.append(f"{idx}. `{cf['file']}` (Risque : **{cf['risk_level']}**, Score : {cf['score']})")
            lines.append(f"   * Raisons : {reasons_str}")
            # Top 3 nodes in this file
            top_nodes = [f"`{n['label']}` (degré {n['degree']})" for n in cf["nodes"][:3]]
            if top_nodes:
                lines.append(f"   * Éléments clés : {', '.join(top_nodes)}")
    else:
        lines.append("- Aucun fichier critique identifié.")
    lines.append("")

    # 2. God nodes
    lines.append("## NŒUDS MAJEURS DU SYSTÈME (GOD NODES)")
    lines.append("Ces nœuds ont un grand nombre de connexions directes et représentent les points critiques d'architecture :")
    if project.god_nodes:
        for idx, god in enumerate(project.god_nodes, 1):
            label = god.get("label", god.get("id", ""))
            degree = god.get("degree", 0)
            # Find source file from nodes list if not present
            source_file = "Fichier inconnu"
            for n in project.nodes:
                if n.get("id") == god.get("id") or n.get("label") == label:
                    source_file = n.get("source_file", "Fichier inconnu")
                    break
            lines.append(f"{idx}. `{label}` (Degré : {degree}, Fichier : `{source_file}`)")
    else:
        lines.append("- Aucun god node listé.")
    lines.append("")

    # 3. Communautés
    lines.append("## MODULES ET COMMUNAUTÉS D'ARCHITECTURE")
    lines.append("Les nœuds sont regroupés en communautés. Un score de cohésion faible (< 0.15) suggère un couplage lâche ou des responsabilités mixtes :")
    
    # Mapper pour les nœuds par communauté
    nodes_by_community = {}
    node_by_id = {}
    for n in project.nodes:
        node_by_id[n.get("id")] = n
        comm_id = str(n.get("community", "none"))
        if comm_id not in nodes_by_community:
            nodes_by_community[comm_id] = []
        nodes_by_community[comm_id].append(n)
        
    for comm_id, node_list in nodes_by_community.items():
        if comm_id == "none":
            continue
        # Récupère le libellé humain si disponible
        comm_label = project.labels.get(comm_id, f"Community {comm_id}")
        cohesion_score = project.cohesion.get(comm_id, "Inconnue")
        if isinstance(cohesion_score, float):
            cohesion_str = f"{cohesion_score:.4f}"
        else:
            cohesion_str = str(cohesion_score)
            
        total_nodes = len(node_list)
        lines.append(f"### {comm_label} (ID: {comm_id})")
        lines.append(f"- Score de cohésion interne : {cohesion_str}")
        lines.append(f"- Nombre total de nœuds : {total_nodes}")
        
        # Échantillon de nœuds
        sample_size = min(10, total_nodes)
        sample_nodes = node_list[:sample_size]
        sample_labels = [f"`{n.get('label')}`" for n in sample_nodes]
        sample_str = ", ".join(sample_labels)
        if total_nodes > sample_size:
            sample_str += f" (+ {total_nodes - sample_size} autres nœuds)"
        lines.append(f"- Nœuds (échantillon) : {sample_str}")
        lines.append("")

    # 4. Connexions surprenantes
    lines.append("## RELATIONS ARCHITECTURALES INATTENDUES (SURPRISES)")
    lines.append("Ces liens relient des parties éloignées du système et méritent une attention de sécurité/qualité :")
    if project.surprises:
        for s in project.surprises:
            src = s.get("source", "")
            tgt = s.get("target", "")
            rel = s.get("relation", "calls")
            conf = s.get("confidence", "EXTRACTED")
            why = s.get("why", "")
            files = ", ".join(s.get("source_files", []))
            lines.append(f"- `{src}` --[{rel} ({conf})]--> `{tgt}`")
            if why:
                lines.append(f"  * Explication : {why}")
            if files:
                lines.append(f"  * Fichiers impactés : {files}")
    else:
        lines.append("- Aucune surprise détectée.")
    lines.append("")

    # 5. GRAPH_REPORT.md
    lines.append("## RAPPORT DE SYNTHÈSE DE HAUT NIVEAU (GRAPH_REPORT.MD)")
    if project.summary_md:
        lines.append(project.summary_md.strip())
    else:
        lines.append("Aucun rapport de synthèse disponible.")
    lines.append("")

    # 6. Direct relations for entry points (Surface d'attaque)
    lines.append("## SURFACE D'ATTAQUE : ENTRÉES ET DÉPENDANCES DIRECTES")
    lines.append("Détails des points d'entrée probables de l'application (fonctions API, scripts principaux, ou routes) et leurs appels directs :")
    
    entry_point_nodes = []
    for n in project.nodes:
        label = n.get("label", "")
        norm_label = n.get("norm_label", "")
        source_file = n.get("source_file", "")
        
        is_api_label = label.lower().startswith("api_") or norm_label.lower().startswith("api_") or label.lower().startswith("/api/")
        is_entry_file = any(f in source_file.lower() for f in ["app.py", "main.py", "routes"])
        
        if is_api_label or is_entry_file:
            entry_point_nodes.append(n)
            
    if entry_point_nodes:
        for ep in entry_point_nodes:
            ep_id = ep.get("id")
            ep_label = ep.get("label", ep_id)
            ep_file = ep.get("source_file", "Inconnu")
            ep_loc = ep.get("source_location", "")
            
            lines.append(f"### Point d'entrée : `{ep_label}` (Fichier : `{ep_file}` {ep_loc})")
            
            # Liens sortants et entrants
            relations = []
            for link in project.links:
                src = link.get("source")
                tgt = link.get("target")
                relation = link.get("relation", "calls")
                confidence = link.get("confidence", "EXTRACTED")
                
                if src == ep_id:
                    # Liens sortants (ce que le point d'entrée appelle)
                    target_node = node_by_id.get(tgt)
                    target_label = target_node.get("label", tgt) if target_node else tgt
                    target_file = target_node.get("source_file", "Inconnu") if target_node else "Inconnu"
                    relations.append(f"  - Appelle (relation: {relation}, confiance: {confidence}) : `{target_label}` (dans `{target_file}`)")
                elif tgt == ep_id:
                    # Liens entrants (ce qui appelle le point d'entrée)
                    source_node = node_by_id.get(src)
                    source_label = source_node.get("label", src) if source_node else src
                    source_file = source_node.get("source_file", "Inconnu") if source_node else "Inconnu"
                    relations.append(f"  - Est appelé par (relation: {relation}, confiance: {confidence}) : `{source_label}` (dans `{source_file}`)")
            
            if relations:
                lines.extend(relations)
            else:
                lines.append("  - Aucune relation directe extraite.")
            lines.append("")
    else:
        lines.append("- Aucun point d'entrée identifié par les heuristiques.")
    lines.append("")

    # Construction du contexte complet
    full_context = "\n".join(lines)
    
    # Vérification de dépassement de limite
    if len(full_context) > max_chars:
        raise ContextTooLargeError(
            f"Le contexte généré ({len(full_context)} caractères) dépasse la limite maximale autorisée de {max_chars} caractères. "
            "Le graphe est trop volumineux pour être injecté en entier."
        )
        
    return full_context
