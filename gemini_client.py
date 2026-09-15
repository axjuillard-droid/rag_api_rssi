import os
from google import genai
from google.genai import types

def ask_gemini(system_prompt: str, conversation_history: list[dict], user_question: str, api_key: str) -> str:
    """
    Envoie la question à l'API Gemini avec le prompt système et l'historique
    de conversation, et retourne la réponse texte.

    Gère explicitement, avec des messages d'erreur clairs destinés à l'UI Streamlit :
    - clé API absente ou invalide
    - dépassement de quota (429 / RESOURCE_EXHAUSTED)
    - timeout réseau
    - réponse vide ou bloquée par les filtres de sécurité du modèle
    """
    if not api_key:
        return "⚠️ Erreur : Clé API absente. Veuillez renseigner votre clé API Gemini dans le panneau latéral ou dans le fichier .env."

    try:
        # Initialise le client avec la clé API fournie
        client = genai.Client(api_key=api_key)
        
        # Récupération du modèle depuis l'environnement ou valeur par défaut
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

        # Conversion de l'historique au format attendu par le SDK google-genai
        # (Chaque élément doit être un types.Content avec un rôle 'user' ou 'model')
        contents = []
        for turn in conversation_history:
            role = turn.get("role", "user")
            # Streamlit utilise souvent 'assistant', l'API attend 'model'
            if role == "assistant":
                role = "model"
            content_text = turn.get("content", "")
            if content_text:
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=content_text)]
                    )
                )

        # Ajoute la nouvelle question de l'utilisateur
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_question)]
            )
        )

        # Configuration de la requête (Prompt système)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2, # Température basse pour privilégier l'exactitude des faits
        )

        # Appel API
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )

        # Gestion de la réponse
        if not response or not response.text:
            # Vérification si la réponse a été bloquée par la sécurité
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason") and str(candidate.finish_reason) == "SAFETY":
                    return "⚠️ La réponse a été bloquée par les filtres de sécurité de l'API Gemini. La question ou le contexte peut contenir des éléments considérés comme sensibles."
            return "⚠️ Erreur : Le modèle a retourné une réponse vide."

        return response.text

    except Exception as e:
        error_msg = str(e)
        
        # Identification des erreurs courantes
        if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg or "403" in error_msg:
            return "⚠️ Erreur : La clé API Gemini fournie est invalide. Veuillez vérifier votre saisie."
        elif "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower() or "429" in error_msg:
            return "⚠️ Erreur : Quota d'API Gemini dépassé (Resource Exhausted). Veuillez patienter quelques minutes avant de rééssayer."
        elif "timeout" in error_msg.lower() or "deadline exceeded" in error_msg.lower():
            return "⚠️ Erreur de Timeout : Le service Gemini a mis trop de temps à répondre. Veuillez réessayer."
        elif "connection" in error_msg.lower() or "http" in error_msg.lower():
            return "⚠️ Erreur réseau : Impossible de se connecter à l'API Gemini. Veuillez vérifier votre connexion internet."
        
        # Autre erreur non interceptée : on renvoie le message d'erreur nettoyé de toute stack trace
        return f"⚠️ Une erreur est survenue lors de l'appel à l'API Gemini : {error_msg}"
