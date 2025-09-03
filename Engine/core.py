import os
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

class User:
    """Représente un utilisateur dans le moteur Italk."""
    def __init__(self, user_id: str, username: str, metadata: Optional[dict] = None):
        self.id: str = user_id
        self.username: str = username
        self.metadata: dict = metadata or {}
        self.connected: bool = False

class Message:
    """Message envoyé par un utilisateur."""
    def __init__(self, user: 'User', content: str, timestamp: Optional[str] = None):
        self.user: User = user
        self.content: str = content
        self.timestamp: str = timestamp or datetime.utcnow().isoformat()

class Group:
    """Groupe d'utilisateurs."""
    def __init__(self, name: str):
        self.name: str = name
        self.members: Dict[str, User] = {}

    def add_member(self, user: User) -> None:
        self.members[user.id] = user

    def remove_member(self, user_id: str) -> None:
        self.members.pop(user_id, None)

class ItalkEngine:
    """Moteur principal de gestion des utilisateurs, groupes, messages, extensions et événements."""
    def __init__(self, config_path: str = "extensions/config.json", state_path: str = "engine_state.json"):
        self.users: Dict[str, User] = {}
        self.groups: Dict[str, Group] = {}
        self.extensions: List[str] = []
        self.listeners: Dict[str, List[Callable]] = {
            "on_connect": [],
            "on_disconnect": [],
            "on_message": [],
            "on_error": [],
        }
        self.config_path: str = config_path
        self.state_path: str = state_path
        self.load_config(self.config_path)
        self.setup_logging()
        self.load_extensions()
        self.load_state(self.state_path)

    def load_config(self, path: str) -> None:
        if os.path.exists(path):
            with open(path) as f:
                self.config = json.load(f)
        else:
            self.config = {}
        self.logging_enabled = self.config.get("logging", True)

    def setup_logging(self) -> None:
        self.logger = logging.getLogger("ItalkEngine")
        self.logger.setLevel(logging.DEBUG)
        if self.logging_enabled and not self.logger.hasHandlers():
            handler = logging.FileHandler("engine.log", encoding="utf-8")
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log(self, level: str, msg: str) -> None:
        if self.logging_enabled:
            log_func = getattr(self.logger, level.lower(), self.logger.info)
            log_func(msg)

    # --- Gestion des événements ---
    def on(self, event_name: str, callback: Callable) -> None:
        if event_name in self.listeners:
            self.listeners[event_name].append(callback)
        else:
            self.log("warning", f"Tentative d'ajouter un événement inconnu : {event_name}")

    def emit(self, event_name: str, *args, **kwargs) -> None:
        for callback in self.listeners.get(event_name, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.log("error", f"Erreur dans l'événement {event_name} : {e}")

    # --- Utilisateurs ---
    def register_user(self, user_id: str, username: str, metadata: Optional[dict] = None) -> User:
        """Crée un nouvel utilisateur."""
        if user_id in self.users:
            raise ValueError(f"Utilisateur {user_id} déjà enregistré")
        user = User(user_id, username, metadata)
        self.users[user_id] = user
        self.save_state(self.state_path)
        self.log("info", f"Utilisateur enregistré : {username}")
        return user

    def connect_user(self, user_id: str, username: str, metadata: Optional[dict] = None) -> User:
        """Connecte un utilisateur existant ou nouveau."""
        user = self.users.get(user_id)
        if not user:
            user = User(user_id, username, metadata)
            self.users[user_id] = user
        user.connected = True
        self.emit("on_connect", user)
        self.log("info", f"{username} connecté.")
        self.save_state(self.state_path)
        return user

    def disconnect_user(self, user_id: str) -> None:
        user = self.users.get(user_id)
        if user:
            user.connected = False
            self.emit("on_disconnect", user)
            self.log("info", f"{user.username} déconnecté.")
            self.save_state(self.state_path)

    def send_message(self, user_id: str, content: str) -> Optional[Message]:
        user = self.users.get(user_id)
        if not user or not user.connected:
            self.log("warning", f"Utilisateur non connecté : {user_id}")
            return None
        msg = Message(user, content)
        self.emit("on_message", user, msg)
        self.log("info", f"Message de {user.username} : {content}")
        self.save_state(self.state_path)
        return msg

    # --- Extensions ---
    def load_extensions(self) -> None:
        path = "extensions"
        extensions_to_load = self.config.get("extensions", [])
        if not os.path.exists(path):
            os.mkdir(path)
        for name in extensions_to_load:
            file = f"{name}.py"
            full_path = os.path.join(path, file)
            if os.path.isfile(full_path):
                try:
                    mod = __import__(f"extensions.{name}", fromlist=[name])
                    if hasattr(mod, "setup"):
                        mod.setup(self)
                        self.extensions.append(name)
                        self.log("info", f"Extension chargée : {name}")
                except Exception as e:
                    self.log("error", f"Erreur lors du chargement de l’extension {name} : {e}")
            else:
                self.log("warning", f"Extension {name} non trouvée dans {path}")

    # --- Persistance ---
    def save_state(self, filepath: Optional[str] = None) -> None:
        path = filepath or self.state_path
        try:
            data = {
                "users": [
                    {"id": u.id, "username": u.username, "metadata": u.metadata, "connected": u.connected}
                    for u in self.users.values()
                ],
                "groups": [
                    {"name": g.name, "members": list(g.members.keys())}
                    for g in self.groups.values()
                ]
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log("error", f"Erreur lors de la sauvegarde de l’état : {e}")

    def load_state(self, filepath: Optional[str] = None) -> None:
        path = filepath or self.state_path
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.users = {}
            for u in data.get("users", []):
                user = User(u["id"], u["username"], u.get("metadata", {}))
                user.connected = u.get("connected", False)
                self.users[user.id] = user
            self.groups = {}
            for g in data.get("groups", []):
                group = Group(g["name"])
                for user_id in g["members"]:
                    if user_id in self.users:
                        group.add_member(self.users[user_id])
                self.groups[group.name] = group
        except Exception as e:
            self.log("error", f"Erreur lors du chargement de l’état : {e}")
