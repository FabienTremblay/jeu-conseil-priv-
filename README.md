# 🏛️ Cabinet – Moteur de jeu politique

## 🎯 Objectif

**Cabinet** est le moteur d’un jeu de simulation politique et économique.  
Il modélise des axes de tension (santé, sécurité, économie…), l’économie nationale, les joueurs (gouvernement, opposition, puissances), les programmes de tour et les événements perturbateurs.  

Le projet est organisé pour :

- charger une **configuration YAML** (ou “skin”) définissant la situation initiale ;
- valider sa structure par un **schéma JSON** ;
- construire un **État complet** (`Etat`) sous forme de dataclasses Python ;
- tester la cohérence et les invariants avec **pytest**.

---

## 🗂️ Structure du dépôt

```bash
packages/cabinet/
├── moteur/ # Cœur du moteur (dataclasses, usines, bootstrap)
│ ├── etat.py # Modèle de domaine complet
│ ├── factories.py # Construction de l'État depuis la config
│ ├── config_loader.py # Lecture YAML et validation minimale
│ └── bootstrap.py # Entrée unique : charger_etat_depuis_yaml()
│
├── schemas/
│ └── regles.schema.json # Schéma JSON de validation des skins
│
├── skins/
│ ├── demo_minimal.yaml # Exemple de configuration valide
│ └── archives/ # Anciens skins (exclus des tests)
│
└── tests/
├── unit/ # Tests unitaires (ex: factories, état)
├── integration/ # Tests d’intégration et de validation YAML
└── conftest.py # Configuration Pytest
```

## ⚙️ Installation et environnement

### 1️⃣ Prérequis

- Python ≥ 3.12  
- Environnement virtuel actif (`venv` ou `poetry`)

### 2️⃣ Dépendances minimales

```bash
pip install pyyaml pytest check-jsonschema
```
### 3️⃣ Exécution rapide
```bash
pytest -q
```
##✅ Validation des fichiers YAML (skins)
###Commande directe
```bash
check-jsonschema \
  --schemafile packages/cabinet/schemas/regles.schema.json \
  packages/cabinet/skins/*.yaml
```
Valide tous les fichiers YAML/JSON contre le schéma.

Supporte plusieurs fichiers en une commande.

Échoue si un skin ne respecte pas la structure ou les types.

Makefile (optionnel)
makefile
Copier le code
validate:
	check-jsonschema --schemafile packages/cabinet/schemas/regles.schema.json packages/cabinet/skins/*.yaml
Puis :

bash
Copier le code
make validate
🧪 Tests
1️⃣ Lancer tous les tests
bash
Copier le code
pytest
2️⃣ Exclure des répertoires spécifiques
(archives, dist, etc.)

ini
Copier le code
# pytest.ini
[pytest]
norecursedirs =
    .* build dist node_modules archives
addopts =
    --ignore-glob="**/archives/*"
3️⃣ Tests présents
Type	Fichier	Vérifie
Unitaires	unit/test_factories.py	Construction d’un Etat valide depuis YAML
Intégration	integration/test_bootstrap_end_to_end.py	Chaîne complète de chargement
Validation multi-skins	integration/test_all_skins.py	Tous les skins sauf /archives conformes au schéma

4️⃣ Exemple de test paramétré
python
Copier le code
@pytest.mark.parametrize("skin", sorted(_iter_skins(SKINS_DIR)))
def test_skin_valide(skin):
    res = subprocess.run(
        ["check-jsonschema", "--schemafile", str(SCHEMA), str(skin)],
        capture_output=True, text=True
    )
    assert res.returncode == 0, f"{skin} invalide:\n{res.stdout}\n{res.stderr}"
🧰 Bonnes pratiques
🔹 Ajout d’un nouveau skin
Crée un fichier packages/cabinet/skins/mon_skin.yaml.

Vérifie sa validité :

bash
Copier le code
make validate
Lance les tests :

bash
Copier le code
pytest -q
Observe les erreurs éventuelles de schéma ou de cohérence métier.

🔹 Extension du schéma
Ajoute les nouvelles propriétés dans regles.schema.json.

Garde additionalProperties: false pour éviter les oublis de clé.

Versionne le schéma si tu veux gérer plusieurs versions de règles.

🔹 Nomme clairement tes skins
Exemple :

demo_minimal.yaml — base de test unitaire

scenario_crise.yaml — scénario d’événements multiples

archives/ — anciens tests ou données non conformes (ignorés)

🧭 Étapes suivantes
Objectif	Prochaines actions
Automatisation CI/CD	GitHub Actions (validation + tests + badges)
Pré-commit	Hook check-jsonschema pour valider avant chaque commit
Extension gameplay	Ajouter les modules “actions”, “événements”, “résolution de tour”
Couverture	Ajouter un test de logique pour chaque type de carte
Documentation	Générer la doc API du moteur (pdoc, mkdocs, etc.)

📜 Licence et crédits
Projet interne — simulation éducative et stratégique.
Auteur : Fabien Tremblay
Langage : Python 3.12+
Style : code et commentaires en français pour clarté pédagogique.
