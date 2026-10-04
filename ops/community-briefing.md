# ㅋㅋㅋ 애객 원문·댓글 선별 운영

Asia/Seoul 매일 오전 09:00, 오후 21:00에 Codex가 애객(aagag.com) 화면을 직접 확인해 발행합니다. 기존 수집기 앱, Python 수집기, WebKit, launchd, Oracle과 과거 feed.json은 재개하거나 수정하지 않습니다. ㄴㅇㅅ 뉴스는 변경하지 않습니다.

## 확인과 선정

- public/data/community/index.json과 이전 14개 회차의 topicKey·원문 URL을 먼저 읽습니다. 같은 글·재게시와 동일 회차 중복 발행을 제외합니다.
- 최근 24시간 애객 후보 30~50개를 확인하고 조건에 맞는 글을 최대 15~20개 고릅니다. 다른 커뮤니티·SNS를 별도로 검색하지 않습니다. 애객이 제공한 원본 링크는 출처로 표시합니다.
- 회차 기준은 09:00/21:00 KST입니다. 00~08시 지연 실행은 전날 pm입니다. cutoffAt은 회차 시각, generatedAt은 실제 작성 시각입니다. 게시 시각을 실제 확인하고, 미확인은 null과 확인 범위에 한계를 남깁니다. 과거 이미지 재등장은 새 사건으로 표현하지 않습니다.
- 유머는 애객 댓글의 전부보기를 누른 뒤 표시된 댓글을 ID로 중복 제거해 실제 댓글 텍스트에 있는 문자 'ㅋ'를 모두 합산합니다. 제목·작성자명·본문의 ㅋ는 세지 않습니다. kCount가 10 이상인 글만 유머로 발행합니다. 내용이 유머인데 수치가 부족한 글을 다른 분류로 바꿔 넣지 않습니다.
- commentCount는 확인한 애객 댓글 수, commentsVerifiedAt은 확인 시각입니다. 원래 커뮤니티의 모든 댓글을 확인한 수치라고 주장하지 않습니다. 로딩 완료와 표시 댓글 수를 대조하고 일부만 확인했으면 그 범위를 verificationNote에 명시합니다. 미확인 값을 0으로 만들지 않습니다.
- 분류는 유머·정보·화제·생활·문화·스포츠·ㅇㅎㅂ입니다. 생활은 음식·소비·일상, 문화는 방송·음악·영화·게임, 스포츠는 경기와 선수 등 실제 내용에 맞게 분류합니다.
- ㅇㅎㅂ은 애객 제목 또는 펼친 출처 목록의 원본 커뮤니티 제목 중 하나라도 독립된 ㅇㅎ·ㅎㅂ·ㅇㅎㅂ 표시가 있으면 별도 분류합니다. 애객 제목에 표시가 없어도 제외하지 않습니다. 출처 목록에서 실제 확인한 표시가 있는 원본 제목과 애객이 제공한 원본 URL을 sources에 추가하고 verifiedAt을 기록합니다. 표시 없는 애객 제목을 임의로 바꾸지 않습니다. ㅋ 10개 기준을 적용하지 않으며 확인한 애객 댓글 수가 많은 순, 같으면 게시 시각이 최신인 순으로 고릅니다. 대표 이미지나 영상이 있는 글을 대상으로 합니다. 이전 요청에 따라 실제 댓글에 instagram.com, x.com, twitter.com 공개 링크 또는 단어 leaked가 확인된 글도 이 분류의 후보로 포함합니다. 제목 표시만으로 선정된 글에는 contentSignals를 요구하지 않습니다. contentSignals에 kind(instagram/x/leaked), commentId, 실제 링크 URL(링크일 때)을 기록합니다. 단서가 있다는 이유만으로 게시하지 말고 공개 비노골적 콘텐츠인지 직접 확인해 contentReview를 public-non-explicit로 남깁니다. 성적 유출물, 비동의 친밀 이미지, 노골적 성적 콘텐츠, 미성년자의 성적 대상화, 개인정보 노출과 악의적 루머는 제외합니다. 단서를 찾기 위해 해당 콘텐츠를 별도로 검색하지 않습니다. 확인할 수 없는 글은 제외합니다.
- CAPTCHA·접근 제한이면 우회하거나 다른 플랫폼으로 대체하지 않고 수집 실패와 사용자 인증 필요를 보고합니다. 조건에 맞는 글이 적으면 실제 개수와 이유를 알립니다. 3개 미만이면 새 회차를 발행하지 않습니다.

## 화면과 데이터

내용 요약과 전체 흐름 요약을 작성하지 않습니다. 실제 원문 제목을 title에 쓰고 summary와 overview는 빈 배열로 둡니다. 독자적인 제목으로 바꾸지 않습니다. 원본 문구는 짧은 인용 originalText, 댓글은 짧은 인용 comments에 담고 원문 링크를 제공합니다. 댓글 전문, 게시글 전문과 전체 이미지 묶음은 복제하지 않습니다. title·originalText·댓글 인용을 합쳐 출처 글 하나당 25단어 이내로 제한합니다. 인용이 중간에 잘렸으면 truncated:true로 표시하고, 생략한 내용을 만들어 붙이지 않습니다. 댓글 ID와 추천 수는 실제 확인한 경우만 남깁니다. 댓글 인용이 일부라고 화면에 알리고 전체 댓글은 원본에서 볼 수 있게 합니다.

본문에서 확인한 대표 이미지 URL 한 개를 imageUrl에 저장합니다. 영상이 있으면 실제 공개 video src와 poster URL을 videoUrl·videoPosterUrl에 저장합니다. 다른 글의 미디어로 대체하거나 미디어 파일을 다운로드하지 않습니다. 영상은 페이지 안에서 재생 버튼으로 재생하고 자동 재생하지 않습니다.

출처 보기를 펼쳐 커뮤니티별 재게시 항목을 sourceBreakdown에 [{"name":"루리웹","count":2}]로 합산하고 sourceStatsVerifiedAt에 확인 시각을 남깁니다. 애객 총합과 목록 합계가 다르면 차이는 미표시 출처로 구분합니다. 커뮤니티 이름이나 숫자를 추측하지 않습니다. 화면은 누적 출처라는 한 줄 비율 막대이며 당일 반응·추천·순위로 오해하지 않게 합니다. 선정 이유 selectionReason과 확인 범위 verificationNote는 원본 링크 아래 기본으로 접힌 영역에 표시합니다.

초안 경로: ~/Library/Application Support/DailyK/community/drafts/
저장소: /Users/bacbaqui/Desktop/code/02_tools/daily_k/홈페이지

```json
{"schemaVersion":2,"timezone":"Asia/Seoul","id":"YYYY-MM-DD-am","date":"YYYY-MM-DD","edition":"am","cutoffAt":"YYYY-MM-DDT09:00:00+09:00","generatedAt":"실제 ISO 시각","overview":[],"stories":[{"id":"짧은 안정된 ID","topicKey":"중복 판별 키","title":"원문 제목","category":"유머","summary":[],"originalText":"짧은 원본 인용","comments":[{"id":"확인한 댓글 ID","text":"짧은 실제 댓글","truncated":false,"likes":1}],"kCount":10,"commentCount":5,"commentsVerifiedAt":"실제 ISO 시각","selectionReason":"실제 선정 근거","popularityEvidence":"실제 확인한 인기 근거","verificationNote":"확인 범위와 한계","imageUrl":null,"videoUrl":null,"videoPosterUrl":null,"sourceBreakdown":[{"name":"커뮤니티 이름","count":2}],"sourceStatsVerifiedAt":"실제 ISO 시각","contentSignals":[],"sources":[{"name":"애객 또는 애객 제공 원출처","title":"실제 원문 제목","url":"확인한 원문 URL","imageUrl":null,"publishedAt":null,"verifiedAt":"실제 ISO 시각"}]}]}
```

## 검증·발행

python3 scripts/community/publish.py /절대/초안.json --check로 검증합니다. 원문 제목·인용·ㅋ 수·댓글 확인 범위·미디어·분류·중복을 직접 대조합니다. --push는 해당 회차와 index의 public/docs 네 파일만 커밋해 발행합니다. 뉴스 공용 발행 잠금을 쓰고 다른 변경을 보존합니다. 데이터 발행에는 전체 빌드가 필요 없습니다. GitHub Pages 빌드 성공과 실제 community JSON 반영을 확인합니다. 새 발행·실패·사용자 조치가 필요할 때만 알립니다. Mac과 Codex 앱이 실행 중이어야 예약 작업이 수행되며 09시·21시는 시작 시각입니다.

이미지 저장 전 본문 미디어의 로딩이 끝난 뒤 실제 img src와 naturalWidth가 0보다 큰지 확인합니다. 첫 로딩 순간 이미지가 없다는 이유만으로 imageUrl을 null로 두지 않습니다. 대표 이미지가 있는 글은 카드와 읽기 창 양쪽에서 로드 성공을 검증합니다. 긴 세로 이미지는 높이 제한 없이 원래 비율로 표시합니다.

본문·댓글에서 실제 확인한 인스타·X 주소는 portalLinks 배열에 완전한 URL로 별도 보존합니다. 인용이 짧아 링크가 생략되어도 읽기 창 상단에서 인스타·X 버튼으로 표시합니다. 링크 이름·주소는 추정하지 않습니다.
