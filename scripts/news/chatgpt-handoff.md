# ChatGPT 뉴스 운영

2026-11-16 전환. 다음 회차부터 ChatGPT 앱에서 조사·초안을 받고 Codex는 출처·중복 검사와 기존 발행기 연결을 담당한다. API 유료 호출로 대체하지 않는다.

## 실행 구조

- Oracle daily-k-news.timer의 09:00/21:00 KST 일정은 유지한다.
- 서비스의 chatgpt-handoff.conf에서 실행 명령만 web_handoff.py --queue로 바꾼다. 기존 조사기는 호출하지 않는다.
- Mac Codex automation-2가 실제 요청/수신/검증/전달을 수행한다. Mac과 앱이 실행 가능하고 ChatGPT 세션이 유효해야 한다. 서버 단독으로 ChatGPT 웹을 제어하지 않는다.
- 로그인/도구 오류, 응답 지연, 검증 실패는 해당 회차 상태에 기록한다. 다른 방식으로 몰래 생성하거나 검증을 생략하지 않는다. 기존 게시 결과는 보존한다.

## 요청·수신

1. 원격 Git과 실서비스 회차 JSON, delivery.json, Discord news-sent.json을 먼저 대조한다. 이미 발행한 회차는 요청하지 않는다. 다른 작업이 run.lock을 잡았으면 기다린다.
2. `state/ID/awaiting-chatgpt.json`의 cutoffAt을 고정한다. 없으면 회차 ID의 09:00 또는 21:00 KST를 사용한다. 생성/검증 시각은 실제 시각이다.
3. `scripts/news/chatgpt-news-prompt.txt`의 문구를 바꾸지 않는다. 앞에만 기준 날짜·오전/오후·KST cutoff 및 실제 웹 검색, 예약 생성 금지를 명시한다. 회차 식별자 `[DailyK:YYYY-MM-DD-am|pm]`를 넣는다.
4. ChatGPT 대화 `6afa77d2-bbfc-83e8-a46a-c0c438bfe58b`를 사용한다. 앱의 send_message_to_thread/read_thread를 우선한다. 모델은 임의 변경하지 않는다. 브라우저 세션 쿠키나 비밀번호를 파일에 저장하지 않는다.
5. 보내기 전에 원격 회차 폴더에 chatgpt-request.json(회차, cutoff, 요청문, conversationUrl, status=submitting, startedAt)을 배타적 생성한다. 이미 있으면 대화를 먼저 확인한다. 전송 뒤 sent 상태와 실제 시각을 기록한다. 도구 성공 응답만으로 답변 완료라고 판단하지 않는다. 회차 표식이 붙은 새 사용자 메시지와 그 뒤 완성된 답변이 필요하다.
6. 상태 조회가 오래된 답변을 돌려주면 ChatGPT UI에서 읽기 전용으로 새 메시지를 확인한다. 전송 여부 불명확하면 재전송하지 않는다. 60초 이하 간격, 최대 45분 기다리고 pending이면 다음 실행에서 이어간다.
7. 원문 답변과 출처 링크를 chatgpt-response.txt에 보존한다. 질문별 요청 상태로 중복 요청을 방지한다.

## 검증과 변환

- 원문 링크를 열어 보도 시각, 사건 발생 시각, 핵심 사실과 수치를 직접 확인한다. 검색 요약이나 ChatGPT 주장만으로 통과시키지 않는다.
- 최근 7일의 대표 기사와 예비·추가 기사까지 topicKey와 사건의 실제 내용으로 비교한다. 새 사실 없는 반복은 제외하고, 후속은 새 사실과 이전 회차 관계를 기록한다.
- 요청문은 그대로 사용하지만 검증에서 탈락한 기사를 수량이나 분야를 맞추려고 되살리지 않는다. 빈자리를 억지로 채우지 않는다.
- public/data/news의 최근 정상 JSON과 publish.py의 현재 schema를 기준으로 publication.json을 만든다. 기존 원고의 형식만 바꾸어 새 조사로 취급하지 않는다. 근거 없는 문단·수치·시각을 채우지 않는다.
- operationId는 `publish-news-ID`, cutoffAt은 원래 정각, generatedAt은 실제 변환 시각이다. source verifiedAt도 실제 검증 시각이다.
- 전체 원격 history는 oracle_runner.histories(ID)[0]으로 읽는다. `web_handoff.digest(payload)`와 `digest(history)`를 검토 기록에 넣는다.
- 검토 파일 필수: edition, approved=true, payloadSha256, historySha256, conversationUrl, responseCompletedAt, verifiedAt, factsChecked=true, publicationDatesChecked=true, eventDatesChecked=true, priorLeadAndReserveChecked=true, sources=[{url,accessible:true,factsSupported:true, 근거 메모}]. 확인한 경우에만 true를 쓴다. 탈락 사유와 출처별 검증 내용도 남긴다.

## 발행

파일은 repo 밖 `state/ID/`에 candidate-publication.json, candidate-review.json으로 저장한다. 기존 publication.json과 승인 초안을 덮어쓰지 않는다.

서비스와 동일한 Git 환경에서 다음을 실행한다:

```
cd /home/ubuntu/daily-k-news/repo
export GIT_SSH_COMMAND='ssh -i /home/ubuntu/.ssh/daily-k-news-deploy -o IdentitiesOnly=yes -o BatchMode=yes'
export GIT_AUTHOR_NAME=DailyK-News GIT_AUTHOR_EMAIL=news@daily-k.invalid
export GIT_COMMITTER_NAME=DailyK-News GIT_COMMITTER_EMAIL=news@daily-k.invalid
python3 scripts/news/web_handoff.py --payload /home/ubuntu/daily-k-news/state/ID/candidate-publication.json --review /home/ubuntu/daily-k-news/state/ID/candidate-review.json
# 위 검사가 통과한 동일 파일만 --push로 실행
```

기존 publish-news --check/--push, 잠금, operationId, Git 트랜잭션, Discord 중복 방지는 그대로 쓴다. 게시 후 기존 verify_delivery는 Pages 내용·목록과 봇 영수증을 확인한다. Codex가 마지막으로 Discord 실제 메시지도 조회해 회차 표식을 확인한다. 원문 전체 로그나 인증값은 출력하지 않는다.

기존 publication.json/publish-result.json이 있으면 bridge가 재발행을 거부한다. remote Git, public JSON, 트랜잭션, Discord 영수증·실제 메시지를 대조한 뒤 기존 복구 경로로 미완료 단계만 이어간다. 홈페이지가 있으면 재생성하지 않는다. 홈페이지 전용 회차는 Discord에 보내지 않는다.

## 운영 범위·되돌리기

앱 메시지 도구의 전송과 웹 화면의 응답을 2026-11-16에 확인했다. 이것은 서버 무인 브라우저 운용이나 향후 세션·예약 성공을 보장하지 않는다. 웹 UI의 자동 추출을 별도 크롤러로 구현하지 않는다. ChatGPT 약관의 자동 추출 제한과 모델별 한도는 별도이며 API 요금과 혼동하지 않는다.

전환 전 실행 명령은 /usr/bin/python3 scripts/news/oracle_runner.py. 되돌릴 때는 이 서비스의 chatgpt-handoff.conf만 제거하고 daemon-reload하며 automation-2도 이전 확인 전용 역할로 되돌려 경쟁 실행을 막는다. 다른 서비스·타이머를 변경하지 않는다.
