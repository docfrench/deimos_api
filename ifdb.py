from fastapi import FastAPI, Query
import httpx
from fastapi import APIRouter, HTTPException
from typing import Optional
import sqlite3

router = APIRouter(prefix="/api/ifdb", tags=["ifdb"])

DB_PATH = "/data/ifdb.sqlite"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/entries") 
def list_entries(author: Optional[str] = Query(None), system: Optional[str] = Query(None)):
    conn = get_db()
 
    query = """
        SELECT e.id, e.title, e.year, e.system, e.play_url, e.invisiclues, e.manual,
               GROUP_CONCAT(a.name, ', ') AS authors
        FROM entries e
        LEFT JOIN entry_authors ea ON ea.entry_id = e.id
        LEFT JOIN authors a ON a.id = ea.author_id
    """
 
    conditions = []
    params = []
 
    if system:
        conditions.append("e.system = ?")
        params.append(system)
 
    if author:
        # restrict to entries that have this author linked, without
        # dropping their OTHER co-authors from the GROUP_CONCAT result
        conditions.append("""
            e.id IN (
                SELECT ea2.entry_id FROM entry_authors ea2
                JOIN authors a2 ON a2.id = ea2.author_id
                WHERE a2.name = ?
            )
        """)
        params.append(author)
 
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
 
    query += " GROUP BY e.id"
 
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/authors/{name}")
def get_author(name: str):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, bio, photo_url FROM authors WHERE name = ?", (name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {"error": "not found"}
