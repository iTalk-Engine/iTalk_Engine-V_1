import os
import json
import datetime
import jwt
import hashlib
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from Engine.core import ItalkEngine

# --- Chargement des variables d'environnement ---
load_dotenv()
SECRET_KEY = os.environ.get("ITALK_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("ITALK_SECRET_KEY non défini dans .env")

# --- Initialisation ---
app = Flask(__name__)
CORS(app)
engine = ItalkEngine()  # instance du moteur partagé avec app.py

USERS_FILE = "users.json"

# --- Fonctions utilitaires ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if not os.path.isfile(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth_header.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = payload["user"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expiré"}), 401
        except Exception:
            return jsonify({"error": "Token invalide"}), 401
        return f(*args, **kwargs)
    return decorated

# --- Routes utilisateurs ---
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm = data.get("confirm_password", "")
    users = load_users()

    if not username or not email or not password or not confirm:
        return jsonify({"error": "Tous les champs sont obligatoires"}), 400
    if password != confirm:
        return jsonify({"error": "Mots de passe différents"}), 400
    if any(u["username"].lower() == username.lower() for u in users.values()):
        return jsonify({"error": "Nom déjà utilisé"}), 409
    if any(u["email"] == email for u in users.values()):
        return jsonify({"error": "Email déjà utilisé"}), 409

    user_id = str(len(users) + 1)
    users[user_id] = {
        "username": username,
        "email": email,
        "password": hash_password(password)
    }
    save_users(users)
    return jsonify({"status": "Utilisateur créé avec succès", "user_id": user_id})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    users = load_users()

    if not username or not password:
        return jsonify({"error": "Nom et mot de passe requis"}), 400

    user = next((u for u in users.values() if u["username"].lower() == username.lower()), None)
    if not user or user["password"] != hash_password(password):
        return jsonify({"error": "Identifiants invalides"}), 403

    payload = {
        "user": user["username"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return jsonify({"token": token, "username": user["username"], "email": user["email"]})

@app.route("/api/refresh", methods=["POST"])
@require_token
def refresh_token():
    username = request.user
    users = load_users()
    user = next((u for u in users.values() if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404
    payload = {
        "user": user["username"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return jsonify({"token": token})

# --- Routes ItalkEngine ---
@app.route("/api/users", methods=["GET"])
@require_token
def list_users():
    return jsonify([
        {"id": u.id, "username": u.username, "connected": u.connected}
        for u in engine.users.values()
    ])

@app.route("/api/users/connect", methods=["POST"])
@require_token
def connect_user():
    data = request.json or {}
    user = engine.connect_user(data["id"], data["username"])
    return jsonify({"id": user.id, "username": user.username, "connected": user.connected})

@app.route("/api/users/disconnect", methods=["POST"])
@require_token
def disconnect_user():
    data = request.json or {}
    engine.disconnect_user(data["id"])
    return jsonify({"status": "ok"})

@app.route("/api/messages/send", methods=["POST"])
@require_token
def send_message():
    data = request.json or {}
    user_id = data.get("id")
    content = data.get("content")
    if not user_id or not content:
        return jsonify({"error": "id et content requis"}), 400
    msg = engine.send_message(user_id, content)
    if not msg:
        return jsonify({"error": "Utilisateur non connecté"}), 400
    return jsonify({
        "status": "envoyé",
        "message": {
            "user_id": user_id,
            "content": msg.content,
            "timestamp": msg.timestamp
        }
    })

# --- Routes extensions ---
@app.route("/api/extensions", methods=["GET"])
@require_token
def list_extensions():
    available = [f[:-3] for f in os.listdir("extensions") if f.endswith(".py") and not f.startswith("_")]
    loaded = engine.extensions
    return jsonify({"loaded": loaded, "available": available})

@app.route("/api/extensions/activate", methods=["POST"])
@require_token
def activate_extension():
    ext = request.json.get("name")
    if not ext:
        return jsonify({"error": "No extension name"}), 400
    if ext not in engine.config.get("extensions", []):
        engine.config.setdefault("extensions", []).append(ext)
        engine.load_extensions()
        with open(engine.config_path, "w", encoding="utf-8") as f:
            json.dump(engine.config, f, indent=2)
    return jsonify({"status": "ok"})

@app.route("/api/extensions/deactivate", methods=["POST"])
@require_token
def deactivate_extension():
    ext = request.json.get("name")
    if not ext or ext not in engine.config.get("extensions", []):
        return jsonify({"error": "Extension non active"}), 400
    engine.config["extensions"].remove(ext)
    engine.load_extensions()
    with open(engine.config_path, "w", encoding="utf-8") as f:
        json.dump(engine.config, f, indent=2)
    return jsonify({"status": "ok"})

# --- Lancement ---
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
