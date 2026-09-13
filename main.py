from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from bypassers import run_bypass

app = FastAPI(title="Bypass API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def home():
    return {"status": "ok", "endpoints": ["/bypass?link=<url>"]}

@app.get("/bypass")
async def bypass(link: str):
    result = await run_bypass(link)
    if not result:
        raise HTTPException(404, detail="Bypass failed - shortener not supported")
    return {"original": link, "bypassed": result}
