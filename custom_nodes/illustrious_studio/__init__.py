"""Optional Studio UI. Exported workflows themselves only use native ComfyUI nodes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aiohttp import web
import folder_paths
from server import PromptServer
from illustrious.workflow import build_workflow, catalog

routes = PromptServer.instance.routes
STATIC = ROOT / "web"


@routes.get("/illustrious")
async def redirect(request):
    raise web.HTTPFound("/illustrious/")


@routes.get("/illustrious/")
async def index(request):
    return web.FileResponse(STATIC / "index.html")


@routes.get("/illustrious/assets/{name}")
async def asset(request):
    name = request.match_info["name"]
    if name not in ("studio.js", "studio.css"):
        raise web.HTTPNotFound()
    return web.FileResponse(STATIC / name)


@routes.get("/illustrious/catalog")
async def get_catalog(request):
    data = catalog()
    available = set(folder_paths.get_filename_list("loras"))
    checkpoints = set(folder_paths.get_filename_list("checkpoints"))
    data["checkpoint"]["available"] = data["checkpoint"]["filename"] in checkpoints
    for character in data["characters"]:
        character["available"] = character["filename"] in available
    return web.json_response(data)


@routes.post("/illustrious/workflow")
async def workflow(request):
    if request.content_length and request.content_length > 100_000:
        raise web.HTTPRequestEntityTooLarge(max_size=100_000, actual_size=request.content_length)
    try:
        scene = await request.json()
        return web.json_response(build_workflow(scene))
    except (ValueError, TypeError, KeyError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


NODE_CLASS_MAPPINGS = {}
