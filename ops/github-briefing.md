# ㄱㅎㅂ GitHub Trending 운영

사용자가 2026-11-17에 승인한 흐름: 매일 한국시간 오전 9시에 GitHub Trending 전체 언어·일간 1~10위를 수집하고, ChatGPT에서 분석한 답변을 Codex가 공식 자료와 대조해 이미지와 함께 Daily K에 게시한다. 9시는 조사 시작 시각이며 게시 완료 시각은 아니다. 이 자동화는 Mac과 ChatGPT 앱/로그인 세션이 필요하다. 유료 API로 임의 대체하지 않는다.

공개 주소: https://bacbaqui-web.github.io/daily-k/?tab=github

## 저장과 중복 방지

- 소스 원격: `https://github.com/bacbaqui-web/daily-k.git`, `main`, Pages `/docs`.
- 실행 시 깨끗한 체크아웃에서 `git fetch origin`, `git pull --ff-only`로 최신화한다. 로컬 미커밋 작업을 덮어쓰지 않는다. 필요하면 `~/Library/Application Support/DailyK/github/checkout-날짜`에 새 clone을 사용한다.
- 비공개 작업 자료: `~/Library/Application Support/DailyK/github/YYYY-MM-DD/`. 요청·원문 답변·검토 기록과 인증 자료는 공개 저장소에 넣지 않는다.
- 원격 `public/data/github/YYYY-MM-DD.json`과 공개 URL이 이미 정상인 경우 재요청·재발행하지 않는다. 발행 완료 여부가 불명확하면 Git/Pages를 먼저 대조한다.
- 회차 폴더의 `run.lock`을 배타적으로 만들고 작업 종료 시 해제한다. 기존 잠금이 있으면 실행 중인지 확인하고 중복 실행하지 않는다. `request.txt`와 `request-state.json`이 있으면 ChatGPT 응답부터 확인한다. 전송 여부가 불명확할 때 재전송하지 않는다.

## 수집과 ChatGPT 분석

1. `python3 scripts/github/collect.py --output '회차 폴더'`를 실행한다. 원본 HTML과 실제 수집 시각, 표시 순서, 오늘 증가한 별 개수가 `snapshot.json`에 저장된다. 정확히 10개가 확인되지 않으면 중단한다. 기존 snapshot은 재사용하고 순위를 별 개수로 재정렬하지 않는다.
2. 이 회차를 `[DailyK-GitHub:YYYY-MM-DD]`로 표시한 요청을 만든다. 아래 스키마와 수집한 순위·repo·starsToday를 포함한다. `request.txt`에 먼저 보관하고 `request-state.json`을 submitting으로 배타적 생성한다.
3. 전용 ChatGPT 대화 ID는 `~/Library/Application Support/DailyK/github/chatgpt.json`을 사용한다. send_message_to_thread/read_thread를 우선한다. 모델을 임의로 바꾸지 않는다. 대화가 실행 중이면 완료를 기다린다. 전송 뒤 sent 상태·실제 시각을 기록한다. 예약은 Codex가 담당하므로 ChatGPT에 예약을 만들지 말라고 명시한다.
4. 공식 README·문서를 실제로 확인하고 쉽게 설명하도록 요청한다. 순위 페이지 접근 실패 시 제공 스냅샷 사용을 명시하고 순위를 추측하지 않는다. 모든 10개를 포함하며 각 항목은 `rank, repo, title, summary, explanation(문단 배열), useCase, requirements(문자열), emphasis(본문에 실제 있는 핵심 문구 1~3개 배열), sources([{label,url}])`를 반환한다. 최상위는 `{date,intro,items}`이다. title에는 도구가 하는 일을 한글 15자 안팎으로 쓴다. 프로젝트 이름 옆에 표시하므로 이름을 반복하지 않는다. 예: AI 계획·코드 검토, 중국 역사 지도. 화면에는 이미지와 summary 한두 문장, requirements 한두 문장만 표시한다. 이미지 아래 공식 README 안내·캡션·출처 문구는 표시하지 않고 이미지 클릭으로 원본에 연결한다. summary는 ㄴㅇㅅ과 같은 간결한 존댓말로 핵심부터 쓴다. 무엇을 해주는지 일상말로 구체적인 1~2문장, 가급적 40~90자로, requirements는 꼭 필요한 설치·비용·이용 제한만 120자 안팎으로 쓴다. 제목과 긴 본문을 반복하지 않는다. explanation과 useCase는 검토용 자료로 보관하며 화면에 표시하지 않는다. 설치·계정·모델/API·상용 기능의 실제 조건을 구분한다. 직접 실행한 것처럼 쓰거나 상승 원인을 지어내지 않는다.
5. 해당 회차 사용자 메시지 뒤 완성된 답변을 확인한다. 도구 성공만으로 응답 완료를 간주하지 않는다. read_thread가 오래된 상태이면 CUA 브라우저에서 새 메시지를 읽기 전용으로 확인한다. 60초 이하의 확인 간격을 사용하되 바쁜 반복 조회를 피한다. 45분이 지나도 미완료면 pending 기록을 남겨 다음 실행에서 이어간다.
6. 실제 원문을 `chatgpt-response.txt`에 보존하고 `analysis.json`으로 변환한다. 수치·조건의 오류만 공식 출처로 수정하며 수정 이유를 검토 파일에 남긴다. 답변이 없을 때 Codex 자체 분석을 ChatGPT 분석으로 바꿔 게시하지 않는다.

## 이미지와 검토

- 공식 README의 화면·설명 그림을 우선한다. 없으면 실제 저장소 `og:image`를 사용하며 '저장소 소개 이미지 · 실제 사용 화면은 아닙니다'라고 표시한다. 주소를 추측하거나 AI로 가짜 사용 화면을 만들지 않는다.
- 이미지 파일은 비공개 회차의 `images/`에 내려받아 직접 확인한다. SVG는 정상적인 렌더러로 PNG로 변환하고 내용이 잘리지 않았는지 확인한다. 큰 이미지는 읽을 수 있는 크기로 최적화한다. 이미지 출처와 대체 텍스트를 남긴다.
- `images.json`은 순위순 10개 배열: `{repo,file,sourceUrl,alt,caption,sha256}`. 파일명은 안전한 png/jpg/webp 이름이다. sha256은 최종 파일 기준이다.
- 모든 공식 출처를 직접 열어 기능·필수 조건·유료 영역을 대조한다. 확인 못한 사항은 본문에서 미확인으로 표시하고 확인했다고 기록하지 않는다.
- `review.json`: `date, approved:true, responseComplete:true, conversationUrl, verifiedAt, snapshotSha256, analysisSha256, imagesSha256, responseSha256, items:[{repo,factsChecked:true,imageChecked:true,notes}]`. 해시는 해당 파일 바이트 기준이다. 실제 확인 후에만 true를 쓴다.

## 발행과 확인

1. `python3 scripts/github/publish.py --state '회차 폴더' --check`로 검증한다. 이 명령은 쓰기나 operation ID 소모를 하지 않는다.
2. 같은 파일로 `--check` 없이 실행한다. `public/data/github/`와 `docs/data/github/`의 날짜별 JSON·이미지·인덱스만 갱신한다. 이전 날짜를 지우지 않는다. 동일 날짜의 다른 내용은 덮어쓰기하지 않는다.
3. `node --experimental-strip-types scripts/test-github.ts`와 필요한 검사를 실행한다. 데이터만 바뀌었으면 프런트를 재빌드하지 않는다. 코드 변경 때만 `npm run build`, `npx astryx doctor --built dist/client`, `python3 scripts/prepare-pages.py`를 실행한다.
4. 해당 GitHub 데이터만 커밋·push한다. 원격이 앞서면 fetch/rebase 후 기존 새 회차와 인덱스를 보존해 합친다. force push는 하지 않는다. 기존 뉴스/유머/만화 데이터와 예약은 변경하지 않는다.
5. Pages 배포 완료와 공개 JSON, 이미지 10개, 실제 ㄱㅎㅂ 화면의 순서·본문을 확인한다. 실패하면 기존 발행본을 유지하고 원인을 보고한다. `delivery.json`에 커밋·공개 URL·확인 시각·검증 결과를 기록한다.
6. 이 요청은 Daily K 웹페이지 게시이다. Discord나 다른 외부 채널에 보내지 않는다. 완료/실패와 확인한 범위를 짧게 보고한다.

## 화면과 문체

- ㄱㅎㅂ은 뉴스의 글자 크기와 간결한 문체를 유지하되 주황 계열 메인 색상으로 구분한다. 대표 이미지 → 프로젝트 이름과 한글 제목 → 설명 순서로 표시한다. 이미지는 잘리지 않게 원래 비율을 유지한다.
- ChatGPT는 summary·requirements에 실제 들어 있는 핵심 문구 1~3개를 emphasis 배열로 함께 반환한다. 문장 전체를 강조하지 않는다. 화면에서는 이 문구만 굵게 표시하고 원문은 바꾸지 않는다.
- 제목은 프로젝트 이름과 짧은 한글 용도를 함께 표시한다. 본문은 무엇을 해주는지부터 짧고 쉬운 존댓말로 설명한다. 같은 기능을 소개와 사용 예시에서 반복하지 않는다. 중요한 조건·비용·미확인 사항은 줄이는 과정에서 지우거나 바꾸지 않는다.
- ChatGPT가 최종 문구를 작성한다. Codex는 가져와 검토·게시하며, 문체 수정이 필요하면 ChatGPT에 요청한다.

## 비개발자도 이해하는 설명 기준

- 제목은 무엇을 하는 도구인지 일상말로 쓴다. ‘업무 기능 확장’, ‘개발 도구’처럼 추상적인 이름으로 끝내지 않는다.
- summary는 비개발자가 첫 문장만 읽어도 용도를 알 수 있게 쓴다. 무엇을 넣거나 시키면 어떤 결과를 얻는지 일상말로 설명하고, 필요하면 실제 쓰임 하나를 덧붙인다. 40~90자 정도의 짧은 1~2문장을 우선하며 길이를 채우려고 늘리지 않는다.
- 에이전트·프로토콜·런타임·의존성·MCP·CLI·컨테이너 같은 용어만으로 설명하지 않는다. 꼭 필요하면 쉬운 뜻을 함께 쓴다.
- requirements도 쉬운 존댓말로 쓰되 설치·계정·비용·개발 필요 여부·운영체제 제한을 빠뜨리지 않는다. 설치만 하면 모든 작업이 자동으로 된다는 인상을 주지 않는다.
- 복사되는 explanation·useCase에도 같은 문체를 적용한다. 단순화하면서 기능을 과장하거나 새 사실을 추가하지 않는다.
- ‘효율화·구성·활용·지원’ 같은 추상적인 말만으로 끝내지 않는다. 예: ‘웹사이트 주소를 넣으면 여러 페이지의 글을 한꺼번에 모아 줍니다.’ 사용자가 직접 쓰는 앱인지, AI에 추가하는 지침인지, 개발자가 연결해야 하는 코드인지 구분한다.
- ChatGPT가 이 기준으로 최종 문구를 작성하고, Codex는 기존 자료와 대조한 뒤 게시한다.
