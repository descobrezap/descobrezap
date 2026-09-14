import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Meu Site",
    description="Plataforma de ferramentas práticas online.",
    version="1.0.0",
)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("index.html")


@app.get("/orcamento")
async def read_orcamento():
    return FileResponse("orcamento.html")


@app.get("/api/status")
async def api_status():
    return {
        "status": "online",
        "site": "Meu Site",
        "message": "Sistema funcionando corretamente."
    }


@app.get("/favicon.ico")
async def favicon():
    if os.path.exists("favicon.ico"):
        return FileResponse("favicon.ico")
    return {"message": "Favicon não configurado."}
