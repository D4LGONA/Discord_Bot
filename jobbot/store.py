"""이미 올린 공고를 기억해서 매일 새 공고만 걸러내는 SQLite 저장소."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Posting

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    category    TEXT NOT NULL,
    title       TEXT,
    company     TEXT,
    url         TEXT,
    career_raw  TEXT,
    career_min  INTEGER,
    level       TEXT,
    location    TEXT,
    employment  TEXT,
    deadline    TEXT,
    first_seen  TEXT NOT NULL,
    posted      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source, external_id, category)
);
CREATE INDEX IF NOT EXISTS idx_first_seen ON postings(first_seen);
CREATE INDEX IF NOT EXISTS idx_cat_level  ON postings(category, level);
"""


class Store:
    def __init__(self, path: str | Path = "data/jobs.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @property
    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 0

    def total(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]

    def filter_new(self, postings: list[Posting]) -> list[Posting]:
        """DB에 없는 공고만 돌려준다. 저장은 하지 않는다."""
        known = {
            (r["source"], r["external_id"], r["category"])
            for r in self.conn.execute("SELECT source, external_id, category FROM postings")
        }
        seen: set[tuple[str, str, str]] = set()
        fresh = []
        for p in postings:
            if p.key in known or p.key in seen:
                continue
            seen.add(p.key)
            fresh.append(p)
        return fresh

    def save(self, postings: list[Posting], posted: bool) -> int:
        """공고를 적재한다. posted=False 면 '조용히 적재'(첫 실행 시드)."""
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                p.source, p.external_id, p.category, p.title, p.company, p.url,
                p.career_raw, p.career_min, p.level, p.location, p.employment,
                p.deadline, now, int(posted),
            )
            for p in postings
        ]
        cur = self.conn.executemany(
            "INSERT OR IGNORE INTO postings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
        )
        self.conn.commit()
        return cur.rowcount

    def recent(self, category: str | None = None, level: str | None = None, limit: int = 20):
        sql = "SELECT * FROM postings WHERE 1=1"
        args: list = []
        if category:
            sql += " AND category = ?"
            args.append(category)
        if level:
            sql += " AND level = ?"
            args.append(level)
        sql += " ORDER BY first_seen DESC, rowid DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.conn.execute(sql, args)]

    def stats(self) -> list[dict]:
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT category, level, COUNT(*) AS n FROM postings "
                "GROUP BY category, level ORDER BY category, level"
            )
        ]


class SeenFile:
    """GitHub Actions 처럼 실행이 끝나면 사라지는 환경에서 쓰는 저장소.

    SQLite 파일을 매일 커밋하면 저장소가 무겁게 불어난다. 여기서는
    '이미 올린 공고 키'만 한 줄씩 텍스트로 들고 있어서 git diff 가 깔끔하고
    커밋 용량도 거의 늘지 않는다.

    한 줄 형식:  source|external_id|category
    """

    def __init__(self, path: str | Path = "data/seen.txt"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.keys: set[str] = set()
        if self.path.exists():
            self.keys = {
                line.strip()
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }

    @staticmethod
    def _key(p: Posting) -> str:
        return f"{p.source}|{p.external_id}|{p.category}"

    @property
    def is_empty(self) -> bool:
        return not self.keys

    def total(self) -> int:
        return len(self.keys)

    def filter_new(self, postings: list[Posting]) -> list[Posting]:
        fresh, batch = [], set()
        for p in postings:
            k = self._key(p)
            if k in self.keys or k in batch:
                continue
            batch.add(k)
            fresh.append(p)
        return fresh

    def add(self, postings: list[Posting]) -> None:
        """새 키를 더하고 정렬해서 다시 쓴다. 정렬해 두면 커밋 diff 가 안 튄다."""
        self.keys |= {self._key(p) for p in postings}
        self.path.write_text(
            "\n".join(sorted(self.keys)) + "\n", encoding="utf-8"
        )


def _norm(text: str) -> str:
    """중복 판정용. 공백·괄호·기호를 걷어내고 비교한다."""
    return re.sub(r"[\s\[\]()（）·・,./-]+", "", (text or "").lower())


def _deadline(raw: str) -> str:
    """사이트마다 '~ 08/31(월)' / '10/19' / '채용시' 로 제각각이라 물결표를 정리한다."""
    t = (raw or "").strip().lstrip("~").strip()
    return t


def snapshot(
    postings: list[Posting],
    fresh_keys: set[tuple[str, str, str]] | None = None,
    path: str | Path = "data/postings.json",
) -> Path:
    """현재 열려 있는 공고 전체를 JSON 으로 떨궈 둔다.

    디스코드에는 신규만 보내지만 웹 목록에는 전체가 필요해서 따로 남긴다.
    build_site.py 가 이 파일을 읽어 페이지를 만든다.
    """
    fresh_keys = fresh_keys or set()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 같은 공고가 사이트마다 올라와 있으면 목록에 두 번 뜬다.
    # 회사+제목이 같으면 한 건으로 보고, 분류가 정확한 소스를 남긴다.
    priority = {"gamejob": 0, "wanted": 1, "saramin": 2, "jobkorea": 3}
    best: dict[tuple[str, str, str], Posting] = {}
    for p in postings:
        k = (p.category, _norm(p.company), _norm(p.title))
        cur = best.get(k)
        if cur is None or priority.get(p.source, 9) < priority.get(cur.source, 9):
            # 어느 소스에서든 새로 뜬 공고면 NEW 표시는 살려 둔다
            if cur is not None and cur.key in fresh_keys:
                fresh_keys = fresh_keys | {p.key}
            best[k] = p

    rows = [
        {
            "source": p.source,
            "id": p.external_id,
            "category": p.category,
            "title": p.title,
            "company": p.company,
            "url": p.url,
            "career": p.career_raw,
            "years": p.career_min,
            "location": p.location,
            "employment": p.employment,
            "deadline": _deadline(p.deadline),
            "new": p.key in fresh_keys,
        }
        for p in best.values()
    ]
    rows.sort(key=lambda r: (r["category"], r["years"] if r["years"] is not None else 99,
                             r["company"], r["title"]))
    out.write_text(
        json.dumps(
            {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "count": len(rows), "postings": rows},
            ensure_ascii=False, separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return out
