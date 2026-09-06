from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import sqlite3

router = APIRouter(prefix="/api/vampire", tags=["vampire"])

DB_PATH = "/data/vampire_england_db.sqlite"
 
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn



@router.get("/scoreboard") 
def get_scoreboard(player: Optional[str] = Query(None),):
    db = get_db()
    characters = db.execute("SELECT * FROM characters WHERE active = 1").fetchall()
    result = []
    for c in characters:
        xp_events = db.execute("SELECT * FROM xp_events WHERE character_id = ?", (c["id"],)).fetchall()
        current_xp = sum(e["delta"] for e in xp_events)
        spent_xp = -sum(e["delta"] for e in xp_events if e["delta"] < 0)
        boons = db.execute("SELECT * FROM boons WHERE character_id = ? AND resolved = 0", (c["id"],)).fetchall()
        achievements = db.execute("SELECT text FROM achievements WHERE character_id = ? ORDER BY awarded_at DESC", (c["id"],)).fetchall()
        result.append({
            "character_name": c["character_name"],
            "player_name": c["player_name"],
            "clan": c["clan"],
            "generation": c["generation"],
            "road": c["road"],
            "current_xp": current_xp,
            "spent_xp": spent_xp,
            "boons_owed_to_pc": [dict(b) for b in boons if b["direction"] == "owed_to_pc"],
            "boons_owed_by_pc": [dict(b) for b in boons if b["direction"] == "owed_by_pc"],
            "achievements": [a["text"] for a in achievements],
        })
    db.close()
    return result


@router.get("/players/{name}")
def get_pc(name: str):
    db = get_db()
    characters = db.execute(
        "SELECT * FROM characters WHERE player_name = ?", (name,)
    ).fetchall()

    if not characters:
        db.close()
        raise HTTPException(status_code=404, detail=f"No characters found for player '{name}'")

    result = []
    for c in characters:
        xp_events = db.execute("SELECT * FROM xp_events WHERE character_id = ?", (c["id"],)).fetchall()
        current_xp = sum(e["delta"] for e in xp_events)
        spent_xp = -sum(e["delta"] for e in xp_events if e["delta"] < 0)
        boons = db.execute("SELECT * FROM boons WHERE character_id = ? AND resolved = 0", (c["id"],)).fetchall()
        achievements = db.execute("SELECT text FROM achievements WHERE character_id = ? ORDER BY awarded_at DESC", (c["id"],)).fetchall()
        disciplines = db.execute("SELECT * FROM disciplines WHERE character_id = ? ORDER BY level DESC", (c["id"],)).fetchall()
        contacts = db.execute("SELECT * FROM contacts WHERE character_id = ?", (c["id"],)).fetchall()
        xp_spend_log = [
            {"delta": e["delta"], "reason": e["reason"], "session_date": e["session_date"]}
            for e in xp_events if e["delta"] < 0
        ]
        xp_award_log = [
            {"delta": e["delta"], "reason": e["reason"], "session_date": e["session_date"]}
            for e in xp_events if e["delta"] > 0
        ]
        result.append({
            "character_name": c["character_name"],
            "player_name": c["player_name"],
            "charsheet": c["charsheet"],
            "clan": c["clan"],
            "generation": c["generation"],
            "road": c["road"],
            "current_xp": current_xp,
            "image_path": c["image_path"],
            "spent_xp": spent_xp,
            "boons_owed_to_pc": [dict(b) for b in boons if b["direction"] == "owed_to_pc"],
            "boons_owed_by_pc": [dict(b) for b in boons if b["direction"] == "owed_by_pc"],
            "achievements": [a["text"] for a in achievements],
            "disciplines": [{"name": d["name"], "level": d["level"]} for d in disciplines],
            "contacts": [{"name": ct["name"], "description": ct["description"], "contact_type": ct["contact_type"]} for ct in contacts],
            "xp_spend_log": sorted(xp_spend_log, key=lambda x: x["session_date"] or "", reverse=True),
            "xp_award_log": sorted(xp_award_log, key=lambda x: x["session_date"] or "", reverse=True),
        })
    db.close()
    return result


@router.get("/sessionlog")
def get_session_log():
    db = get_db()
    sessions = db.execute("SELECT * FROM session_log ORDER BY date DESC").fetchall()
    result = [{"date": s["date"], "summary": s["summary"]} for s in sessions]
    db.close()
    return result


@router.get("/denizens")
def get_denizens():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM denizens WHERE met = 1 ORDER BY category, faction, name"
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if not row.get("clan_known"):
            row["clan"] = None
        result.append(row)
    db.close()
    return result

@router.get("/denizens-test")
def get_denizens_test():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM denizens ORDER BY category, faction, name"
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        if not row.get("clan_known"):
            row["clan"] = None
        result.append(row)
    db.close()
    return result


@router.get("/clocks")
def get_clocks():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM clocks WHERE active = 1 ORDER BY name"
    ).fetchall()
    result = [dict(r) for r in rows]
    db.close()
    return result







