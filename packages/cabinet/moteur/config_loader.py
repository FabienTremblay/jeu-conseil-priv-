# packages/cabinet/moteur/config_loader.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import subprocess, shutil
import yaml

def _validate_with_schema(yaml_path: Path, schema_path: Path) -> None:
    """Valide avec check-jsonschema si disponible ; sinon passe silencieusement."""
    exe = shutil.which("check-jsonschema")
    if not exe:
        return  # on n'impose pas la présence en runtime
    res = subprocess.run(
        [exe, "--schemafile", str(schema_path), str(yaml_path)],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        raise ValueError(
            f"Le YAML '{yaml_path.name}' ne respecte pas le schéma '{schema_path.name}':\n"
            f"{res.stdout}\n{res.stderr}"
        )

def load_cfg(path_yaml: str | Path, schema_path: str | Path | None = None) -> Dict[str, Any]:
    """
    Charge la config YAML. Si schema_path est fourni, tente une validation via check-jsonschema.
    """
    yaml_p = Path(path_yaml)
    if schema_path is not None:
        _validate_with_schema(yaml_p, Path(schema_path))

    with open(yaml_p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Normalisations éventuelles à ajouter ici...
    return data

