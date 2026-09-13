import aiohttp
import asyncio
import re
import json
import base64
from urllib.parse import urlparse, parse_qs

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = aiohttp.ClientTimeout(total=30)


# ============ LAYER 1: SIMPLE REDIRECT EXPAND ============
async def expand_redirect(url: str) -> str:
    """bit.ly, tinyurl, goo.gl, t.co, is.gd, rebrand.ly, t.ly, tiny.cc etc."""
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        async with s.get(url, allow_redirects=True) as r:
            final = str(r.url)
            # agar final domain shortener khud hai to fail maano
            short_domains = ["bit.ly", "tinyurl", "goo.gl", "t.co", "is.gd",
                             "rebrand.ly", "t.ly", "tiny.cc", "cl.gy", "shorter.me",
                             "rkns.link", "tinylink.onl", "v.gd"]
            if any(d in final for d in short_domains):
                return ""
            return final if final.rstrip("/") != url.rstrip("/") else ""


# ============ LAYER 2: ADBYPASS.ORG ============
async def adbypass(url: str) -> str:
    """Bypass All Shortlinks database - 500+ shorteners"""
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        async with s.get("https://adbypass.org/bypass", params={"bypass": url}) as r:
            html = await r.text()
            # final link page se nikalo
            m = re.search(r'(?:href|data-href|url)\s*=\s*["\'](https?://[^"\']{10,})["\']', html)
            if m and not any(d in m.group(1) for d in ["adbypass.org", "google.com"]):
                return m.group(1)
            # json response ho sakta hai
            try:
                data = json.loads(html)
                return data.get("destination", data.get("result", ""))
            except Exception:
                return ""


# ============ LAYER 3: CROWDBYPASS (FastForward) ============
async def crowd_bypass(url: str) -> str:
    """FastForward crowd database lookup"""
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        # pehle page lo, crowd target nikalo
        try:
            async with s.get(url, allow_redirects=True) as r:
                html = await r.text()
        except Exception:
            html = ""
        m = re.search(r'crowd-?bypass["\']?\s*[:=]\s*["\']([^"\']+)', html, re.I)
        target = m.group(1) if m else url
        # crowd server se lookup
        async with s.post("https://crowdresolve.fastforward.team/gtargets",
                          data={"target": target}) as r:
            try:
                data = await r.json()
                return data.get("dest", "")
            except Exception:
                return ""


# ============ LAYER 4: GPLINKS ============
async def gplinks(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        async with s.get(url) as r:
            html = await r.text()
        m = re.search(r'appid["\']?\s*[:=]\s*["\']([^"\']+)', html)
        appid = m.group(1) if m else parsed.netloc.split(".")[0]
        async with s.get(f"{base}/token.php?appid={appid}") as t:
            token = json.loads(await t.text()).get("token", "")
        body = base64.b64encode(f"{token}~{url}".encode()).decode()
        async with s.post(f"{base}/links", data={"token": token, "body": body}) as l:
            resp = json.loads(await l.text())
            return resp.get("link", "")


# ============ LAYER 5: LINKVERTISE ============
async def linkvertise(url: str) -> str:
    """Linkvertise dynamic link bypass"""
    url = url.replace("linkvertise.com/", "linkvertise.com/api/dynamic-link/")
    if "?" not in url:
        url += "?redirect=true"
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        async with s.get(url) as r:
            try:
                data = await r.json()
                return data.get("data", {}).get("redirect", {}).get("target", "")
            except Exception:
                return ""


# ============ LAYER 6: LOOTLINKS / ADMAVEN ============
async def lootlinks(url: str) -> str:
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        async with s.get(url) as r:
            html = await r.text()
        # session id aur task id nikalo
        sid = re.search(r'session["\']?\s*[:=]\s*["\']([^"\']+)', html)
        if not sid:
            return ""
        async with s.post("https://loot-link.com/api/session/start",
                          json={"session": sid.group(1)}) as r2:
            data = await r2.json()
            return data.get("destination", "")


# ============ LAYER 7: OUO.IO ============
async def ouo(url: str) -> str:
    parsed = urlparse(url)
    code = parsed.path.strip("/")
    if not code:
        return ""
    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
        async with s.post(f"https://ouo.press/api/v1/resolve",
                          json={"link": url}) as r:
            try:
                data = await r.json()
                return data.get("destination", "")
            except Exception:
                return ""


# ============ PIPELINE ============
SHORTENER_HOSTS = {
    "gplinks": ["gplinks", "gplink"],
    "linkvertise": ["linkvertise", "mboost.me", "bst.gg", "booo.st"],
    "lootlinks": ["loot-link", "lootlinks", "lootlabs", "lootdest"],
    "ouo": ["ouo.io", "ouo.press"],
}

async def run_bypass(link: str) -> str:
    link = link.strip()
    if not link.startswith("http"):
        link = "https://" + link
    host = urlparse(link).netloc.lower()

    # --- Site-specific pehle try karo ---
    if any(d in host for d in SHORTENER_HOSTS["gplinks"]):
        try:
            r = await gplinks(link)
            if r: return r
        except Exception: pass

    if any(d in host for d in SHORTENER_HOSTS["linkvertise"]):
        try:
            r = await linkvertise(link)
            if r: return r
        except Exception: pass

    if any(d in host for d in SHORTENER_HOSTS["lootlinks"]):
        try:
            r = await lootlinks(link)
            if r: return r
        except Exception: pass

    if any(d in host for d in SHORTENER_HOSTS["ouo"]):
        try:
            r = await ouo(link)
            if r: return r
        except Exception: pass

    # --- Generic layers ---
    # Layer 1: simple expand
    try:
        r = await expand_redirect(link)
        if r: return r
    except Exception: pass

    # Layer 2: adbypass.org (sabse wide free coverage)
    try:
        r = await adbypass(link)
        if r: return r
    except Exception: pass

    # Layer 3: crowd bypass
    try:
        r = await crowd_bypass(link)
        if r: return r
    except Exception: pass

    return ""
