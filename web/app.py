import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

load_dotenv()

API_BASE = os.environ.get("FASTAPI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

PREVIEW_LIMIT = 8


def _game_id_or_redirect():
    game_id = session.get("game_id")
    if not game_id:
        return None, redirect(url_for("home"))
    return game_id, None


@app.route("/")
def home():
    return render_template("home.html", api_base=API_BASE)


@app.route("/session", methods=["POST"])
def set_session():
    data = request.get_json(silent=True) or {}
    game_id = data.get("game_id")
    if not game_id:
        return {"error": "game_id required"}, 400
    session["game_id"] = game_id
    return {"ok": True}


@app.route("/start", methods=["POST"])
def start_game():
    """Legacy form POST — prefer home.js + /session."""
    import httpx

    seed = int(request.form.get("seed", 42))
    with httpx.Client(base_url=API_BASE, timeout=60.0) as client:
        r = client.post("/games", json={"seed": seed})
        r.raise_for_status()
        game = r.json()
    session["game_id"] = game["id"]
    return redirect(url_for("world"))


@app.route("/world")
def world():
    game_id, redirect_resp = _game_id_or_redirect()
    if redirect_resp:
        return redirect_resp
    return render_template(
        "world.html",
        game_id=game_id,
        api_base=API_BASE,
        preview_limit=PREVIEW_LIMIT,
    )


@app.route("/invent")
def invent():
    game_id, redirect_resp = _game_id_or_redirect()
    if redirect_resp:
        return redirect_resp
    return render_template(
        "invent.html",
        game_id=game_id,
        api_base=API_BASE,
        region_id=session.get("last_region_id"),
    )


@app.route("/lab")
def lab():
    game_id, redirect_resp = _game_id_or_redirect()
    if redirect_resp:
        return redirect_resp
    return render_template(
        "lab.html",
        game_id=game_id,
        api_base=API_BASE,
        region_id=session.get("last_region_id"),
    )


@app.route("/history")
def history():
    game_id, redirect_resp = _game_id_or_redirect()
    if redirect_resp:
        return redirect_resp
    return render_template(
        "history.html",
        game_id=game_id,
        api_base=API_BASE,
    )


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host=host, port=port, debug=True)
