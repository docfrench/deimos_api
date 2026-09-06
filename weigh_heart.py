import uuid
from fastapi import APIRouter, Request, Response, Query
from typing import Optional
from pydantic import BaseModel
import sqlite3

router = APIRouter(prefix="/api/weighheart", tags=["weighheart"])
 
DB_PATH = "/data/aiquiz_db.sqlite"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class GuessPayload(BaseModel):
    story_id: int
    guessed_ai: bool

class NamePayload(BaseModel):
    display_name: str


@router.get("/story/random")
def get_random_story(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie("session_id", session_id, max_age=60*60*24*365, httponly=True)

    db = get_db()
    try:
        story = db.execute(
            """
            SELECT id, title, author, story_path
            FROM stories
            WHERE id NOT IN (
                SELECT story_id FROM guesses WHERE session_id = ?
            )
            ORDER BY RANDOM() LIMIT 1
            """,
            (session_id,)
        ).fetchone()

        if story is None:
            return {"done": True, "message": "You've seen every story! Reset to play again."}

        return {
            "id": story["id"],
            "title": story["title"],
            "author": story["author"],
            "story_path": story["story_path"],
        }
    finally:
        db.close()




@router.post("/guess")
def submit_guess(payload: GuessPayload, request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        # shouldn't normally happen if they hit /story/random first,
        # but guard against a stray direct POST
        return {"error": "no session found"}

    db = get_db()
    try:
        story = db.execute(
            "SELECT ai_flag FROM stories WHERE id = ?", (payload.story_id,)
        ).fetchone()

        if story is None:
            return {"error": "story not found"}

        actual_ai = bool(story["ai_flag"])
        correct = (payload.guessed_ai == actual_ai)

        db.execute(
            """
            INSERT INTO guesses (story_id, guessed_ai, correct, session_id)
            VALUES (?, ?, ?, ?)
            """,
            (payload.story_id, payload.guessed_ai, correct, session_id)
        )
        db.commit()

        return {"correct": correct, "actual_ai": actual_ai}
    finally:
        db.close()




@router.get("/stats")
def get_stats():
    db = get_db()
    try:
        overall = db.execute(
            "SELECT COUNT(*) as total, SUM(correct) as correct FROM guesses"
        ).fetchone()
        total = overall["total"] or 0
        correct = overall["correct"] or 0

        by_type = db.execute(
            """
            SELECT s.ai_flag, COUNT(*) as total, SUM(g.correct) as correct
            FROM guesses g JOIN stories s ON s.id = g.story_id
            GROUP BY s.ai_flag
            """
        ).fetchall()
        type_breakdown = {}
        for row in by_type:
            key = "ai" if row["ai_flag"] else "human"
            t, c = row["total"], row["correct"] or 0
            type_breakdown[key] = {"total": t, "correct": c, "accuracy": round(c / t * 100, 1) if t else None}

        per_story = db.execute(
            """
            SELECT s.id, s.title, s.author, s.ai_flag,
                   COUNT(g.id) as total_guesses, SUM(g.correct) as correct_guesses
            FROM stories s LEFT JOIN guesses g ON g.story_id = s.id
            GROUP BY s.id ORDER BY s.id
            """
        ).fetchall()
        stories_out = []
        for row in per_story:
            t, c = row["total_guesses"] or 0, row["correct_guesses"] or 0
            stories_out.append({
                "id": row["id"], "title": row["title"], "author": row["author"],
                "actual_ai": bool(row["ai_flag"]), "total_guesses": t,
                "fooled_rate": round(100 - (c / t * 100), 1) if t else None,
            })

        return {
            "total_guesses": total,
            "overall_accuracy": round(correct / total * 100, 1) if total else None,
            "by_type": type_breakdown,
            "stories": stories_out,
        }
    finally:
        db.close()


@router.get("/player/me")
def get_me(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return {"display_name": None, "guesses": 0, "correct": 0, "accuracy": None}

    db = get_db()
    try:
        player = db.execute(
            "SELECT display_name FROM players WHERE session_id = ?", (session_id,)
        ).fetchone()
        row = db.execute(
            "SELECT COUNT(*) as total, SUM(correct) as correct FROM guesses WHERE session_id = ?",
            (session_id,)
        ).fetchone()

        total = row["total"] or 0
        correct = row["correct"] or 0
        return {
            "display_name": player["display_name"] if player else None,
            "guesses": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1) if total else None,
        }
    finally:
        db.close()



@router.post("/player/name")
def set_display_name(payload: NamePayload, request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie("session_id", session_id, max_age=60*60*24*365, httponly=True)

    name = payload.display_name.strip()[:24]
    if not name:
        return {"error": "name cannot be empty"}

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO players (session_id, display_name) VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET display_name = excluded.display_name
            """,
            (session_id, name)
        )
        db.commit()
        return {"display_name": name}
    finally:
        db.close()


@router.get("/stats/leaderboard")
def get_leaderboard(min_guesses: int = 3):
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT p.display_name, COUNT(g.id) as total, SUM(g.correct) as correct
            FROM players p JOIN guesses g ON g.session_id = p.session_id
            GROUP BY p.session_id
            HAVING total >= ?
            ORDER BY (CAST(correct AS FLOAT) / total) DESC
            """,
            (min_guesses,)
        ).fetchall()
        return [
            {"display_name": r["display_name"], "guesses": r["total"],
             "correct": r["correct"], "accuracy": round(r["correct"] / r["total"] * 100, 1)}
            for r in rows
        ]
    finally:
        db.close()

