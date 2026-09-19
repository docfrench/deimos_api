import asyncio
import os
import time

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException

import ifdb
import vampire
import weigh_heart

load_dotenv()

app = FastAPI()

# Anything an upstream can do to us: network errors, bad status, bad JSON, unexpected shape
UPSTREAM_ERRORS = (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError)

CACHE_TTL = 60          # seconds a good response is served without touching upstream
PARTIAL_TTL = 10        # shorter TTL when some library counts failed
FAIL_BACKOFF = 15       # seconds to skip upstream after a failure


# Health check

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(ifdb.router)
app.include_router(vampire.router)
app.include_router(weigh_heart.router)


##
## Jellyfin widget
##
router = APIRouter(prefix="/api/jellyfin", tags=["jellyfin"])
JELLYFIN_URL = os.environ["JELLYFIN_URL"]
JELLYFIN_API_KEY = os.environ["JELLYFIN_API_KEY"]

# maps Jellyfin's CollectionType to which item type we count for that library
COLLECTION_TYPE_TO_ITEM = {
    "movies": "Movie",
    "tvshows": "Series",
    "music": "MusicAlbum",
    "books": "Book",
    "homevideos": "Video",
}

_jf_cache = {"data": None, "expires": 0.0}
_jf_fail_until = 0.0
_jf_lock = asyncio.Lock()


async def _jf_library_count(client: httpx.AsyncClient, headers: dict, folder: dict, item_type: str):
    try:
        resp = await client.get(
            f"{JELLYFIN_URL}/Items",
            headers=headers,
            params={
                "ParentId": folder["ItemId"],
                "Recursive": "true",
                "IncludeItemTypes": item_type,
                "Limit": 1,
                "EnableTotalRecordCount": "true",
            },
        )
        resp.raise_for_status()
        return resp.json().get("TotalRecordCount", 0)
    except UPSTREAM_ERRORS:
        return None


def _jf_stale_or_502():
    if _jf_cache["data"]:
        return _jf_cache["data"]
    raise HTTPException(status_code=502, detail="Jellyfin unreachable")


@router.get("/status")
async def jellyfin_status():
    global _jf_fail_until

    if _jf_cache["data"] and time.monotonic() < _jf_cache["expires"]:
        return _jf_cache["data"]

    # One refresh at a time; concurrent requests wait, then hit the fresh cache
    async with _jf_lock:
        now = time.monotonic()
        if _jf_cache["data"] and now < _jf_cache["expires"]:
            return _jf_cache["data"]
        if now < _jf_fail_until:
            return _jf_stale_or_502()

        headers = {"X-Emby-Token": JELLYFIN_API_KEY}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                folders_resp = await client.get(
                    f"{JELLYFIN_URL}/Library/VirtualFolders", headers=headers
                )
                folders_resp.raise_for_status()
                folders = folders_resp.json()

                # skip mixed/unknown-type libraries
                targets = []
                for folder in folders:
                    item_type = COLLECTION_TYPE_TO_ITEM.get(folder.get("CollectionType", ""))
                    if item_type and folder.get("ItemId"):
                        targets.append((folder, item_type))

                counts = await asyncio.gather(
                    *(_jf_library_count(client, headers, f, t) for f, t in targets)
                )
        except UPSTREAM_ERRORS:
            _jf_fail_until = time.monotonic() + FAIL_BACKOFF
            return _jf_stale_or_502()

        libraries = [
            {"name": f.get("Name"), "type": f.get("CollectionType", ""), "count": c}
            for (f, _), c in zip(targets, counts)
        ]
        data = {"libraries": libraries}
        ttl = CACHE_TTL if all(l["count"] is not None for l in libraries) else PARTIAL_TTL
        _jf_cache.update(data=data, expires=time.monotonic() + ttl)
        return data

app.include_router(router)


##
## BookOrbit widget
##
bookorbit_router = APIRouter(prefix="/api/bookorbit", tags=["bookorbit"])

BOOKORBIT_URL = os.environ["BOOKORBIT_URL"]
BOOKORBIT_USERNAME = os.environ["BOOKORBIT_USERNAME"]
BOOKORBIT_PASSWORD = os.environ["BOOKORBIT_PASSWORD"]

LOGIN_BACKOFF = 60      # seconds to stop retrying login after a failure

_bookorbit_token_cache = {"token": None}
_login_backoff_until = 0.0
_books_cache = {"data": None, "expires": 0.0}
_books_lock = asyncio.Lock()


async def get_bookorbit_token(client: httpx.AsyncClient) -> str:
    global _login_backoff_until

    if _bookorbit_token_cache["token"]:
        return _bookorbit_token_cache["token"]
    if time.monotonic() < _login_backoff_until:
        raise httpx.HTTPError("login in backoff")

    try:
        resp = await client.post(
            f"{BOOKORBIT_URL}/api/v1/auth/login",
            json={"username": BOOKORBIT_USERNAME, "password": BOOKORBIT_PASSWORD},
        )
        resp.raise_for_status()
        token = resp.json()["accessToken"]
    except UPSTREAM_ERRORS:
        _login_backoff_until = time.monotonic() + LOGIN_BACKOFF
        raise

    _bookorbit_token_cache["token"] = token
    return token


@bookorbit_router.get("/books")
async def bookorbit_status():
    if _books_cache["data"] and time.monotonic() < _books_cache["expires"]:
        return _books_cache["data"]

    # One refresh at a time; this also serializes re-login on token expiry
    async with _books_lock:
        if _books_cache["data"] and time.monotonic() < _books_cache["expires"]:
            return _books_cache["data"]

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                token = await get_bookorbit_token(client)
                url = f"{BOOKORBIT_URL}/api/v1/libraries"
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

                # token expired mid-flight: re-authenticate once and retry
                if resp.status_code == 401:
                    _bookorbit_token_cache["token"] = None
                    token = await get_bookorbit_token(client)
                    resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

                resp.raise_for_status()
                data = {
                    "libraries": [
                        {"id": lib["id"], "name": lib["name"], "count": lib["bookCount"]}
                        for lib in resp.json()
                    ]
                }
        except UPSTREAM_ERRORS:
            if _books_cache["data"]:  # serve stale rather than fail
                return _books_cache["data"]
            raise HTTPException(status_code=502, detail="BookOrbit unreachable")

        _books_cache.update(data=data, expires=time.monotonic() + CACHE_TTL)
        return data

app.include_router(bookorbit_router)
