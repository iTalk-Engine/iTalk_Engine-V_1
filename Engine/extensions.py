import os
import importlib.util
import json
import traceback
from typing import Any, Callable, Dict, List, Optional

class ExtensionManager:
    """
    Gère le chargement, déchargement et exécution des hooks des extensions pour ItalkEngine.
    """

    def __init__(
        self,
        engine: Any,
        extensions_folder: str = 'extensions',
        config_path: str = 'extensions/config.json',
        logger: Optional[Any] = None
    ):
        self.engine = engine
        self.extensions_folder = extensions_folder
        self.config_path = config_path
        self.logger = logger
        self.extensions: Dict[str, Any] = {}   # {nom_extension: module}
        self.hooks: Dict[str, List[Callable]] = {
            'on_init': [],
            'on_connect': [],
            'on_disconnect': [],
            'on_message': [],
            'on_error': [],
        }

    # --- Logging interne ---
    def log(self, msg: str, level: str = "info") -> None:
        if self.logger:
            getattr(self.logger, level, self.logger.info)(msg)
        else:
            print(f"[ExtensionManager] {level.upper()}: {msg}")

    # --- Config ---
    def load_config(self) -> List[str]:
        if not os.path.isfile(self.config_path):
            self.log(f"Aucun fichier config trouvé ({self.config_path})", "warning")
            return []
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return cfg.get('extensions', [])
        except Exception as e:
            self.log(f"Erreur chargement config extensions: {e}", "error")
            return []

    # --- Chargement extensions ---
    def load_extensions(self) -> None:
        extension_names = self.load_config()
        for name in extension_names:
            self.load_extension(name)
        self.call_hook('on_init')

    def load_extension(self, name: str) -> None:
        path = os.path.join(self.extensions_folder, f"{name}.py")
        if not os.path.isfile(path):
            self.log(f"Extension non trouvée : {path}", "warning")
            return
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if not spec or not spec.loader:
                self.log(f"Impossible de charger spec pour {name}", "error")
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.extensions[name] = module
            self.log(f"Extension chargée : {name}")

            # Enregistrement des hooks
            for hook in self.hooks.keys():
                hook_func = getattr(module, hook, None)
                if callable(hook_func):
                    self.hooks[hook].append(hook_func)

        except Exception:
            self.log(f"Erreur chargement extension {name}", "error")
            traceback.print_exc()

    def unload_extension(self, name: str) -> None:
        module = self.extensions.get(name)
        if not module:
            self.log(f"Extension non chargée : {name}", "warning")
            return
        # Supprime tous les hooks liés à cette extension
        for hook, funcs in self.hooks.items():
            self.hooks[hook] = [f for f in funcs if f.__module__ != module.__name__]
        del self.extensions[name]
        self.log(f"Extension déchargée : {name}")

    def reload_extension(self, name: str) -> None:
        self.unload_extension(name)
        self.load_extension(name)

    # --- Appel des hooks ---
    def call_hook(self, hook_name: str, *args, **kwargs) -> None:
        if hook_name not in self.hooks:
            self.log(f"Hook inconnu: {hook_name}", "warning")
            return
        for func in self.hooks[hook_name]:
            try:
                func(self.engine, *args, **kwargs)
            except Exception:
                self.log(f"Erreur dans hook {hook_name} de {func.__module__}", "error")
                traceback.print_exc()

    # --- Liste des extensions dispo ---
    def available_extensions(self) -> List[str]:
        if not os.path.isdir(self.extensions_folder):
            return []
        return [
            f[:-3] for f in os.listdir(self.extensions_folder)
            if f.endswith(".py") and not f.startswith("_")
        ]
