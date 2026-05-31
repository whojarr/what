import os

import httpx
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

load_dotenv()

# Local dev: http://127.0.0.1:8000 — Lambda: set by serverless (API Gateway /api prefix)
API_BASE = os.environ.get("FASTAPI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")


def api_client():
    return httpx.Client(base_url=API_BASE, timeout=60.0)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/start", methods=["POST"])
def start_game():
    seed = int(request.form.get("seed", 42))
    with api_client() as client:
        r = client.post("/games", json={"seed": seed})
        r.raise_for_status()
        game = r.json()
    session["game_id"] = game["id"]
    return redirect(url_for("world"))


@app.route("/world")
def world():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))
    with api_client() as client:
        r = client.get(f"/games/{game_id}")
        r.raise_for_status()
        game = r.json()
    return render_template("world.html", game=game)


@app.route("/world/rename", methods=["POST"])
def rename_region():
    game_id = session.get("game_id")
    region_id = request.form.get("region_id")
    name = request.form.get("name")
    if game_id and region_id and name:
        with api_client() as client:
            client.post(
                f"/games/{game_id}/regions/{region_id}/name",
                json={"name": name},
            )
    return redirect(url_for("world"))


@app.route("/invent", methods=["GET", "POST"])
def invent():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))

    result = None
    error = None
    if request.method == "POST":
        text = request.form.get("idea", "")
        region_id = request.form.get("region_id")
        session["last_region_id"] = region_id
        try:
            with api_client() as client:
                r = client.post(
                    "/ideas/interpret",
                    json={
                        "game_id": game_id,
                        "text": text,
                        "region_id": region_id,
                    },
                )
                if r.status_code in (503, 500):
                    body = r.json()
                    detail = body.get("detail", r.text)
                    if isinstance(detail, list):
                        detail = detail[0].get("msg", str(detail)) if detail else r.text
                    error = detail
                else:
                    r.raise_for_status()
                    result = r.json()
        except httpx.HTTPError as e:
            error = str(e)

    with api_client() as client:
        game_r = client.get(f"/games/{game_id}")
        game_r.raise_for_status()
        game = game_r.json()

    return render_template(
        "invent.html",
        game=game,
        result=result,
        error=error,
        last_region_id=session.get("last_region_id"),
    )


@app.route("/lab", methods=["GET", "POST"])
def lab():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))

    result = None
    error = None
    intent = ""
    selected_materials: list[str] = []
    selected_components: list[str] = []
    selected_objects: list[str] = []
    selected_methods: list[str] = []

    with api_client() as client:
        game_r = client.get(f"/games/{game_id}")
        game_r.raise_for_status()
        game = game_r.json()
        region_id = session.get("last_region_id") or game["regions"][0]["id"]
        opt_r = client.get(f"/games/{game_id}/lab/options", params={"region_id": region_id})
        opt_r.raise_for_status()
        options = opt_r.json()

    if request.method == "POST":
        region_id = request.form.get("region_id", options["region_id"])
        selected_materials = request.form.getlist("material_ids")
        selected_components = request.form.getlist("component_ids")
        selected_objects = request.form.getlist("object_ids")
        selected_methods = request.form.getlist("method_ids")
        intent = request.form.get("intent", "")
        session["last_region_id"] = region_id
        try:
            with api_client() as client:
                r = client.post(
                    f"/games/{game_id}/lab/combine",
                    json={
                        "region_id": region_id,
                        "material_ids": selected_materials,
                        "component_ids": selected_components,
                        "object_ids": selected_objects,
                        "method_ids": selected_methods,
                        "intent": intent,
                    },
                )
                if r.status_code == 400:
                    body = r.json()
                    detail = body.get("detail", body)
                    if isinstance(detail, dict):
                        error = detail.get("error") or detail.get("errors", ["Combination failed"])[0]
                    else:
                        error = str(detail)
                else:
                    r.raise_for_status()
                    result = r.json()
        except httpx.HTTPError as e:
            error = str(e)

    return render_template(
        "lab.html",
        options=options,
        result=result,
        error=error,
        intent=intent,
        selected_materials=selected_materials,
        selected_components=selected_components,
        selected_objects=selected_objects,
        selected_methods=selected_methods,
    )


@app.route("/place", methods=["POST"])
def place():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))

    payload = {
        "type": request.form.get("type"),
        "tags": request.form.getlist("tags") or request.form.get("tags", "").split(","),
        "capabilities": {},
        "region_id": request.form.get("region_id"),
        "name": request.form.get("invention_name") or request.form.get("name", "Unnamed"),
    }
    if isinstance(payload["tags"], str):
        payload["tags"] = [t.strip() for t in payload["tags"].split(",") if t.strip()]

    import json

    caps_json = request.form.get("capabilities_json", "{}")
    try:
        payload["capabilities"] = json.loads(caps_json)
    except json.JSONDecodeError:
        pass

    with api_client() as client:
        r = client.post(f"/games/{game_id}/entities", json=payload)
        if r.status_code == 400:
            return render_template(
                "place_result.html",
                success=False,
                detail=r.json(),
            )
        r.raise_for_status()
        data = r.json()
    return render_template("place_result.html", success=True, detail=data)


@app.route("/survey", methods=["POST"])
def survey():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))
    region_id = request.form.get("region_id")
    with api_client() as client:
        r = client.post(f"/games/{game_id}/regions/{region_id}/survey")
        r.raise_for_status()
        result = r.json()
    return render_template("survey_result.html", result=result)


@app.route("/tick", methods=["POST"])
def tick():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))
    with api_client() as client:
        r = client.post(f"/games/{game_id}/tick")
        r.raise_for_status()
        result = r.json()
    return render_template("tick_result.html", result=result)


@app.route("/history")
def history():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("home"))
    q = request.args.get("q", "")
    with api_client() as client:
        mem_r = client.get(f"/games/{game_id}/memory", params={"q": q, "limit": 20})
        mem_r.raise_for_status()
        events_r = client.get(f"/games/{game_id}/events")
        events_r.raise_for_status()
    return render_template(
        "history.html",
        records=mem_r.json().get("records", []),
        events=events_r.json().get("events", []),
        query=q,
    )


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5000))
    app.run(host=host, port=port, debug=True)
