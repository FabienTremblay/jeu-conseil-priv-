import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]  # …/packages
# ajouter la racine du repo (un cran au-dessus de "packages")
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
