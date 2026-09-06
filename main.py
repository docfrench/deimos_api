from dotenv import load_dotenv
import os
from fastapi import FastAPI, Query, APIRouter, HTTPException
import httpx
from typing import Optional
import sqlite3
import vampire
import weigh_heart
import ifdb

load_dotenv()

app = FastAPI()

#Health check

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


@router.get("/status")
async def jellyfin_status():
    headers = {"X-Emby-Token": JELLYFIN_API_KEY}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            folders_resp = await client.get(f"{JELLYFIN_URL}/Library/VirtualFolders", headers=headers)
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Jellyfin unreachable")

    folders = folders_resp.json()

    libraries = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for folder in folders:
            collection_type = folder.get("CollectionType", "")
            item_type = COLLECTION_TYPE_TO_ITEM.get(collection_type)
            if not item_type or not folder.get("ItemId"):
                continue  # skip mixed/unknown-type libraries

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
                count = resp.json().get("TotalRecordCount", 0)
            except httpx.RequestError:
                count = None

            libraries.append({
                "name": folder.get("Name"),
                "type": collection_type,
                "count": count,
            })

    return {
        "libraries": libraries,
    }
app.include_router(router)

##
## BookOrbit widget
##
bookorbit_router = APIRouter(prefix="/api/bookorbit", tags=["bookorbit"])

BOOKORBIT_URL = os.environ["BOOKORBIT_URL"]
BOOKORBIT_USERNAME = os.environ["BOOKORBIT_USERNAME"]
BOOKORBIT_PASSWORD = os.environ["BOOKORBIT_PASSWORD"]


_bookorbit_token_cache = {"token": None}

async def get_bookorbit_token(client: httpx.AsyncClient) -> str:
    if _bookorbit_token_cache["token"]:
        return _bookorbit_token_cache["token"]

    resp = await client.post(
        f"{BOOKORBIT_URL}/api/v1/auth/login",
        json={"username": BOOKORBIT_USERNAME, "password": BOOKORBIT_PASSWORD},
    )
    resp.raise_for_status()
    token = resp.json()["accessToken"]
    _bookorbit_token_cache["token"] = token
    return token

@bookorbit_router.get("/books")
async def bookorbit_status():
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            token = await get_bookorbit_token(client)
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="BookOrbit unreachable")

        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(f"{BOOKORBIT_URL}/api/v1/libraries", headers=headers)

        # token expired mid-flight — re-authenticate once and retry
        if resp.status_code == 401:
            _bookorbit_token_cache["token"] = None
            token = await get_bookorbit_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get(f"{BOOKORBIT_URL}/api/v1/libraries", headers=headers)

        resp.raise_for_status()
        libraries_raw = resp.json()

    libraries = [
        {"id": lib["id"], "name": lib["name"], "count": lib["bookCount"]}
        for lib in libraries_raw
    ]

    return {"libraries": libraries}

app.include_router(bookorbit_router)
