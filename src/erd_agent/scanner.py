from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
import re

# 파일명 힌트: *Entity.java
ENTITY_NAME_RE = re.compile(r".*Entity\.java$", re.IGNORECASE)

# 본문 힌트: @Entity 중심
ENTITY_ANN_RE = re.compile(r"@\s*Entity\b")
TABLE_ANN_RE = re.compile(r"@\s*Table\b")  # 보조 신호(테이블명 추출용)

@dataclass
class ScanConfig:
    prefer_dirs: tuple[str, ...] = ("models", "model", "entity", "entities", "domain")
    exts: tuple[str, ...] = (".java",)
    include_table_only: bool = False  # 레거시 대응 옵션(기본 False)

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def _has_entity(text: str) -> bool:
    return bool(ENTITY_ANN_RE.search(text))

def _has_table(text: str) -> bool:
    return bool(TABLE_ANN_RE.search(text))

def scan_repo(repo_path: Path, cfg: ScanConfig | None = None) -> List[Path]:
    """
    JPA 엔티티 후보 파일을 찾아 반환한다.
    우선순위:
      1) @Entity가 있는 파일
      2) 파일명이 *Entity.java 인 파일 (보조)
      3) (옵션) @Table만 있는 파일 include_table_only=True일 때만
    """
    cfg = cfg or ScanConfig()
    candidates: set[Path] = set()

    def consider_file(f: Path):
        if not f.is_file() or f.suffix not in cfg.exts:
            return
        text = _read_text(f)

        if _has_entity(text):
            candidates.add(f)
            return

        # 보조: 파일명 패턴
        if ENTITY_NAME_RE.match(f.name):
            candidates.add(f)
            return

        # 매우 예외적인 케이스만: @Table only
        if cfg.include_table_only and _has_table(text):
            candidates.add(f)

    # 1) prefer_dirs 우선 탐색
    for d in cfg.prefer_dirs:
        p = repo_path / d
        if p.exists() and p.is_dir():
            for f in p.rglob("*"):
                consider_file(f)

    # 2) 전체 탐색 (보완)
    for f in repo_path.rglob("*.java"):
        consider_file(f)

    return sorted(candidates)