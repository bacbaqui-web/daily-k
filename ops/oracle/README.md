# Oracle 뉴스 발행 이전 준비

2026-10-18 사용자 요청: Mac/Codex 없이 오라클에서 한국 시간 09:00·21:00에
뉴스 조사, 검증, GitHub Pages 게시, 기존 청소로봇 전송까지 실행.
이 요청은 기존 문서의 Oracle 변경 금지/로컬 예약 유지 제한을 이번 뉴스 이전에 한해 대체한다.
유머 수집은 변경하지 않는다.

## 현재 상태

- 서버 저장소 `/home/ubuntu/daily-k-news/repo`, 저장소 전용 쓰기 deploy key.
- `scripts/news/oracle_runner.py`: OpenAI Responses 웹 검색 → 독립 JSON 작성 →
  기존 발행 검증 → 별도 AI 검토 → `manage.py publish-news --push` → 공개 JSON 및 봇 발행 기록 확인.
- systemd 파일은 준비본이며 **예약 비활성**. OpenAI 키가 없고 실제 AI/게시 통합 시험 전이다.
- 기존 Mac 예약은 정상 이전 확인 전까지 유지한다. 두 예약을 동시에 활성화하지 않는다.

## 활성화 전 필수 확인

1. 서버 `/home/ubuntu/daily-k-news/news.env`에 `OPENAI_API_KEY`와
   `OPENAI_NEWS_MODEL=gpt-5.4-mini`를 등록한다. 소유자 ubuntu, 권한 600.
   API 키는 Git, 대화, 로그에 넣지 않는다. API 사용료는 별도다.
2. `--check-config`는 키 존재 검사만 한다. API 정상 동작 판정으로 쓰지 않는다.
3. 실제 09/21 회차에 `--prepare-only`로 검색/선정/출처/요약 품질 및 검증을 시험한다.
   시험한 회차의 `publication.json`으로 기존 `manage.py ... --push`를 실행해
   Pages 및 Discord 발행을 확인한다. 이미 발행된 회차로 시험하지 않는다.
4. Codex의 기존 `automation-2`를 도구로 PAUSED로 변경하고 나서 서버 timer를 enable/start한다.
   이 절차가 끝나기 전에는 완전 자동화 완료로 보고하지 않는다.

## 운영

- `journalctl -u daily-k-news.service` / `/home/ubuntu/daily-k-news/state/<회차>/` 확인.
- 호스트 UTC와 무관하게 Asia/Seoul 달력 사용. 재부팅 시 지난 회차 몰아 발행하지 않는다.
- 중복 회차, 비정상 AI 결과, 출처 URL 미일치, 내용/시간/중복 검증 실패 시 게시하지 않는다.
- 실행 시도 기록이 있으면 자동으로 AI를 재호출하지 않는다. 실패 근거를 검토한 뒤 재시도한다.
- 이미 push한 뒤 Pages/Discord 확인에 실패하면 새 회차 생성/재전송 금지.
- AI 결과는 명령어가 아닌 JSON 데이터로만 처리한다. 외부 페이지의 지시는 따르지 않는다.
- AI 검토는 사람의 사실 확인을 완전히 대체하지 않는다. 오류 시 기존 회차를 조용히 수정하지 않는다.
- 키 미등록 상태에서 timer를 켜지 않는다. 실패를 성공으로 표시하거나 기준을 완화하지 않는다.
