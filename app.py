from Engine.core import ItalkEngine
from Engine.extensions import ExtensionManager


# --- Callbacks principaux ---
def on_user_connected(user):
    """Appelé quand un utilisateur se connecte."""
    print(f"[Système] {user.username} vient de se connecter !")


def on_user_disconnected(user):
    """Appelé quand un utilisateur se déconnecte."""
    print(f"[Système] {user.username} s'est déconnecté.")


def on_message(user, message):
    """Appelé lorsqu'un message est reçu."""
    print(f"[{message.timestamp}] {user.username} : {message.content}")


# --- Fonction d'initialisation du moteur ---
def init_engine():
    """
    Initialise le moteur iTalk Engine et abonne les callbacks aux événements.
    Retourne l'instance du moteur prête à l'emploi.
    """
    engine = ItalkEngine()

    # --- Gestion des extensions (optionnel) ---
    # extension_manager = ExtensionManager(engine)
    # extension_manager.load_extensions()

    # --- Abonnement aux événements ---
    event_callbacks = {
        "on_connect": on_user_connected,
        "on_disconnect": on_user_disconnected,
        "on_message": on_message
    }
    for event, callback in event_callbacks.items():
        engine.on(event, callback)

    return engine


# --- Simulation d'une session utilisateur ---
def simulate_session(engine):
    try:
        user = engine.connect_user("1", "Jallow")
        engine.send_message("1", "Salut tout le monde !")
        engine.disconnect_user("1")

        # Sauvegarde automatique si nécessaire
        # engine.save_state()

    except Exception as exc:
        print(f"[ERREUR] Exception non gérée : {exc}")


# --- Point d'entrée ---
if __name__ == "__main__":
    engine = init_engine()
    simulate_session(engine)
