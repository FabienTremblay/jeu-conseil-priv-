from __future__ import annotations
from typing import Any, Dict
from .config_loader import load_cfg
from .factories import construire_etat
from .etat import Etat

def charger_etat_depuis_yaml(path_yaml: str, schema_path: str | None = None) -> Etat:
    cfg: Dict[str, Any] = load_cfg(path_yaml, schema_path=schema_path)
    return construire_etat(cfg)
