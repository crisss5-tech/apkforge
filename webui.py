import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from config import (WEB_HOST, WEB_PORT, CACHE_DIR, PATCHES_DIR,
                    BOT_NAME, BOT_VERSION, BOT_OWNER, TEMPLATES_DIR)
from core import admin_stats, metrics_all

app = FastAPI(title=f"{BOT_NAME} Dashboard")
tmpl = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return tmpl.TemplateResponse("index.html", {
        "request": request,
        "bot_name": BOT_NAME,
        "bot_version": BOT_VERSION,
        "bot_owner": BOT_OWNER,
    })

@app.get("/api/stats")
async def stats():
    return {**admin_stats(), **metrics_all()}

@app.get("/api/cache")
async def cache():
    out = []
    for f in os.listdir(CACHE_DIR):
        fp = os.path.join(CACHE_DIR, f)
        if os.path.isfile(fp):
            out.append({"name": f, "size": os.path.getsize(fp)})
    return out

@app.post("/api/cache/clear")
async def cache_clear():
    n = 0
    for f in os.listdir(CACHE_DIR):
        try:
            os.remove(os.path.join(CACHE_DIR, f)); n += 1
        except OSError:
            pass
    return {"cleared": n}

@app.get("/api/templates")
async def templates():
    return sorted(f[:-5] for f in os.listdir(PATCHES_DIR)
                  if f.endswith(".json") and not f.startswith("."))

def run():
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT, log_level="warning")

if __name__ == "__main__":
    run()