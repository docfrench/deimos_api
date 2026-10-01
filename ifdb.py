import sqlite3
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/ifdb", tags=["ifdb"])

DB_PATH = "/data/ifdb.sqlite"

@contextmanager
def get_db(ro: bool = False):
    uri = f"file:{DB_PATH}?mode=ro" if ro else f"file:{DB_PATH}"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@router.get("/entries") 
def list_entries(author: str | None = Query(None), system: str | None = Query(None)):
    with get_db(ro=True) as conn:
 
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

        return [dict(r) for r in rows]

@router.get("/authors/{name}")
def get_author(name: str):
    with get_db(ro=True) as conn:
        row = conn.execute(
            "SELECT id, name, bio, photo_url FROM authors WHERE name = ?", (name,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No author named '{name}'")
    return dict(row)
