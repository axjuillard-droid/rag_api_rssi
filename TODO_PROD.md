# Production Readiness Security TODOs

This file tracks the list of security actions marked with `# TODO sécurité prod:` that must be implemented before moving this PoC application to a production environment.

## Sensibles Data Leakage & Anonymization

Before sending data to any external API (e.g. Gemini Cloud API) or presenting reports to standard users, system-specific files and directory paths must be anonymized to prevent exposing internal infrastructure details or developer usernames.

### Items Identified:

1. **Ingestion Level**  
   * **File**: [ingest.py](file:///c:/Users/axjui/Downloads/rag_api_rssi/ingest.py#L75)  
   * **Action**: `# TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe`  
   * **Description**: The input paths in `.graphify_detect.json` under `scan_root` and `files.code` can expose absolute file system paths of the scanning machine.

2. **Context Building Level**  
   * **File**: [context_builder.py](file:///c:/Users/axjui/Downloads/rag_api_rssi/context_builder.py#L29)  
   * **Action**: `# TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe`  
   * **Description**: Ensure the serialized text block constructed for prompt injection removes or hashes absolute local paths before sending to Gemini.

3. **Application/UI Level**  
   * **File**: [app.py](file:///c:/Users/axjui/Downloads/rag_api_rssi/app.py#L185)  
   * **Action**: `# TODO sécurité prod: anonymiser scan_root et files.code avant tout envoi à une API externe`  
   * **Description**: Make sure any absolute local paths are anonymized before rendering in UI components or sending via API calls.
