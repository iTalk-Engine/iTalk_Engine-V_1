from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from Engine.core import ItalkEngine
from Engine.extensions import ExtensionManager
from dotenv import load_dotenv
import os

# --- Charger les variables d'environnement ---
load_dotenv()  # lit le fichier .env
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret")  # fallback si non défini

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Initialisation du moteur ---
engine = ItalkEngine()

# --- Callbacks du moteur ---
def on_user_connected(user):
    print(f"[Système] {user.username} connecté")
    socketio.emit('user_connected', {'id': user.id, 'username': user.username})

def on_user_disconnected(user):
    print(f"[Système] {user.username} déconnecté")
    socketio.emit('user_disconnected', {'id': user.id})

def on_message(user, message):
    print(f"[{message.timestamp}] {user.username} : {message.content}")
    socketio.emit('new_message', {
        'user_id': user.id,
        'username': user.username,
        'content': message.content,
        'timestamp': message.timestamp
    })

engine.on("on_connect", on_user_connected)
engine.on("on_disconnect", on_user_disconnected)
engine.on("on_message", on_message)

# --- Routes HTTP ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    user_id = data.get("id")
    username = data.get("username")
    if not user_id or not username:
        return jsonify({"error": "id et username requis"}), 400
    try:
        user = engine.register_user(user_id, username)
        return jsonify({"status": "ok", "user": {"id": user.id, "username": user.username}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    user_id = data.get("id")
    username = data.get("username")
    if not user_id or not username:
        return jsonify({"error": "id et username requis"}), 400
    try:
        user = engine.connect_user(user_id, username)
        return jsonify({"status": "connecté", "user": {"id": user.id, "username": user.username}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json or {}
    user_id = data.get("id")
    if not user_id:
        return jsonify({"error": "id requis"}), 400
    try:
        engine.disconnect_user(user_id)
        return jsonify({"status": "déconnecté", "user_id": user_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- SocketIO Events ---
@socketio.on('send_message')
def handle_send_message(data):
    user_id = data.get('id')
    content = data.get('content')
    if not user_id or not content:
        emit('error', {'error': 'id et content requis'})
        return
    try:
        engine.send_message(user_id, content)
    except Exception as e:
        emit('error', {'error': str(e)})

# --- Lancement du serveur ---
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
