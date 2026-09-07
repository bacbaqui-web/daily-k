# ㅋㅋㅋ

최근 24시간의 유머 글을 모아 보는 개인용 웹사이트입니다.

- 사이트: https://bacbaqui-web.github.io/daily-k/
- ㅋㅋㅋ: 댓글의 ㅋ 총개수순
- ㅇㅎㅂ: 제목 표시 기준, 댓글 수순
- 게시 후 24시간 자동 만료, 읽음 처리, 영상 미리보기 및 키보드 탐색

## 빌드 및 배포

`npm ci` 후 `npm run build`를 실행합니다. `python3 scripts/prepare-pages.py`로 경로를 정리한 뒤 main에 반영합니다. GitHub Pages는 main의 /docs에서 배포합니다.

수집은 별도 로컬 작업에서 수행하며 GitHub에는 공개용 feed.json만 전달합니다. Oracle 수집 연결은 아직 구성하지 않았습니다.
