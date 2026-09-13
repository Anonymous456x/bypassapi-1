from fastapi import FastAPI, HTTPException
import aiohttp

app = FastAPI()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

# ---------- Layer 1: simple redirect expand ----------
async def expand_redirect(url: str) -> str:
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        async with s.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=20)) as r:
            final = str(r.url)
            # agar final url bhi wahi shortener domain hai to bypass nahi hua
            return final

# ---------- Layer 2: CrowdBypass (FastForward) ----------
async def crowd_bypass(url: str) -> str:
    # FastForward crowd server pe destination contribute/lookup
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        async with s.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=25)) as r:
            html = await r.text()
        # crowdbypass target nikalo
        import re
        m = re.search(r'crowd-?bypass["\']?\s*[:=]\s*["\']([^"\']+)', html, re.I)
        if not m:
            return ""
        target = m.group(1)
        async with s.post("https://crowdresolve.fastforward.team/gtargets",
                          data={"target": target}) as resp:
            return (await resp.json()).get("dest", "")

# ---------- Layer 3: adbypass.org ----------
async def adbypass(url: str) -> str:
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        async with s.get("https://adbypass.org/bypass",
                         params={"bypass": url},
                         timeout=aiohttp.ClientTimeout(total=30)) as r:
            import re
            html = await r.text()
            m = re.search(r'href=["\'](https?://[^"\']+)["\'].*?class=["\']goto', html, re.I | re.S)
            return m.group(1) if m else ""

# ---------- Pipeline ----------
async def run_bypass(link: str) -> str:
    link = link.strip()
    # Layer 1
    try:
        final = await expand_redirect(link)
        if final != link and "shortener" not in final:  # simple check
            return final
    except Exception:
        pass
    # Layer 2
    try:
        result = await crowd_bypass(link)
        if result:
            return result
    except Exception:
        pass
    # Layer 3
    try:
        result = await adbypass(link)
        if result:
            return result
    except Exception:
        pass
    raise HTTPException(404, detail="Bypass failed for this link")

@app.get("/bypass")
async def bypass(link: str):
    return {"original": link, "bypassed": await run_bypass(link)}
