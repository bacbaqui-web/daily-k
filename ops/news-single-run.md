# 09:00 / 21:00 단일 뉴스 조사·발행 계약

뉴스 운영은 이 문서와 `news-briefing.md`를 우선합니다. 2026-10-11 오전 회차부터 한국시간 매일 09:00·21:00에 조사·검증·작성·최종 게시를 한 번의 예약 실행으로 처리합니다. 사전 준비 예약과 다음 회차 공개 준비본은 사용하지 않습니다. 예약 설정은 부모 작업이 관리하며 이 저장소는 예약이나 수집 프로세스를 만들지 않습니다.

## 입력과 명령

`schemas/news-publication.schema.json`의 봉투 형식으로 파일을 작성합니다. 실제 기사 내용은 기존 뉴스 브리핑 구조·품질·출처·중복·웹툰·이슈 검증을 모두 유지합니다.

```json
{
  "schemaVersion": 1,
  "operationId": "publish-news-YYYY-MM-DD-am",
  "brief": { "기존 뉴스 브리핑 필드": "실제 조사·검증한 자료" }
}
```

위 형식 설명은 실행 가능한 기사 샘플이 아닙니다. `brief.id=YYYY-MM-DD-am|pm`, date, edition, timezone, cutoffAt, generatedAt, overview, stories, events, keywords 등 기존 필수 필드를 채웁니다.

```sh
python3 scripts/live/manage.py publish-news /absolute/final-news.json --check
python3 scripts/live/manage.py publish-news /absolute/final-news.json --push
```

대상 회차는 파일의 `brief.id`입니다. `--edition`을 함께 넣지 않습니다. 예약이 늦거나 자정을 넘겨도 최초 대상 날짜·회차와 동일 입력/operationId를 유지합니다. 다른 회차로 바꾸거나 이미 확정된 회차를 덮어쓰지 않습니다. 변경된 입력을 같은 operationId로 재사용하면 거부합니다. 같은 회차·동일 입력은 operationId가 달라도 최초 확정본을 재사용하고, 다른 입력이면 명시적 정정 절차로 처리합니다.

`stage-news`, `finalize-news`, 일반 `finalize`는 새 회차에 사용하지 않습니다. `finalize-news`에 brief를 넣어도 발행되지 않으며 명시적으로 오류를 냅니다. `scripts/news/publish.py`는 내용 검증·파생 파일 생성 내부 모듈로 남지만 새 회차의 직접 쓰기 CLI는 거부합니다.

## 실제 시각

- 적용 경계: **2026-10-11 오전부터**. 이미 발행된 2026-10-07~10-10의 08:30/20:30 cutoffAt과 그 이전 09:00/21:00 기록은 그대로 보존합니다.
- 새 `cutoffAt`: 대상 날짜 오전 09:00 또는 오후 21:00 KST와 정확히 같은 시점. UTC 등 동등한 시간대 표기도 허용합니다. 기사는 이 시각까지 알려진 자료만 포함합니다. 경계 이후 보도/수정의 새 사실을 경계 이전 정보처럼 쓰지 않습니다.
- sources/relatedArticles/event source의 `verifiedAt`: 이번 실행에서 실제로 확인한 시각이며 cutoffAt 이상, 해당 generatedAt/updatedAt 이하입니다. 사전 확인을 9시 확인으로 바꾸지 않습니다.
- `generatedAt`: 실제 작성 완료 시각. cutoffAt 이상이며 실행 현재 시각보다 미래일 수 없습니다. updatedAt도 실제 시각이며 생성보다 빠르거나 현재보다 늦으면 거부합니다.
- `finalizedAt`·scheduledFor·recordId는 게시 명령이 기록합니다. 입력에서 공급하거나 앞당길 수 없습니다. 기준 9시와 실제 완료 시각은 같다고 가정하지 않습니다.
- finalizedAt은 데이터 확정 트랜잭션 시각이며 실제 웹 배포 완료 시각이 아닙니다. GitHub push 결과, 정확한 커밋의 Pages 실행 완료 시각, 실제 공개 JSON 조회 시각을 실행 결과에 별도로 보존합니다. 아직 모르는 배포 시각을 불변 JSON에 만들어 넣지 않습니다.

## 저장·실패·보존

명령은 준비 창 없이 명시한 회차의 뉴스 JSON, 회차 인덱스, 누적 이슈 파일·인덱스, 뉴스 전용 불변 스냅샷(items=[]), 실행 이벤트를 함께 계획합니다. 다음 창을 생성하거나 기존 window를 전진시키지 않습니다. 기존 window·과거 회차·커뮤니티·rolling 유머는 보존합니다.

로컬은 기존 flock·개별 원자 교체·복구 저널을 사용합니다. 여러 파일 전체가 하나의 파일시스템 연산으로 바뀌는 것은 아닙니다. 실패 시 `python3 scripts/live/manage.py recover`가 원본 파일→인덱스→current 순으로 복구합니다. `--check`는 공개 파일을 쓰지 않습니다. 뉴스/이슈 검증 실패는 전체 계획을 거부합니다.

`--push`는 격리 clone에서 최신 main을 읽고 한 커밋으로 정상 fast-forward만 전송합니다. 경합 시 최신 상태에 같은 의도를 재적용하며 강제 push하지 않습니다. 전송이 불확실하면 원격 회차·작업 기록부터 확인합니다. 실제 발행된 커밋의 Pages 성공과 공개 회차/인덱스/이슈 JSON을 검증하기 전에는 완료로 보고하지 않습니다.

뉴스 화면은 최근 실제 발행 회차를 기본으로 표시합니다. 명시한 날짜·오전/오후·record·과거 기사 링크는 보존합니다. 미래 또는 미발행 회차를 직접 선택하면 미발행 상태만 표시하고 조사 진행을 주장하지 않습니다. 기존 24시간 유머 탭의 계약은 변경하지 않습니다.
