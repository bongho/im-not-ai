---
name: humanize-structure
version: "0.1.0"
description: 글의 뼈대(문단 순서, 채움 문단, 결론 반복, 빠진 입장)에서 드러나는 AI 티를 먼저 고치고, 이어서 humanize-korean으로 문장을 다듬는 2단계 스킬. sepia(StoryScope 기반 구조 점검)를 한국어 업무 글에 맞게 옮겼다. 사실, 수치, 인용, 고유명사는 바꾸지 않고, 구조 변경은 diff로 보여 준 뒤 승인을 받는다. 모드 3개: write(재료로 처음부터 쓰기), refactor(구조 편집 + 윤문), review(진단만). 트리거: "구조부터 사람처럼", "글 뼈대 AI 티", "sepia로", "처음부터 사람처럼 써줘", "보고서 구조 점검", "문단 순서가 AI 같아", "/humanize-structure". 문장 표현만 고치면 되는 글은 humanize-korean을 바로 쓴다.
metadata:
  loop_type: product
  loop_exit_criterion: "사용자가 구조 편집을 승인하면 2단계로 넘어가고, 2단계 게이트 통과 시 종료"
  max_iterations: 2
  human_gate: true
---

# Humanize Structure: 뼈대 먼저, 문장은 다음

humanize-korean은 "내용은 한 글자도 건드리지 않는다"는 원칙 아래 문장과 표현만 고친다. 그런데 문장을 다 고쳐도 남는 신호가 글의 구조에 있다(StoryScope: 표면 문체를 사람이 고친 뒤에도 구조 특징만으로 판별 성능이 95.5%에서 93.9%로만 떨어졌다. 영어 소설 코퍼스). 이 스킬은 그 구조 층을 1단계로 따로 다루고, 문장 층은 humanize-korean에 그대로 맡긴다.

불변 원칙을 이렇게 나눈다.

| 층 | 바꿀 수 있는 것 | 바꿀 수 없는 것 | 검증 |
|---|---|---|---|
| 1단계 구조 | 문단과 문장의 순서, 삭제, 병합, 분할 | 사실, 수치, 인용, 고유명사, 주장. 원문에 없는 내용 추가 | `structure_facts.py` + 사용자 승인 |
| 2단계 문장 | humanize-korean 규칙 그대로 | humanize-korean 철칙 그대로 | humanize-korean 게이트 |

## Phase 0: 준비

첫 줄에 출력한다.

```
humanize-structure v0.1: {write|refactor|review} 모드 / run_id: structure-{YYYY-MM-DD-NNN}
```

**모드 결정**
- 재료(메모, 사실 목록, 경험)를 주고 글을 써 달라 → **write**
- "진단만", "고치지 말고", "어디가 문제야" → **review**
- 그 외 완성된 글 → **refactor** (기본)

**경로**: 데이터는 cwd 기준 `_workspace/structure-{YYYY-MM-DD-NNN}/`. 시퀀스는 `Glob(pattern="_workspace/structure-YYYY-MM-DD-*/00_original.txt")`로 찾아 최댓값 + 1. 스크립트는 절대경로로 부른다.

```bash
SKILL_ROOT="$(d="$(cd -P "${CLAUDE_SKILL_DIR}" && pwd)"; \
  while [ "$d" != / ] && [ ! -d "$d/.claude-plugin" ]; do d="$(dirname "$d")"; done; echo "$d")"
ls "${SKILL_ROOT}/scripts/structure_facts.py"
```

`ls`가 실패하면 사실 보존 검사 없이 진행한다고 사용자에게 알린 뒤 계속한다. 조용히 건너뛰지 않는다.

**자리(venue) 결정**: 이 글이 어디에 올라가는지(보고 문서, 슬랙, PR 답변, 회고, 블로그, 칼럼)를 첫 300자와 사용자 말로 추정한다. 확신이 없으면 한 번만 묻는다. 같은 자리의 사람 글 표본을 사용자가 주면 그게 기준이다. 없으면 [`${CLAUDE_SKILL_DIR}/references/venues.md`](references/venues.md)의 기준과 `genre` 값을 쓴다.

## refactor / review 경로

### Phase 1: 구조 진단

1. 원문을 `00_original.txt`로 저장한다.
2. [`${CLAUDE_SKILL_DIR}/references/structure-pass.md`](references/structure-pass.md)의 S-1 ~ S-11을 **하나씩** 본다. 자리별로 먼저 볼 항목은 venues.md 표를 따른다.
3. S-7, S-8은 실제로 만들어 본다. 문단마다 답하는 질문을 한 줄씩 적고, 문단 첫 문장만 뽑아 목록으로 읽는다.
4. 점검표 말미의 보고 형식으로 `01_structure_report.md`를 쓰고 사용자에게 보여 준다.

**review 모드는 여기서 끝난다.** 파일 수정 없음.

판정이 `깨끗함` 또는 `단발 적중`이면 1단계를 건너뛰고 바로 Phase 4로 간다고 알린다. 한 건 적중으로 뼈대를 흔들지 않는다.

### Phase 2: 질문

보고서의 `질문:` 줄(S-3 입장, S-4 구체성, S-11 강조)이 비어 있지 않으면 `AskUserQuestion`으로 묻는다. 답이 오기 전에 그 빈칸을 채우지 않는다. 사용자가 "넘어가"라고 하면 `TODO:`로 남긴다.

### Phase 3: 구조 편집과 승인

1. 적중 항목의 조치(삭제, 이동, 병합, 분할)만 적용해 `02_structure.md`를 쓴다. 문장 안 표현은 손대지 않는다. 2단계 몫이다. Phase 2 답변은 사용자 말 그대로에 가깝게 넣는다.
2. 사실 보존 검사:
   ```bash
   python3 "${SKILL_ROOT}/scripts/structure_facts.py" \
     --before _workspace/{run_id}/00_original.txt --after _workspace/{run_id}/02_structure.md
   ```
   - exit 2(FAIL, 원문에 없던 수치나 인용 주입): 편집을 다시 한다. Phase 2 답변에서 온 수치라면 그 사실을 승인 화면에 적고 통과로 본다.
   - exit 1(REVIEW, 앵커 소실): 소실 목록을 승인 화면에 그대로 싣는다.
3. 변경 내역을 보여 준다. 무엇을 지웠고(인용), 무엇을 어디로 옮겼는지 항목별로 적고, 각 항목에 근거 S-ID를 붙인다.
4. `AskUserQuestion`으로 승인을 받는다: 승인 / 일부 되돌리기(어느 항목) / 1단계 버리고 원문으로 2단계.
5. 되돌리기 지시는 최대 2회까지 반영한다. 그래도 합의가 안 되면 원문으로 2단계에 간다.

## write 경로

1. 재료를 `00_original.txt`로 저장한다. 이게 사실의 정본이다.
2. 독자, 한 줄 요지, 자리가 재료에 없으면 한 번에 묻는다.
3. 개요를 **문단별 질문 목록**으로 짠다. 짠 개요에 S-7(행정 면담 순서, 성찰 꼬리), S-8(깔끔한 요약 개요), S-10(답이 늦게 나옴)을 적용해 고친 뒤 사용자에게 보여 주고 승인받는다.
4. 승인된 개요대로 초안 `02_structure.md`를 쓴다. 재료에 없는 사실은 쓰지 않고 `TODO:`로 둔다. 문장 표현은 거칠어도 된다. 2단계가 다듬는다.
5. `structure_facts.py --before 00_original.txt --after 02_structure.md`로 수치와 인용 주입만 본다(write에서 소실은 정상이다. 재료를 다 쓰지 않아도 된다).

## Phase 4: 문장 단계 (humanize-korean)

`02_structure.md`(1단계를 건너뛰었으면 `00_original.txt`)를 입력으로 `humanize-korean` 스킬을 호출하고, 그 스킬의 절차를 끝까지 따른다. `genre`는 venues.md 값을 넘긴다.

> **에이전트 이름 충돌 주의**: 이 저장소를 플러그인으로 설치하면 스킬과 에이전트가 `humanize-korean:` 네임스페이스로 들어온다. 사용자 환경에 같은 이름(`humanize-monolith` 등)의 다른 버전 에이전트가 따로 있을 수 있다. 서브에이전트 목록에 `humanize-korean:humanize-monolith`처럼 접두가 붙은 항목이 있으면 **그것을 쓴다**. 스킬도 `humanize-korean:humanize-korean`이 있으면 그것을 호출한다.

## Phase 5: 마무리 검사

```bash
python3 "${SKILL_ROOT}/scripts/structure_facts.py" \
  --before _workspace/{run_id}/00_original.txt --after <humanize-korean 최종본>
```

두 단계를 거친 결과가 원문 대비 수치나 인용을 주입하지 않았는지 끝에서 한 번 더 본다(refactor 기준. write는 Phase 3 승인분과 대조). 결과를 최종본 경로, 1단계에서 바꾼 항목 수, 2단계 게이트 결과와 함께 보고한다.

## 하지 않는 것

- 소설의 서사 구조 처방(sepia narrative-pass)은 옮기지 않았다. 인과를 느슨하게 하거나 사건 배치를 바꾸는 일은 내용 변경이다.
- 구조 항목을 점수로 내지 않는다. S 계열은 한국어 실측 전이라 판별력 수치가 없다.
- 1단계에서 문장 표현을 고치지 않는다. 두 단계가 같은 문장을 고치면 어느 쪽 규칙이 바꿨는지 추적할 수 없다.

## 참조

- 구조 점검표: [`${CLAUDE_SKILL_DIR}/references/structure-pass.md`](references/structure-pass.md)
- 자리별 기준: [`${CLAUDE_SKILL_DIR}/references/venues.md`](references/venues.md)
- 사실 보존 검사: `${SKILL_ROOT}/scripts/structure_facts.py`
- 원 출처: [Nanako0129/sepia](https://github.com/Nanako0129/sepia) (MIT), StoryScope [arXiv:2604.03136](https://arxiv.org/abs/2604.03136)
