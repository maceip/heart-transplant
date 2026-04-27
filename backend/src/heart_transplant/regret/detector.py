from __future__ import annotations

from collections import Counter, defaultdict

from heart_transplant.models import CodeNode, StructuralArtifact
from heart_transplant.regret.models import RegretItem
from heart_transplant.regret.patterns import PATTERNS
from heart_transplant.regret.scoring import score_pattern_match, to_regret_item


def _assignments_by_node(semantic: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in semantic.get("block_assignments", []) or []:
        nid = str(row.get("node_id", ""))
        blk = str(row.get("primary_block", ""))
        if nid and blk:
            out[nid] = blk
    return out


def _keyword_hits(nodes: list[CodeNode], keywords: tuple[str, ...]) -> tuple[int, list[str], list[str], list[str]]:
    hit_nodes: list[str] = []
    hit_files: list[str] = []
    evidence: list[str] = []
    total = 0
    for node in nodes:
        blob = f"{node.name}\n{node.content[:800]}".lower()
        matched = [k for k in keywords if k in blob]
        if matched:
            total += len(matched)
            hit_nodes.append(node.scip_id)
            hit_files.append(node.file_path)
            evidence.append(f"{node.file_path}: matched {', '.join(matched)} on `{node.name}`")
    return total, evidence, hit_nodes, hit_files


def _block_alignment(nodes: list[CodeNode], pattern: RegretPattern, assignments: dict[str, str]) -> float:
    if not pattern.block_hints:
        return 0.0
    hits = 0
    for n in nodes:
        b = assignments.get(n.scip_id, "")
        if b in pattern.block_hints:
            hits += 1
    return min(1.0, hits / max(len(nodes), 1))


def _file_spread(file_paths: list[str]) -> float:
    return float(len(set(file_paths)))


def detect_regrets(
    artifact: StructuralArtifact,
    semantic: dict | None,
    *,
    min_score: float = 0.35,
) -> list[RegretItem]:
    assignments = _assignments_by_node(semantic or {})
    regrets: list[RegretItem] = []
    by_pattern_files: dict[str, list[str]] = defaultdict(list)

    for pattern in PATTERNS:
        total_kw, evidence, hit_nodes, hit_files = _keyword_hits(artifact.code_nodes, pattern.keywords)
        if total_kw == 0:
            continue
        nodes_subset = [n for n in artifact.code_nodes if n.scip_id in set(hit_nodes)]
        align = _block_alignment(nodes_subset, pattern, assignments)
        spread = _file_spread(hit_files)
        score = score_pattern_match(
            pattern,
            keyword_hits=total_kw,
            block_alignment=align,
            file_spread=spread,
        )
        if score < min_score:
            continue
        rid = f"{artifact.repo_name}:{pattern.pattern_id}"
        regrets.append(
            to_regret_item(
                pattern,
                regret_id=rid,
                score=score,
                evidence=evidence[:12],
                node_ids=hit_nodes[:40],
                file_paths=hit_files,
            )
        )
        by_pattern_files[pattern.pattern_id].extend(hit_files)

    route_counts = Counter(n.file_path for n in artifact.code_nodes if "route" in n.file_path.lower())
    for fp, cnt in route_counts.items():
        if cnt >= 12:
            rid = f"{artifact.repo_name}:fat_route_file:{fp}"
            score = min(0.85, 0.35 + cnt / 40.0)
            if score >= min_score:
                regrets.append(
                    RegretItem(
                        regret_id=rid,
                        pattern_id="fat_route_file",
                        title="Dense route handler file",
                        score=score,
                        confidence=score,
                        evidence=[f"{fp} contains {cnt} extracted code units"],
                        node_ids=[n.scip_id for n in artifact.code_nodes if n.file_path == fp][:50],
                        file_paths=[fp],
                    )
                )

    regrets.sort(key=lambda r: -r.score)
    return regrets
