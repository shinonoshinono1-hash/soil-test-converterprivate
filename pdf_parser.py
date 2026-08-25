from __future__ import annotations

import io
import re
from collections import defaultdict
from pathlib import Path
from typing import BinaryIO, Iterable

import fitz

from models import Hole, Sample

# JGS「土質試験結果一覧表（基礎地盤）」の標準帳票で使われる行Y座標。
# 座標は帳票自体の固定レイアウトに基づく。多少のズレは許容する。
Y = {
    "wet_density": 149.3,
    "dry_density": 163.4,
    "particle_density": 177.6,
    "water_content": 191.7,
    "void_ratio": 205.9,
    "saturation": 220.1,
    "gravel": 248.4,
    "sand": 262.5,
    "max_size": 305.1,
    "d50": 333.5,
    "liquid_limit": 361.8,
    "plastic_limit": 375.9,
    "plasticity_index": 390.1,
    "consistency_index": 404.4,
    # 一軸圧縮強さ qu。同一採取深度で最大3供試体を想定。
    "qu1": 531.9,
    "qu2": 546.1,
    "qu3": 560.3,
    "cc": 475.2,
    "pc": 489.3,
    "cu": 602.7,
    "phi_u": 616.9,
}

SAMPLE_RE = re.compile(r"No\.(\d+):([0-9]+[A-Za-z]-[0-9]+)")
DEPTH_RE = re.compile(r"\(?\s*([0-9.]+)\s*[～~〜-]\s*([0-9.]+)\s*m?\)?")
NUMERIC_RE = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")


def parse_pdfs(files: Iterable[str | Path | bytes | BinaryIO]) -> list[Hole]:
    by_hole: dict[int, list[Sample]] = defaultdict(list)
    seen: set[tuple[int, str]] = set()

    for source in files:
        for sample in parse_pdf(source):
            key = (sample.hole_no, sample.sample_no)
            if key in seen:
                continue
            seen.add(key)
            by_hole[sample.hole_no].append(sample)

    holes: list[Hole] = []
    for hole_no in sorted(by_hole):
        samples = by_hole[hole_no]
        samples.sort(key=_sample_sort_key)
        holes.append(Hole(hole_no=hole_no, samples=samples))
    return holes


def parse_pdf(source: str | Path | bytes | BinaryIO) -> list[Sample]:
    doc = _open_document(source)
    out: list[Sample] = []
    try:
        for page_index, page in enumerate(doc):
            text = page.get_text("text") or ""
            if "土質試験結果一覧" not in text or "基礎地盤" not in text:
                continue
            words = page.get_text("words")
            labels = []
            for w in words:
                x0, y0, x1, y1, token = w[:5]
                m = SAMPLE_RE.fullmatch(token.strip())
                if m:
                    labels.append((x0, y0, x1, y1, token.strip(), int(m.group(1)), m.group(2)))
            if not labels:
                continue
            labels.sort(key=lambda w: w[0])
            centers = [(w[0] + w[2]) / 2 for w in labels]

            for i, label in enumerate(labels):
                _, _, _, _, _, hole_no, sample_no = label
                center = centers[i]
                # 帳票は6列で約65ptピッチ。隣接列との中点を境界にする。
                left = (centers[i - 1] + center) / 2 if i > 0 else center - 34
                right = (center + centers[i + 1]) / 2 if i + 1 < len(centers) else center + 34
                col_words = [w for w in words if left <= (w[0] + w[2]) / 2 < right]
                sample = _parse_sample_column(hole_no, sample_no, col_words, page_index + 1)
                out.append(sample)
    finally:
        doc.close()
    return out


def _parse_sample_column(hole_no: int, sample_no: str, words: list[tuple], page_no: int) -> Sample:
    depth = _depth_from_words(words)
    sample = Sample(hole_no=hole_no, sample_no=sample_no, depth=depth, source_page=page_no)

    for field, y in Y.items():
        setattr(sample, field, _numeric_at_y(words, y, tol=4.8))

    # シルト・粘土は、個別記載と2行結合のまとめ記載が混在する。
    fines = []
    for w in words:
        token = _clean_numeric(w[4])
        y0 = w[1]
        if token is not None and 272.0 <= y0 <= 300.5:
            fines.append((y0, token))
    fines.sort(key=lambda x: x[0])
    if len(fines) >= 2:
        # 通常は y≈276.8 がシルト、y≈291.0 が粘土。
        sample.silt = fines[0][1]
        sample.clay = fines[1][1]
        sample.combined_fines = None
    elif len(fines) == 1:
        sample.silt = None
        sample.clay = None
        sample.combined_fines = fines[0][1]
    else:
        sample.silt = sample.clay = sample.combined_fines = None

    name, symbol = _classification(words)
    sample.classification_name = name
    sample.classification_symbol = symbol

    if not depth:
        sample.warnings.append("採取深度を読み取れませんでした")
    return sample


def _depth_from_words(words: list[tuple]) -> str:
    for w in sorted(words, key=lambda x: x[1]):
        if 128 <= w[1] <= 145:
            token = w[4].replace(" ", "")
            m = DEPTH_RE.search(token)
            if m:
                return f"{m.group(1)}～{m.group(2)}"
    return ""


def _numeric_at_y(words: list[tuple], target: float, tol: float) -> str | None:
    candidates = []
    for w in words:
        token = _clean_numeric(w[4])
        if token is None:
            continue
        dist = abs(w[1] - target)
        if dist <= tol:
            candidates.append((dist, w[0], token))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def _clean_numeric(token: str) -> str | None:
    t = token.strip().replace(",", "")
    if t in {"-", "－", "―", "—"}:
        return None
    if NUMERIC_RE.fullmatch(t):
        return t
    return None


def _classification(words: list[tuple]) -> tuple[str | None, str | None]:
    name_parts: list[tuple[float, float, str]] = []
    limit_note: str | None = None
    symbol: str | None = None
    for w in words:
        x0, y0, x1, y1, token = w[:5]
        t = token.strip()
        if 414 <= y0 <= 443:
            if "高液性限界" in t:
                limit_note = "高液性限界"
            elif "低液性限界" in t:
                limit_note = "低液性限界"
            elif t and not t.startswith("(") and not t.startswith("（"):
                name_parts.append((y0, x0, t))
        if 443 <= y0 <= 453 and (t.startswith("(") or t.startswith("（")):
            cleaned = t.strip("()（） ")
            if cleaned and "液性限界" not in cleaned:
                symbol = cleaned
    name_parts.sort()
    name = "".join(p[2] for p in name_parts) or None
    if name and limit_note:
        name = f"{name}（{limit_note}）"
    return name, symbol


def _sample_sort_key(sample: Sample):
    try:
        start = float(sample.depth.split("～", 1)[0])
    except Exception:
        start = 10**9
    return (start, sample.sample_no)


def _open_document(source):
    if isinstance(source, (str, Path)):
        return fitz.open(str(source))
    if isinstance(source, bytes):
        return fitz.open(stream=source, filetype="pdf")
    data = source.read()
    if hasattr(source, "seek"):
        source.seek(0)
    return fitz.open(stream=data, filetype="pdf")
