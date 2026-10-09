# 진행 중 목록과 오전·오후 9시 확정 기록

이 문서는 새 수집·갱신·확정 경로의 우선 지침입니다. 기존 `community-briefing.md`와 `news-briefing.md`의 콘텐츠 검증·인용·출처·안전 규칙은 유지하되, 08:55/20:55 직접 발행 절차는 아래 준비→확정 절차로 대체합니다. 기존 과거 JSON·공유 링크·미디어·뉴스 이슈 기록은 수정하지 않습니다. 저장소에 새 수집기나 예약 실행을 설치하지 않습니다.

## 시간 계약

- 시간대는 `Asia/Seoul`. 창은 전날 21:00 이상~당일 09:00 미만(am), 당일 09:00 이상~21:00 미만(pm). 정확히 09:00/21:00에 도착한 새 자료는 다음 창입니다.
- `firstObservedAt`: 사람이/매크로가 실제 처음 확인한 시각. 같은 안정된 ID에서는 불변입니다.
- `lastVerifiedAt`, 출처의 `verifiedAt`, 지표의 `observedAt`: 실제 관찰 시각. 미확인 시각·숫자를 만들어 넣지 않습니다. 원문 `publishedAt` 미확인은 `null`.
- `recordedAt`: CLI가 실제로 그 입력을 적용한 시각. 사용자가 지정할 수 없습니다. 자료 관찰 시각이나 실제 Pages 공개 완료 시각이 아닙니다. 네트워크·배포 지연은 별도 보고합니다.
- `scheduledFor`: 09:00/21:00 확정 기준. `finalizedAt`: 실제 확정 실행 시각. 늦게 실행해도 앞당기지 않습니다. 그 사이에 온 새 항목·수정은 다음 창에 배정하고 이전 창은 그대로 보존합니다.
- 아직 확정하지 못한 창은 `windows`에 남아 화면에서 ‘확정 지연’으로 표시됩니다. 매크로/조사 실패는 `check`로 기록합니다. 누락을 수집 결과 0으로 바꾸지 않습니다. 빈 창도 실제 확정 실행 시 빈 기록으로 보관할 수 있습니다.
- 운영 시작 `activatedAt` 이전의 창을 소급 생성·확정하지 않습니다. 첫 창의 시작 경계가 운영 시작보다 앞서도 실제 운영 시작 시각을 함께 표시합니다.
- 뉴스 자료 기준 `cutoffAt`은 기존대로 08:30/20:30. 준비한 `generatedAt`은 실제 작성 완료 시각. 08:30/20:30은 준비 시작/기사 기준이며, 09:00/21:00 확정과 구분합니다. 과거 회차의 시간은 변경하지 않습니다.

## JSON과 명령

Python 3.11 이상, 표준 라이브러리와 Git만 사용합니다. 인증은 기존 Git 설정을 그대로 사용합니다. API·유료 서비스·로컬 예약은 추가하지 않습니다.

```sh
python3 scripts/live/manage.py status
python3 scripts/live/manage.py upsert /absolute/batch.json --check
python3 scripts/live/manage.py upsert /absolute/batch.json --push
python3 scripts/live/manage.py check /absolute/collection-check.json --push
python3 scripts/live/manage.py stage-news /absolute/prepared-news.json --check
python3 scripts/live/manage.py stage-news /absolute/prepared-news.json --push
python3 scripts/live/manage.py finalize --edition YYYY-MM-DD-am --push
python3 scripts/live/manage.py finalize --edition YYYY-MM-DD-pm --push
python3 scripts/live/manage.py correct /absolute/correction.json --push
```

`--check`는 어떠한 파일도 쓰지 않는 전체 의미 검증입니다. `--push` 없이 실행하면 현재 작업 공간의 `public/docs`만 갱신합니다. `--push`는 현재 작업 공간을 수정하지 않고 임시 clone에서 최신 원격 main을 읽어 검증·커밋·push합니다. 데이터만 게시할 때 UI 빌드는 불필요합니다. Pages 성공과 실제 JSON을 별도로 확인해야 공개 성공입니다.

`operationId`는 요청 한 번의 안정된 식별자(영문 소문자/숫자/하이픈, 최대 120자)입니다. 재시도는 같은 ID와 **동일한 입력 전체**를 사용합니다. 같은 ID로 다른 요청은 거부합니다. 수정/새 관찰은 새 operationId와 최신 expectedRevision을 사용합니다. 최초 항목 expectedRevision=0, 다음 수정은 `current.json.registry[id].revision`. 경합으로 revision이 달라지면 최신 자료를 검토하고 병합한 뒤 새 요청을 만듭니다.

검증용 문서 예시입니다. 실제 확인값으로 바꾼 입력만 게시합니다:

```json
{
  "schemaVersion": 1,
  "operationId": "topics-20261009-first",
  "items": [{
    "id": "stable-topic-id",
    "kind": "topic",
    "topicKey": "stable-topic-key",
    "expectedRevision": 0,
    "title": "직접 작성한 짧은 주제명",
    "summary": "직접 작성한 짧은 설명",
    "firstObservedAt": "실제 첫 발견 ISO 시각",
    "lastVerifiedAt": "실제 최종 확인 ISO 시각",
    "canonicalUrl": null,
    "sources": [{
      "name": "출처명", "title": "실제 원제", "url": "실제 확인 URL",
      "publishedAt": null, "verifiedAt": "실제 ISO 시각",
      "platform": "community", "region": "unknown", "regionEvidenceUrl": null,
      "periodStart": null, "periodEnd": null,
      "limitations": "확인 범위와 집계·접근 한계", "quotes": []
    }],
    "observations": [{
      "sourceUrl": "위 출처 URL", "metric": "실제 지표명", "value": null,
      "unit": "건", "observedAt": "실제 ISO 시각", "scope": "지표의 실제 관찰 범위"
    }],
    "limitations": "확인 한계와 누락", "selectionReason": "실제 선정 근거",
    "safetyChecked": true, "rightsChecked": true
  }]
}
```

- `kind=topic`: 매시간 커뮤니티·디시 주요 갤러리·인스타 공개 인기·X 자료를 편집 선정한 주제. 출처와 관찰은 여러 개 가능합니다. 공통 트렌드 목록 페이지를 여러 주제가 함께 인용할 수 있으므로 이런 경우 canonicalUrl=null, 안정된 topicKey로 중복을 판단합니다. 개별 원문인 경우 canonicalUrl을 지정합니다. URL의 추적 파라미터·fragment만 다른 경우 같은 원문으로 판정합니다.
- `kind=community`: 애객 매크로 경로. canonicalUrl은 실제 aagag 원문, category는 유머, 실제 댓글 ㅋ 합계 11 이상. `summary`는 빈 문자열. `content`에 기존 schemaVersion 2 story 객체를 그대로 담습니다. 바깥 id/topicKey/title은 content와 일치시킵니다. 바깥 sources에는 content의 모든 출처에 대한 관찰 메타데이터를 넣습니다. 기존 단일 imageUrl, bodyImages(순서·크기·출처·확인 시각), videoUrl/videoPosterUrl, 짧은 원문·댓글·portalLinks를 유지합니다. 이미지 파일은 저장하지 않고 직접 확인한 공개 URL만 사용합니다.
- source.platform: `aagag|community|dcinside|instagram|x|other`. source.region: `KR|unknown`. `KR`은 지역을 실제 확인한 regionEvidenceUrl 필수. **인스타는 unknown만 허용**하며 화면에서 ‘보조 자료, 한국 지역 순위 아님’, 집계 기간 미확인을 표시합니다. **X는 한국 지역 설정을 확인한 자료만 KR**, 그 밖에는 unknown으로 명시합니다. 제3자 추적 사이트의 지역·집계 한계도 limitations에 남깁니다.
- 출처 title+quotes는 출처별 합계 25단어 이하. community content의 제목·원문·댓글 인용도 합계 25단어 이하. 전문 복제 금지, URL만 연결. 독립된 ㅇㅎ/ㅎㅂ/ㅇㅎㅂ 표시는 원출처 제목까지 제외. 성적 유출물·노골적 성적 콘텐츠·미성년 성적 대상화·개인정보 노출·악성 루머 제외. safetyChecked/rightsChecked는 실제 사람/에이전트 검토 확인이며 자동 진위 판정이 아닙니다.
- 미확인 metric value는 null, 관측 자체가 없으면 observations=[]. 숫자 0은 실제 0일 때만. 기간은 두 끝을 모두 확인하거나 둘 다 null. 시각은 시간대가 필수이며 미래 관찰은 거부합니다.
- 같은 ID의 kind/topicKey/canonicalUrl/firstObservedAt은 바꿀 수 없습니다. 두 수집 경로를 통틀어 같은 topicKey나 같은 개별 원문에 새 ID를 부여하면 거부합니다. 새 매크로 항목은 최근 14개 기존 커뮤니티 회차의 topicKey·원문 URL과도 대조하여 재수집을 막습니다. 다음 창에서 다시 관찰할 때도 같은 ID와 다음 revision을 씁니다. 창이 바뀌면 과거 항목을 자동 복사하지 않습니다.

수집 상태 입력:

```json
{"schemaVersion":1,"operationId":"check-run-id","check":{"id":"check-id","channel":"topics","source":"실제 확인한 대상","status":"blocked","checkedAt":"실제 ISO 시각","count":null,"note":"차단·부분 확인·누락 범위"}}
```

channel=`community|topics|news`, status=`ok|empty|blocked|failed|partial`. `empty`는 실제 조건 충족 0건 확인(count=0), 차단/실패 미확인은 count=null. 예약이 아예 실행되지 않은 경우 성공·실패를 꾸며 기록하지 않습니다.

뉴스 준비 입력:

```json
{"schemaVersion":1,"operationId":"news-prepare-id","expectedRevision":0,"brief":{"기존 뉴스 schemaVersion 1 전체 초안":"이 위치의 설명을 실제 초안 전체로 교체"}}
```

기존 뉴스 publisher의 전체 검증을 통과해야 합니다. 준비본은 진행 중 ㄴㅇㅅ에서 보이고 기존 뉴스 회차·이슈 인덱스에는 아직 넣지 않습니다. 09/21 확정 트랜잭션에서 원래 cutoffAt/generatedAt을 유지하며 기존 회차·이슈 인덱스에도 함께 게시합니다. 이미 확정 경계를 지난 대상에 새 준비본을 소급 넣는 동작은 거부합니다. 늦은 뉴스는 실패/지연 기록을 남기고 다음 회차의 새 근거 또는 명시적 정정으로 다룹니다. `finalize`가 재시도되면 뉴스 이슈도 중복 작성하지 않습니다.

정정 입력:

```json
{"schemaVersion":1,"operationId":"correction-run-id","correction":{"id":"correction-id","snapshotId":"YYYY-MM-DD-am","itemId":"원래 항목 ID","action":"correction","reason":"정정 사유","text":"새로 확인한 정정 내용","verifiedAt":"실제 ISO 시각","sources":[],"safetyChecked":true,"rightsChecked":true}}
```

sources는 위와 동일한 검증 출처가 1개 이상 필요합니다. action=`correction|withdrawal`. 해당 확정본·항목이 존재해야 합니다. 원본을 변경하지 않고 별도 정정 파일을 추가하며 화면에 원문과 정정을 함께 표시합니다. 뉴스 사실 정정은 기존 `timeline.correctionOf` 규칙에 따라 다음 뉴스 회차에도 연결합니다.

## 파일 계약과 장애 복구

- `public/data/live/current.json`: schemaVersion=1, timezone, activatedAt, updatedAt, windows(활성+미확정 창), snapshots(불변 파일 경로·SHA-256), corrections, registry(안정된 ID·최신 revision), operations(재시도 판정). 동일 파일을 docs에 미러합니다.
- `data/live/snapshots/YYYY-MM-DD-am|pm.json`: 창 전체·items·checks·news 준비본·scheduledFor·finalizedAt. 한 번 생성하면 덮어쓰기 금지. JSON 정렬 직렬화의 SHA-256을 인덱스에 기록합니다.
- `data/live/events/<operationId>.json`: 요청·실제 적용 시각·결과를 보존하는 변경 이력. 수정 전 진행 중 내용도 이 기록에 남습니다.
- `data/live/corrections/<id>.json`: 원본과 별도의 불변 정정. current는 조회용 복사본을 포함합니다.
- 로컬 동시 실행은 Git 디렉터리의 flock으로 직렬화합니다. 모든 쓰기는 검증 후 pending journal에 먼저 기록하고, 불변 파일→인덱스 순서로 atomic replace합니다. 중단되면 다음 쓰기가 저널을 완성하거나 `python3 scripts/live/manage.py recover`로 복구합니다. 저널이 남아 있으면 dry-run은 복구 필요를 알립니다.
- --push는 임시 clone만 사용합니다. push가 거절되면 최신 main에서 같은 요청을 다시 적용합니다(최대 4회). 원격이 변경되지 않은 네트워크 실패면 중단하고 같은 operationId로 재시도합니다. force push·사용자 checkout reset·생성 JSON rebase는 하지 않습니다. 응답의 commit은 실제 게시된 커밋입니다.
- 코드 배포자는 빌드 직전에 최신 main을 다시 확인하고 public 데이터를 보존해야 합니다. prepare-pages.py가 새 public 데이터를 docs에 복사하므로, 오래된 빌드 결과로 다른 게시자의 데이터를 덮어쓰지 마십시오.

## 부모 클라우드 예약 변경

1. 애객 매크로 신규 확인 결과는 upsert(kind=community), 실패·빈 결과는 check. 로컬 수집기/LaunchAgent는 재활성화하지 않습니다.
2. 매시간 편집 조사는 upsert(kind=topic)·check. 실제 SNS 지역·기간 한계를 포함합니다.
3. 기존 08:30/20:30 뉴스 예약은 검색/검증 후 `stage-news --push`. 08:55/20:55에 ‘확정 완료’로 직접 게시하는 기존 publish.py 호출을 중단합니다.
4. 별도 09:00/21:00 KST 확정 예약은 대상 edition을 예약 시 고정해 `finalize --edition ... --push`. 재시도에서도 edition은 그대로 유지합니다. 자료가 없어도 실제 빈 기록을 확정할 수 있으나 운영 시작 이전 창은 만들지 않습니다.
5. 각 게시 후 Pages 실행 성공과 사이트 JSON commit/내용을 확인하고 실패·차단·지연·사용자 조치만 보고합니다. 정적 사이트 배포 완료 시각을 수집/확정 시각으로 대신 쓰지 않습니다.

## 검증

```sh
python3 -m unittest discover -s scripts/live -p 'test_*.py'
python3 -m unittest discover -s scripts/community -p 'test_*.py'
python3 -m unittest discover -s scripts/news -p 'test_*.py'
node --experimental-strip-types scripts/test-live.ts
npx tsc --noEmit --allowImportingTsExtensions
npm run lint
npm run build
python3 scripts/prepare-pages.py
```

테스트 데이터는 임시 저장소에서만 씁니다. 실서비스 데이터에 예시/가짜 항목을 넣지 않습니다.
