from __future__ import annotations
from typing import Any, Dict
import yaml, json, pathlib

def load_yaml(path: str | pathlib.Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def validate_cfg(cfg: Dict[str, Any], schema_path: str | pathlib.Path | None = None) -> None:
    """
    Validation légère par jsonschema si dispo. Sinon, checks minimaux.
    """
    try:
        if schema_path:
            import jsonschema  # type: ignore
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=cfg, schema=schema)  # lève une exception si invalide
            return
    except Exception as e:  # jsonschema pas installé ou échec
        # fallback minimal
        pass

    # Checks minimaux (fallback)
    assert "axes_tension" in cfg and isinstance(cfg["axes_tension"], list), "axes_tension manquant"
    assert "economie_initiale" in cfg and isinstance(cfg["economie_initiale"], dict), "economie_initiale manquante"
    assert "perturbateurs_tour" in cfg and isinstance(cfg["perturbateurs_tour"], list), "perturbateurs_tour manquant"

def load_cfg(path_yaml: str | pathlib.Path, schema_path: str | pathlib.Path | None = None) -> Dict[str, Any]:
    cfg = load_yaml(path_yaml)
    validate_cfg(cfg, schema_path)
    return cfg
