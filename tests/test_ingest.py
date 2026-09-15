import os
import unittest
import shutil
import tempfile
from ingest import load_project_graph

class TestIngest(unittest.TestCase):
    REAL_PATH = r"C:\Users\axjui\Downloads\projet_postgrsql_metadata\graphify-out"

    def setUp(self):
        self.real_exists = os.path.exists(self.REAL_PATH)

    def test_load_real_graph(self):
        if not self.real_exists:
            self.skipTest(f"Exemple réel de graphify-out non trouvé à l'emplacement '{self.REAL_PATH}'")
        
        project = load_project_graph(self.REAL_PATH)
        
        # Validation 1: Nombre de nœuds et liens
        self.assertEqual(len(project.nodes), 297, "Le nombre de nœuds doit être égal à 297")
        self.assertEqual(len(project.links), 501, "Le nombre de liens doit être égal à 501")
        
        # Validation 2: Premier god node est get_db_connection()
        self.assertTrue(len(project.god_nodes) > 0, "La liste des god nodes ne doit pas être vide")
        first_god = project.god_nodes[0]
        self.assertIn("get_db_connection", first_god.get("label", ""), "Le premier god node doit être get_db_connection()")
        
        # Validation 3: summary_md n'est pas vide
        self.assertTrue(len(project.summary_md.strip()) > 0, "Le rapport summary_md ne doit pas être vide")
        
        # Vérification de l'encodage UTF-16 de .graphify_detect.json
        self.assertIn("total_files", project.stack_detection, "Le dictionnaire stack_detection doit contenir 'total_files'")
        self.assertEqual(project.stack_detection.get("total_files"), 53, "Le nombre de fichiers dans stack_detection doit être 53")

        # Validation 4: Stack technique et fichiers critiques
        self.assertIn("Langages", project.detected_technologies)
        self.assertIn("Bases de données & ORM", project.detected_technologies)
        self.assertIn("PostgreSQL", project.detected_technologies["Bases de données & ORM"])
        
        self.assertTrue(len(project.critical_files) > 0, "La liste des fichiers critiques ne doit pas être vide")
        critical_filenames = [cf["file"] for cf in project.critical_files]
        self.assertTrue(any("db.py" in f or "app.py" in f for f in critical_filenames), "db.py ou app.py doit être identifié comme critique")

    def test_degraded_mode(self):
        if not self.real_exists:
            self.skipTest("Exemple réel non trouvé")
            
        # On copie l'exemple réel dans un dossier temporaire pour tester le mode dégradé
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copie de tout le dossier sauf .graphify_labels.json
            for item in os.listdir(self.REAL_PATH):
                s = os.path.join(self.REAL_PATH, item)
                d = os.path.join(tmpdir, item)
                if os.path.isdir(s):
                    if item != "cache": # skip cache folder
                        shutil.copytree(s, d)
                else:
                    if item != ".graphify_labels.json":
                        shutil.copy2(s, d)
            
            # On charge depuis le dossier temporaire
            project = load_project_graph(tmpdir)
            
            # Le chargement doit réussir
            self.assertEqual(len(project.nodes), 297)
            # Les labels doivent être un dictionnaire vide
            self.assertEqual(project.labels, {})

    def test_missing_directory_error(self):
        fake_path = r"C:\Users\axjui\Downloads\this_directory_does_not_exist_xyz"
        with self.assertRaises(ValueError) as context:
            load_project_graph(fake_path)
        
        self.assertIn("Le chemin spécifié n'existe pas", str(context.exception))

    def test_missing_graph_json_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crée un dossier sans graph.json
            with self.assertRaises(ValueError) as context:
                load_project_graph(tmpdir)
            self.assertIn("Le fichier obligatoire 'graph.json' est absent", str(context.exception))

if __name__ == "__main__":
    unittest.main()
