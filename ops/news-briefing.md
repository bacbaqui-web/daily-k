# ㄴㅇㅅ 운영 지침

이 기능은 GitHub Pages에 발행하는 한국어 뉴스 브리핑입니다. 유머 수집기와 완전히 별도로 작동합니다.

## 실행 환경과 일정

- 저장소: `/Users/bacbaqui/Library/Application Support/DailyK/runtime/daily-k-github`
- Python: `/Users/bacbaqui/Library/Application Support/DailyK/runtime/venv/bin/python`
- 초안·후보 기록: `/Users/bacbaqui/Library/Application Support/DailyK/news/`
- 사이트: https://bacbaqui-web.github.io/daily-k/?tab=news
- Codex 채팅 자동화가 Asia/Seoul 매일 09:00, 21:00에 이 지침을 수행합니다. 로컬 Mac과 Codex 앱이 켜져 있고 네트워크 및 GitHub 인증이 유효해야 합니다. 예약 시각은 생성 시작 시각이며 검색·검증·Pages 배포 시간이 추가됩니다.
- 시각은 매번 현재 시각을 확인해 KST로 계산합니다. 09:00~20:59 실행은 당일 am, 21:00 이후는 당일 pm, 00:00~08:59의 지연 실행은 전날 pm입니다. 지나간 여러 회차를 한꺼번에 자동으로 채우지 않습니다.
- 유머 수집은 사용자가 중지했습니다. `monitor-paused.json`, launchd, Oracle, 기존 수집 자동화, feed.json, monitor.json을 변경하거나 재시작하지 마십시오.

## 매 회차 절차

1. git 상태와 현재 시각을 확인합니다. 작업이 남아 있다면 임의로 덮어쓰거나 전체를 커밋하지 않습니다. 깨끗한 저장소에서 `git pull --ff-only` 후 `public/data/news/index.json`과 최근 7일 회차 JSON을 읽습니다. 같은 ID 회차가 이미 있으면 실서비스 JSON까지 확인한 뒤 중복 생성하지 않습니다. 이전 push 실패로 로컬 커밋만 남았으면 그 뉴스 커밋만 검토해 전송을 재개합니다.
2. **반드시 매번 최신 웹 검색**을 합니다. 오전: 당일 00~09시, 전날 18~24시, 부족한 경우에만 전날 낮 순. 저녁: 당일 12~21시 및 아침 이후 새 결과·수치·공식입장이 확인된 후속 순. 오전 기사와 똑같은 사건·문구를 다시 요약하지 않습니다. 발행 시각과 실제 사건 시각을 각각 확인합니다. 기사 수정 시각이 기준 이후라면 기준 이전에 알려진 내용만 다른 출처로 확인해 사용합니다.
3. 국내 정치/정책·사회, 국제/외교/안보, 경제, 증시/환율/금리, 반도체, 기술/IT/AI, 웹툰 산업 후보를 넓게 검색합니다. 10~20개 후보를 찾아 분야 균형을 검토해 **5~10개**를 선택합니다. 없는 분야는 억지로 채우지 않습니다. 웹툰 산업은 **반드시 하나 이상**: 당일 소식이 부족하면 최근 72시간의 플랫폼·작가·IP·해외진출·정책·불법유통·영상/게임화·공모전·창작자 지원 중 가치 있는 뉴스를 고르고 fallbackNote에 최근 중요 업데이트임을 밝힙니다. 이미 다룬 동일 보도는 다른 웹툰 후보로 대체합니다. 적합한 기사 자체가 없으면 꾸며내지 말고 발행 실패로 보고합니다.
4. 공식 발표 > 주요 통신사 > 주요 종합지/경제지/방송사 > 전문매체 순으로 우선합니다. 각 뉴스는 확인 가능한 한국어 기사 링크 1개 이상 필수입니다. 실제 기사 내용을 열어 확인하고, 접근이 안 되면 다른 매체 원문으로 대조합니다. 검색 결과에만 근거한 경우 내부 후보 메모에 확인 범위를 남깁니다. 단독·익명 주장·외신 인용은 추가 독립 출처를 찾고, 같은 원보도 재전송은 독립 확인으로 간주하지 않습니다. 확인되지 않은 주장은 확정 사실로 쓰지 않습니다. 출처를 합성하거나 URL/발행시각을 추측하지 않습니다. 기사 전문·사진은 복제하지 않고 독자적인 짧은 요약과 원문 링크만 저장합니다.
5. 후보별 0~100점: 최신성 40%, 중요도 25%, 사용자 관심 15%, 국내 파급 10%, 신뢰도 10%. AI/IT/반도체/개발도구, 경제/증시/환율, 국내 웹툰/IP/플랫폼에 관심 가중치를 높입니다. 최신성은 `scripts/news/rank.py`가 시간구간에 따라 계산합니다. 후보 기록은 news/candidates/YYYY-MM-DD-am.json 또는 -pm.json에 `{cutoffAt,edition,candidates:[{id,title,publishedAt,scoreComponents:{importance,interest,domesticImpact,reliability},scoreReason,decision,reason,sources}]}`로 저장하고 rank.py로 점수를 계산합니다. 제외 후보도 이유를 남깁니다. 점수순을 기본으로 분야 균형·필수 웹툰을 고려해 선정합니다.
6. 각 뉴스는 한국어 존댓말 **2~4개 짧은 문단, 총 4~7문장**으로 씁니다. 무슨 일인지, 핵심 수치(없으면 만들지 않음), 이전 대비 변화, 왜 중요한지, 불확실성을 포함합니다. 어려운 용어는 풀어 설명합니다. 정치적 지지/비판 유도·자극적 표현 금지. `예정/검토/보도/주장/확정/분석` 상태를 명확히 하고 장중·종가·예측 수치를 구별합니다. 기업 자체 발표/연구 결과는 누구의 분석인지 밝힙니다.
7. 오전 마지막에는 **오늘 일정·시장 변수** 3~6개: 당일 09:00 이후 중요 일정과 개장 이후 확인할 시장 변수, 경제 지표, 국내 정치/외교, 미국장/글로벌 이벤트. 이미 08시에 발표된 지표를 미래 일정으로 넣지 않습니다. 저녁에는 **오늘의 핵심 키워드** 8~12개와 **내일 주목할 변수** 3~6개(다음 날만). 각 일정은 출처를 확인하고 한국시간 날짜·시각을 저장합니다. 해외 일정은 해당 날짜의 서머타임을 반영합니다. 시각 미확인은 null/timeNote로 표시하고 임의로 00:00을 쓰지 않습니다. 주말 등 일정이 적으면 확인 가능한 정책 시행·휴장·시장 관찰 변수를 고르고 없는 회담·지표를 만들어 수를 맞추지 않습니다.
8. 초안 JSON은 기존 회차 구조와 lib/news.ts, scripts/news/publish.py를 참조합니다. `id=YYYY-MM-DD-am|pm`, `date`, `edition`, `timezone=Asia/Seoul`, `cutoffAt`은 정확히 당일09:00/21:00, `generatedAt`은 **실제 생성 시각**. 출처 verifiedAt은 실제 이번 확인 시각입니다. 웹툰 오래된 기사에 fallbackNote, 사건 시간이 불명확하면 eventAt:null과 eventTimeNote를 씁니다. sources에 name/title/url/language/kind/publishedAt(미확인 null)/verifiedAt을 포함합니다. story publishedAt은 실제 확인된 기사 시각과 일치시킵니다.
9. **중복 검토**: 지난 회차와 동일 사건은 topicKey를 유지합니다. keyFacts는 핵심 숫자·결과·공식입장을 안정된 키/값으로 저장합니다. 표현만 바꾸거나 비교 키를 바꿔 중복 검사를 통과시키지 않습니다. 단순 재보도는 제외. 실제 중요한 변화가 있을 때만 followUp:{editionId,storyId,delta}로 가장 최근 기사를 참조하고 무엇이 달라졌는지 명확히 씁니다. publisher는 topicKey/URL/제목 유사도/사실 해시로 중복을 검사하고 변화 및 새 근거가 없는 재등장을 거부합니다. 의미상 중복 여부와 근거의 진실성은 별도로 직접 검토해야 합니다.
10. `python scripts/news/publish.py /절대/초안.json --check`로 검사하고 기사·수치·시점·문구·일정을 최종 검토합니다. 통과한 경우 `python scripts/news/publish.py /절대/초안.json --push`로 데이터만 커밋/배포합니다. 기존 회차는 덮어쓰지 않습니다. 이 스크립트는 public/data/news 및 docs/data/news의 해당 JSON과 index만 갱신합니다. 유머 24시간 삭제 규칙은 뉴스에 적용되지 않습니다.
11. GitHub Pages build 상태와 라이브 `data/news/index.json`, 회차 JSON을 확인합니다. 실제 게시 성공 전에는 성공이라고 말하지 않습니다. 실패하면 기존 브리핑은 그대로 보존하고 원인을 사용자에게 알립니다. 변경 없거나 이미 발행됐으면 조용히 종료합니다. 새 발행·실패 등 의미 있는 변화만 알립니다.

## 검증과 유지보수

- `python -m unittest discover -s scripts/news -p 'test_*.py'`
- `node --experimental-strip-types scripts/test-news.ts`
- UI 변경 때만 `npx tsc --noEmit --allowImportingTsExtensions`, `npm run build`, `python scripts/prepare-pages.py`; 회차 데이터만 발행할 때는 재빌드 불필요.
- publish.py는 기사의 진위까지 자동 판별하는 도구가 아닙니다. 웹 검색·교차검증·편집 검토가 선행되어야 합니다.
- 새 자동화나 중복 스케줄을 만들지 말고 기존 ㄴㅇㅅ 예약을 유지합니다.
