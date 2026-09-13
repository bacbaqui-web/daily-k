# ㅋㅋㅋ

수집된 유머 글을 최초 공개 후 24시간 동안 모아 보는 개인용 웹사이트입니다.

- 사이트: https://bacbaqui-web.github.io/daily-k/
- ㅋㅋㅋ: 댓글의 ㅋ 총개수순
- ㅇㅎㅂ: 제목 표시 기준, 댓글 수순
- 우리 사이트 최초 공개(`firstPublishedAt`) 후 24시간 자동 만료, 읽음 처리, 영상 미리보기 및 키보드 탐색

## 빌드 및 배포

`npm ci` 후 `npm run build`를 실행합니다. `python3 scripts/prepare-pages.py`로 경로를 정리한 뒤 main에 반영합니다. GitHub Pages는 main의 /docs에서 배포합니다.

수집은 Mac의 전용 LaunchAgent에서 매시간 실행합니다. 애객에 게시된 지 12~13시간인 글을 15초 요청 간격으로 한 번 읽으며, GitHub에는 공개용 feed.json을 전달합니다. Oracle 수집은 중지되어 있습니다. 이미지와 영상 파일은 저장하지 않습니다. 원문 게시 시각과 우리 사이트 최초 공개 시각을 구분하며, 재배포해도 24시간 보관 기한은 연장되지 않습니다.
