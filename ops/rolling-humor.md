# 최근 24시간 유머 / 뉴스 회차 계약

이 문서가 ㅋㅋㅋ 운영의 우선 지침입니다. 유머는 **애객 고유 댓글에 실제로 들어 있는 literal `ㅋ`(U+314B) 합계 10개 이상**입니다. `ᄏ`, `크`, 제목의 ㅋ, 외부 사이트의 댓글 수는 더하지 않습니다. 이전 11개 기준·시간별 문화/SNS 화제 선정·AI가 글마다 브라우저를 여는 감독형 수집 경로는 새 유머 운영에 사용하지 않습니다. 기존 cloud-collector 코드는 과거 재현용이며 일반 프로그램이라고 부르지 않습니다.

## 표시 및 시간

- ㅋㅋㅋ에는 날짜·오전/오후·확정 선택이 없습니다. `data/humor/current.json`의 검증된 유머만 최신 게시 순으로 표시합니다. 일반 topic·SNS·뉴스를 합치지 않습니다.
- `publishedAt`은 의미까지 검증한 **애객 게시 시각**입니다. 애객 이전 원 호스트의 최초 작성 시각과 구분합니다. `publicationEvidence`에 실제 URL·원시 값·관찰 시각·방법·게시 시각이라는 의미의 확인을 남깁니다. 목록의 ‘몇 시간 전’, 재노출 시각, 첫 발견 시각은 대신 사용할 수 없습니다.
- 유효 범위는 `publishedAt <= now < publishedAt + 24h`입니다. 정확히 24시간에 제거합니다. `expiresAt`은 CLI가 계산하고 입력받지 않습니다. 동일 ID의 게시 시각·첫 발견 시각은 불변입니다. 재수집·재노출·수정으로 수명을 연장하지 않습니다.
- 시각 불명확·필드 의미 미확인·댓글 불완전·시각 변경은 보류합니다. 기존 공개 유머 2건은 출처 `publishedAt=null`이므로 자동 이전하지 않습니다. 원본 JSON과 이력은 그대로 보존합니다.
- 페이지는 1초 간격 및 focus/pageshow/visibilitychange에서 현재 시각을 다시 계산합니다. 배포나 수집기가 멈춰도 오래된 JSON의 만료 항목을 표시하지 않습니다. 원격 목록 갱신은 60초마다 확인합니다. 브라우저 시계 기준이며 서버 실행을 보장하는 기능이 아닙니다.

## 파일과 검증 가능한 명령

Python 3.11 이상, 표준 라이브러리·Git. 입력 스키마는 `schemas/rolling-humor-input.schema.json`, 공개 상태는 `schemas/rolling-humor.schema.json`. 의미 검증의 최종 기준은 `scripts/humor/manage.py`입니다.

```sh
python3 scripts/humor/manage.py status
python3 scripts/humor/manage.py upsert /absolute/verified-humor.json --check
python3 scripts/humor/manage.py upsert /absolute/verified-humor.json --push
python3 scripts/humor/manage.py check /absolute/collector-status.json --push
python3 scripts/humor/manage.py expire --operation-id expire-UNIQUE-RUN-ID --check
python3 scripts/humor/manage.py expire --operation-id expire-UNIQUE-RUN-ID --push
python3 scripts/humor/manage.py recover
```

`operationId`는 소문자·숫자·하이픈의 안정된 요청 ID입니다. 같은 실행 재시도는 같은 ID/동일 입력, 다음 실행은 새 ID를 사용합니다. ID는 `aagag-<idx 숫자>`이고 `_rev` 차이는 같은 글입니다. 최초 `expectedRevision=0`, 수정은 최신 `registry[id].revision`을 사용합니다. `--check`는 공개 파일을 쓰지 않습니다. `--push`는 격리 clone에서 최신 main에 의도를 재적용하고 fast-forward push만 합니다. 강제 push·사용자 checkout reset을 하지 않습니다. UI 코드를 먼저 배포한 후 사용합니다.

입력은 `{schemaVersion:1, operationId, items:[...]}`이며 각 항목에는 `id`, `canonicalUrl`, `title`, `publishedAt`, `firstObservedAt`, `lastVerifiedAt`, `expectedRevision`, `publicationEvidence`, `nativeComments`, `review`, `sources`, `content`, `limitations`가 필요합니다.

- `publicationEvidence`: `method=aagag-otime|aagag-explicit-publication`, `sourceUrl`, `value`(publishedAt과 동일), `raw`, `observedAt`, `semanticsVerified=true`. `aagag-otime`의 raw epoch 값도 비교합니다. 검증하지 않고 true로 바꾸지 않습니다.
- `nativeComments`: `scope=native-aagag-all`, `sourceUrl`, `observedAt`, `complete=true`, `reportedCount`, `rows:[{id,literalKCount}]`. native ID로 중복 제거 후 보고 총수와 일치해야 합니다. 동일 ID의 상충된 수치·부분 응답·외부 댓글·미확인은 거부합니다. 원문 댓글 전문은 받지 않습니다. 공개 상태에는 집계와 근거 해시만 보관합니다.
- `review`: `safetyChecked`, `rightsChecked`, `verifiedAt`, `note`. 제목 키워드 필터만으로 맥락·이미지·영상 검토를 했다고 기록할 수 없습니다. 수집 프로그램은 이 확인을 자동으로 만들어내지 않습니다. 이 과정에 AI 호출은 포함하지 않으며 확인이 없으면 게시 보류입니다.
- `sources`: 원문 URL·제목·확인 시각, 게시 시각 미확인은 null. 출처별 제목+인용 합계 25단어 이하. 애객 제목·본문·댓글 인용도 한 예산으로 검사합니다.
- `content`: 기존 단일 imageUrl/videoUrl/videoPosterUrl 및 순서 있는 bodyImages 메타데이터 호환. 본문 이미지에는 원본 URL·양수 크기·확인 출처/시각이 필요합니다. 공개 URL만 연결하고 파일은 복제하지 않습니다. 전문·실행 HTML·추정 URL을 게시하지 않습니다. ㅇㅎ/ㅎㅂ/ㅇㅎㅂ, 성적·폭력·개인 비방 등 기존 제외 기준을 유지합니다.
- 수집 상태 입력은 `{schemaVersion:1,operationId,check:{status,checkedAt,count,note}}`. status는 `ok|empty|partial|blocked|challenge|failed|stopped`. 차단/실패/중단은 count=null이며 0건 수집으로 보고하지 않습니다.

`public/data/humor/current.json`과 `docs/data/humor/current.json`은 동일합니다. `events/<operationId>.json`은 과거 활성 자료·만료를 보존하는 불변 이벤트입니다. 로컬 flock + 원자 교체 + 복구 저널을 사용합니다. 만료는 활성 목록 제거이며 legacy community/live snapshot/news/이슈 JSON을 삭제하지 않습니다. 프로그램이 멈추면 서버 JSON의 물리적 만료 정리는 다음 `expire` 실행까지 늦을 수 있지만 브라우저의 표시 만료는 독립적으로 적용됩니다.

## 일반 프로그램: 개발 완료 범위와 실행 한계

기존 Mac `수집기/collector/aagag.py`와 `collect.py`의 익명 HTTP 목록·본문·댓글 API 경로를 조사했습니다. 기존 코드는 NFKC 계수·24시간 경계 포함·별도 retention 정책 등이 섞여 있으므로 그대로 재가동하지 않았습니다. 새 `scripts/humor/collector.py`는 Python 표준 라이브러리만 사용하는 **유한 1회 실행 프로그램**입니다. 목록과 발견된 다음 페이지, native 댓글, literal 계수, ID 중복, 체크포인트/복구, 만료 후보 정리를 수행합니다. AI·CUA·브라우저 호출은 없습니다.

승인된 실행환경에서 접근 허용 상태를 확인한 뒤 실행할 명령:

```sh
python3 scripts/humor/collector.py --state /PERSISTENT_PRIVATE_PATH/aagag.json --max-pages 20 --max-posts 100 --delay 5
```

정상 페이지 링크만 따라가며 한 호출은 제한량에서 `partial`로 끝납니다. 같은 state로 다음 호출이 미처리 큐를 이어갑니다. 오류/중단도 큐를 보존합니다. `complete`는 해당 탐색 종료일 뿐 전 사이트 누락 없음이나 게시 검증 완료를 뜻하지 않습니다. 오래된 관측 증거를 남기면서 activeCandidateIds는 만료시킵니다. 수집 결과는 private state에만 쓰며 사이트에 게시하지 않습니다.

401/403/429·명시적 challenge·robots 거절에서 즉시 멈추고 URL/HTTP 상태/시각/사유를 저장합니다. CAPTCHA를 풀거나 우회하지 않습니다. 기존 차단을 HTTP·새 IP·새 브라우저로 우회해서는 안 됩니다. 사용자가 기존 접근 경로에서 허용된 방식으로 문제를 해결하고 이를 확인한 뒤에만 `--resume-after-review`로 명시적 1회 재개를 허용합니다. 이 옵션 자체는 CAPTCHA 해결이나 접근 허가의 증거가 아닙니다.

**현재 검증 수준:** 네트워크 수집은 실행하지 않았고 fixture 기반 오프라인 테스트만 수행했습니다. `AAGAG_AA.otime`은 기존 파서가 사용한 정확한 epoch 필드이지만 지금의 게시/재노출 의미를 새 운영에서 실증하지 않았습니다. 따라서 수집기는 `semanticsVerified=false`, `publication_field_semantics_unverified`로 보류합니다. 이미지 URL·본문 스크립트/임베드의 메타데이터와 맥락/권리 검토도 자동으로 완료 처리하지 않습니다. 이 확인 없이 후보를 공개 입력으로 변환하지 않습니다. 수집/계수에 매 글 AI가 필요한 구조는 제거했지만, 안전 검토까지 무인 게시가 완료됐다고 주장하지 않습니다.

현재 GitHub Pages는 정적 파일 호스팅으로 이 프로그램을 실행하지 않습니다. 기존 cloud-collector는 AI 도구 실행 세션에 종속되며 지속 Python 호스트가 아닙니다. Mac은 개발·테스트만 했고 서비스·예약·수집기·자격증명·새 서버를 설치하거나 재가동하지 않았습니다. Mac 없이 상시 운영하려면 **기존 권한 내에서 사용 가능한 지속 클라우드 Python 실행환경, private 체크포인트 디스크, 허용된 애객 접근, 기존 Git 게시 인증**이 확인돼야 합니다. 그 환경이 아직 확인되지 않았으므로 상시 클라우드 수집은 미가동입니다. 새 서버/인증/API/유료 서비스나 GitHub 예약 workflow를 임의 생성하지 않습니다.

## 뉴스 예약: 09/21 단일 조사·발행

뉴스는 [news-single-run.md](news-single-run.md)의 계약을 따릅니다. 2026-10-11 오전부터 09:00/21:00에 한 번 조사·검증·작성한 봉투 입력을 아래 명령으로 최종 게시합니다. 08:30/20:30 준비와 별도 finalize-news 예약은 사용하지 않습니다. 과거 cutoff와 확정 원본은 보존합니다.

```sh
python3 scripts/live/manage.py publish-news /absolute/final-news.json --check
python3 scripts/live/manage.py publish-news /absolute/final-news.json --push
```

유머 경로·기록은 뉴스 발행과 독립입니다. 홈페이지 코드 배포와 수집기 가동도 별개이며, 수집 확인 기록이 없으면 가동 중이라고 표시하지 않습니다. 수집기나 예약 설정 변경은 별도 작업의 권한과 범위를 따릅니다.
