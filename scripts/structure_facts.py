#!/usr/bin/env python3
"""구조 단계 사실 보존 검사 (LLM 콜 0, 표준 라이브러리만).

humanize-structure의 1단계(구조 편집)는 순서를 바꾸고 채움 문장을 덜어내므로
문자율 게이트(verify_gates.py P0)로는 판정할 수 없다. 대신 "사실 앵커"가
원문과 구조 편집본 사이에서 보존됐는지만 결정적으로 본다.

앵커 4종:
    수치     — checks._number_values 재사용 (천단위 콤마·한글 수사 단위 정규화)
    인용     — checks.extract_quotes 재사용 (8자 이상 직접 인용)
    라틴 토큰 — 영문 고유명·제품명·식별자 (2자 이상, 대소문자 무시)
    코드/URL — `code` 스팬과 http(s) URL

판정:
    주입(원문에 없던 수치·인용) → FAIL. 사실 추가는 구조 편집이 아니다.
    소실(원문에 있던 앵커가 사라짐) → REVIEW. 채움 문장 삭제의 정상
        부산물일 수도 있어 막지 않고, 사람이 승인할 목록으로만 낸다.

Exit code: 0 통과 / 1 REVIEW 항목 있음 / 2 FAIL / 3 실행 오류

CLI:
    python3 scripts/structure_facts.py --before 01_input.txt --after 02_structure.md [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checks import _number_values, extract_quotes  # noqa: E402

_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+#-]*[A-Za-z0-9]")
_CODE_RE = re.compile(r"`([^`\n]+)`")
_URL_RE = re.compile(r"https?://[^\s)\]>]+")


def latin_tokens(text: str) -> set[str]:
    text = _URL_RE.sub(" ", _CODE_RE.sub(" ", text))
    return {m.group(0).lower() for m in _LATIN_RE.finditer(text)}


def code_and_urls(text: str) -> set[str]:
    return set(_CODE_RE.findall(text)) | set(_URL_RE.findall(text))


def compare(before: str, after: str) -> dict[str, dict[str, list[str]]]:
    anchors = {
        "numbers": (_number_values(before), _number_values(after)),
        "quotes": (set(extract_quotes(before)), set(extract_quotes(after))),
        "latin": (latin_tokens(before), latin_tokens(after)),
        "code_url": (code_and_urls(before), code_and_urls(after)),
    }
    return {
        name: {"dropped": sorted(b - a), "injected": sorted(a - b)}
        for name, (b, a) in anchors.items()
    }


def verdict(result: dict[str, dict[str, list[str]]]) -> int:
    # 라틴 토큰·코드 주입은 표기 통일(예: 한글 → 영문 제품명)일 수 있어 FAIL에서 뺀다.
    if result["numbers"]["injected"] or result["quotes"]["injected"]:
        return 2
    if any(r["dropped"] for r in result.values()):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="구조 단계 사실 보존 검사")
    p.add_argument("--before", required=True)
    p.add_argument("--after", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    try:
        before = Path(args.before).read_text(encoding="utf-8")
        after = Path(args.after).read_text(encoding="utf-8")
    except OSError as e:
        print(f"실행 오류: {e}", file=sys.stderr)
        return 3

    result = compare(before, after)
    code = verdict(result)
    label = {0: "PASS", 1: "REVIEW", 2: "FAIL"}[code]
    print(f"structure_facts: {label}")
    for name, r in result.items():
        if r["injected"]:
            print(f"  [{name}] 주입: {r['injected']}")
        if r["dropped"]:
            print(f"  [{name}] 소실: {r['dropped']}")
    if args.json:
        print(json.dumps({"verdict": label, **result}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
