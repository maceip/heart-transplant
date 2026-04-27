from __future__ import annotations

import os
from collections.abc import Sequence

from openai import OpenAI

from heart_transplant.models import CodeNode, NeighborhoodRecord
from heart_transplant.ontology import iter_blocks
from heart_transplant.semantic.models import BlockAssignment, BlockClassifyResult


def classify_with_openai(
    node: CodeNode,
    neighbor: NeighborhoodRecord | None = None,
    *,
    model: str = "gpt-4o-mini",
) -> BlockAssignment:
    """Structured classification via the OpenAI API (Pydantic ``parse``); requires ``OPENAI_API_KEY``."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI()
    bl = "\n".join(f"- {b}" for b in iter_blocks())
    imp = " ".join(neighbor.imports) if neighbor else ""
    prompt = f"""Classify the following code into exactly ONE of these functional blocks.
Blocks:
{bl}

file_path: {node.file_path}
name: {node.name}
kind: {node.kind}
imports_neighborhood: {imp}
code:
```
{node.content[:6000]}
```
Return the best single block, confidence 0-1, and one short sentence of reasoning.
"""
    resp = client.beta.chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=BlockClassifyResult,  # type: ignore[arg-type]
    )
    out = resp.choices[0].message.parsed
    if not isinstance(out, BlockClassifyResult):
        raise RuntimeError("parse failed")
    return BlockAssignment(
        node_id=node.scip_id,
        primary_block=out.primary_block,
        confidence=out.confidence,
        reasoning=out.reasoning,
        supporting_neighbors=neighbor.imports if neighbor else [],
    )


def classify_batch(
    items: Sequence[tuple[CodeNode, NeighborhoodRecord | None]],
    *,
    use_openai: bool = True,
) -> list[BlockAssignment]:
    from heart_transplant.classify.heuristic import classify_node_heuristic

    res: list[BlockAssignment] = []
    for node, nbr in items:
        if use_openai and os.environ.get("OPENAI_API_KEY"):
            res.append(classify_with_openai(node, nbr))
        else:
            res.append(classify_node_heuristic(node, nbr))
    return res
