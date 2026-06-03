import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from civsim.models.entity import EntityDraft
from civsim.paths import project_root, resolve_data_path
from civsim.registry.capability_registry import CapabilityRegistry
from civsim.registry.material_registry import MaterialRegistry
from civsim.registry.method_registry import MethodRegistry
from civsim.services.game_service import GameService
from civsim.services.visual_service import VisualService

load_dotenv()

DATA_DIR = project_root() / "data"
SAVES_PATH = resolve_data_path("SAVES_PATH", "data/saves")
IMAGES_PATH = resolve_data_path("IMAGES_PATH", "data/images")

registry = CapabilityRegistry.load_for_era("paleolithic", DATA_DIR)
material_registry = MaterialRegistry.load_for_era("paleolithic", DATA_DIR)
method_registry = MethodRegistry.load_for_era("paleolithic", DATA_DIR)
game_service = GameService(
    registry,
    SAVES_PATH,
    material_registry=material_registry,
    method_registry=method_registry,
    data_dir=DATA_DIR,
)
visual_service = VisualService(IMAGES_PATH, game_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="WHAT Simulation API", version="0.2.0", lifespan=lifespan)

origins = os.environ.get("CORS_ORIGINS", "http://127.0.0.1:5000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateGameRequest(BaseModel):
    seed: int = 42
    name: str | None = None


class InterpretRequest(BaseModel):
    game_id: str
    text: str
    region_id: str | None = None


class PlaceEntityRequest(BaseModel):
    type: str
    tags: list[str] = Field(default_factory=list)
    capabilities: dict[str, float] = Field(default_factory=dict)
    region_id: str
    name: str = "Unnamed"


class RenameRegionRequest(BaseModel):
    name: str


class TravelRequest(BaseModel):
    target_region_id: str
    from_region_id: str | None = None


class LabCombineRequest(BaseModel):
    region_id: str
    material_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    method_ids: list[str] = Field(default_factory=list)
    intent: str = ""


@app.get("/")
def root():
    return {
        "service": "WHAT Simulation API",
        "docs": "/docs",
        "health": "/health",
        "ui": "http://127.0.0.1:5000 (Flask — run: poetry run python web/app.py)",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/games")
def list_games():
    return {"games": game_service.list_saves()}


@app.post("/games")
def create_game(req: CreateGameRequest):
    state = game_service.create_game(req.seed, name=req.name)
    game_service.auto_approve_pending()
    return state.model_dump()


@app.delete("/games/{game_id}")
def delete_game(game_id: str):
    if not game_service.delete_game(game_id):
        raise HTTPException(404, "Game not found")
    return {"ok": True}


@app.get("/games/{game_id}/visuals/{subject_type}/{subject_id}")
def get_visual(game_id: str, subject_type: str, subject_id: str):
    if not game_service.load_game(game_id):
        raise HTTPException(404, "Game not found")
    path = visual_service.get_or_create_image(game_id, subject_type, subject_id)
    if not path:
        if not os.environ.get("OPENAI_API_KEY"):
            raise HTTPException(
                503,
                "OPENAI_API_KEY is required for AI graphics. Set it in .env or use Text graphics.",
            )
        raise HTTPException(404, "Visual not found")
    return FileResponse(path, media_type="image/png")


@app.get("/games/{game_id}")
def get_game(game_id: str):
    state = game_service.load_game(game_id)
    if not state:
        raise HTTPException(404, "Game not found")
    return state.model_dump()


@app.get("/games/{game_id}/world/overview")
def world_overview(game_id: str, region_id: str | None = None):
    result = game_service.get_world_overview(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.get("/games/{game_id}/world/materials/absent")
def world_materials_absent(game_id: str, region_id: str | None = None):
    result = game_service.get_world_materials_absent(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.get("/games/{game_id}/world/materials/available")
def world_materials_available(game_id: str, region_id: str | None = None):
    result = game_service.get_world_materials_available(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.get("/games/{game_id}/world/materials/stocks")
def world_materials_stocks(game_id: str, region_id: str | None = None):
    result = game_service.get_world_materials_stocks(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.get("/games/{game_id}/world/components")
def world_components(game_id: str, region_id: str | None = None):
    result = game_service.get_world_components(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.get("/games/{game_id}/world/objects")
def world_objects(game_id: str, region_id: str | None = None):
    result = game_service.get_world_objects(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.get("/games/{game_id}/entities/{entity_id}")
def get_entity(game_id: str, entity_id: str):
    entity = game_service.get_entity(game_id, entity_id)
    if not entity:
        raise HTTPException(404, "Entity not found")
    return entity


@app.post("/games/{game_id}/travel")
def travel_region(game_id: str, req: TravelRequest):
    result = game_service.travel_to_region(
        game_id, req.target_region_id, req.from_region_id
    )
    if not result:
        raise HTTPException(404, "Game or region not found")
    if result.get("error"):
        raise HTTPException(400, result)
    return result


@app.post("/games/{game_id}/regions/{region_id}/name")
def rename_region(game_id: str, region_id: str, req: RenameRegionRequest):
    state = game_service.rename_region(game_id, region_id, req.name)
    if not state:
        raise HTTPException(404, "Game or region not found")
    return {"region_id": region_id, "name": req.name}


@app.post("/ideas/interpret")
def interpret_idea(req: InterpretRequest):
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(
            503,
            "OPENAI_API_KEY is required for idea interpretation. Set it in .env",
        )
    try:
        result = game_service.interpret_idea(req.game_id, req.text, req.region_id)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Idea interpretation failed: {e}") from e
    if not result:
        raise HTTPException(404, "Game not found")
    return result


@app.post("/games/{game_id}/entities")
def place_entity(game_id: str, req: PlaceEntityRequest):
    draft = EntityDraft(
        type=req.type,
        tags=req.tags,
        capabilities=req.capabilities,
        region_id=req.region_id,
        name=req.name,
    )
    entity, constraint, error, method_learned = game_service.place_entity(game_id, draft)
    if error and not entity and not method_learned:
        raise HTTPException(400, {"error": error, "constraint": constraint.model_dump() if constraint else None})
    return {
        "entity": entity.model_dump() if entity else None,
        "constraint": constraint.model_dump() if constraint else None,
        "method_learned": method_learned,
    }


@app.get("/games/{game_id}/lab/options")
def lab_options(game_id: str, region_id: str | None = None):
    options = game_service.get_lab_options(game_id, region_id)
    if not options:
        raise HTTPException(404, "Game or region not found")
    return options


@app.post("/games/{game_id}/lab/combine")
def lab_combine(game_id: str, req: LabCombineRequest):
    result = game_service.combine_in_lab(
        game_id,
        req.region_id,
        req.material_ids,
        component_ids=req.component_ids,
        object_ids=req.object_ids,
        entity_ids=req.entity_ids,
        method_ids=req.method_ids,
        intent=req.intent,
    )
    if not result:
        raise HTTPException(404, "Game or region not found")
    if result.get("error") and not result.get("proposal"):
        raise HTTPException(400, result)
    return result


@app.post("/games/{game_id}/regions/{region_id}/survey")
def survey_region(game_id: str, region_id: str):
    result = game_service.survey_region(game_id, region_id)
    if not result:
        raise HTTPException(404, "Game or region not found")
    return result


@app.post("/games/{game_id}/tick")
def tick_game(game_id: str):
    result = game_service.tick(game_id)
    if not result:
        raise HTTPException(404, "Game not found")
    return result.model_dump()


@app.get("/games/{game_id}/events")
def get_events(game_id: str, limit: int = 20):
    events = game_service.get_events(game_id, limit)
    if events is None:
        raise HTTPException(404, "Game not found")
    return {"events": events}


@app.get("/capabilities")
def list_capabilities(era: str = "paleolithic"):
    return registry.to_public_dict(era=era)


@app.get("/capabilities/pending")
def list_pending():
    return {"pending": [p.model_dump() for p in registry.list_pending()]}


@app.post("/capabilities/pending/{pending_id}/approve")
def approve_capability(pending_id: str):
    if not registry.approve_pending(pending_id):
        raise HTTPException(404, "Pending capability not found")
    return {"approved": pending_id, "registry": registry.to_public_dict()}


@app.get("/games/{game_id}/memory")
def search_memory(game_id: str, q: str = "", limit: int = 10):
    records = game_service.memory.search_similar(q, game_id, limit)
    return {"records": [r.model_dump() for r in records]}
