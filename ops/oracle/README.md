# Oracle 뉴스 발행: Codex 구독 로그인

2026-10-18 사용자 요청: Mac/Codex 앱이 꺼져 있어도 오라클에서 한국 시간
09:00·21:00에 뉴스 조사, 검증, GitHub Pages 게시, 청소로봇 전송까지 실행.
기존 문서의 Oracle 변경 금지/로컬 예약 유지 제한은 이번 뉴스 이전에 한해 대체한다.
유머 수집은 변경하지 않는다.

## 실행 경로

- 서버 저장소 `/home/ubuntu/daily-k-news/repo`, 저장소 전용 쓰기 deploy key.
- Codex CLI `/home/ubuntu/daily-k-news/codex-cli/node_modules/.bin/codex` (0.163.0).
- ChatGPT 구독 계정으로 기기 인증. `codex login status`가 ChatGPT가 아니면 실행 거부.
- API 키 환경변수를 제거하고 `forced_login_method="chatgpt"`로 API 과금 대체를 막는다.
- `oracle_runner.py` → `codex_subscription.py` → 실제 웹 조사/JSON 작성/별도 검토 →
  기존 validator → `manage.py publish-news --push` → 공개 JSON/Discord 발행 기록 확인.
- Codex는 읽기 전용, shell/apps/multi_agent 비활성으로 뉴스 데이터만 생성한다.
  Git 게시와 Discord 전송은 기존 코드가 처리한다.
- 실행 자료/시도/검토 기록은 `/home/ubuntu/daily-k-news/state/<회차>/`에 비공개 저장한다.

## 이전 상태

2026-10-18 기기 인증, 실제 구독 웹 검색, 서버 예약 환경의 로그인 확인을 완료했다.
뉴스 조사 → 초안 → 출처/중복 검증 → 최종 검토의 실제 시험이 통과했다
(대표 6건, 총 8건, 일정 3건). 시험본은 별도 보관했으며 오늘 기존 회차를 덮어쓰거나 재전송하지 않았다.
기존 공개 뉴스 JSON과 Discord 발행 영수증도 서버에서 확인했다. 자동 테스트 55개 통과.
`daily-k-news.timer`는 enabled/active이며 첫 정기 실행은 2026-10-19 09:00 KST다.
기존 로컬 `automation-2`는 앱에서 존재하지 않는다고 응답했고 로컬 자동화 목록에서도 없었다.
따라서 로컬 예약을 새로 만들지 않았으며 서버 뉴스 타이머만 운영한다.
구독 한도나 품질 검사 실패 시 게시를 건너뛰며, 성공을 보장하는 고정시각 게시 서비스는 아니다.

## 운영

- `systemctl list-timers daily-k-news.timer` 및 `journalctl -u daily-k-news.service` 확인.
- Asia/Seoul 시간대 사용. 서버 재부팅 시 지난 회차를 몰아 발행하지 않는다.
- 시작할 때 대상 회차를 고정하고 같은 회차가 있으면 재게시하지 않는다.
- 실패한 시도는 자동으로 반복하지 않는다. 원인 확인 후 저장된 입력으로 재개한다.
- push 후 Pages/Discord 확인 실패 시 새 회차/중복 메시지를 만들지 않는다.
- 구독 한도 소진, 인증 해제, 인터넷 장애, 품질 검증 실패 시 게시가 멈출 수 있다.
- 로그인 갱신: 위 CLI 경로의 `login --device-auth`. 인증정보를 Git이나 로그에 넣지 않는다.
- AI 검토는 사람의 사실 확인을 완전히 대체하지 않는다. 원래 발행 기록을 조용히 수정하지 않는다.
