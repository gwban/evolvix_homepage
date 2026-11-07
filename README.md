# Evolvix Homepage

(주)이볼빅스 공식 홈페이지 — https://evolvix.co.kr

순수 HTML/CSS 정적 사이트이며, GitHub Actions로 GitHub Pages에 배포합니다. 빌드 도구와 JavaScript가 없습니다.

## 구조

```
.github/workflows/deploy.yml   # main 브랜치 push 시 site/ 폴더를 Pages에 배포
site/                          # 공개되는 파일은 이 폴더 안에만 둡니다
├── index.html                 # 한국어 (/)
├── en/index.html              # 영문 (/en/)
├── 404.html
├── assets/css/style.css       # 디자인 토큰(색상 변수) + Bento Grid 레이아웃
├── assets/img/                # 로고, 제품 사진, 파비콘, OG 이미지
├── robots.txt
└── sitemap.xml
```

## 수정 방법

- **문구 수정**: `site/index.html`(한국어)과 `site/en/index.html`(영문)의 구조가 같습니다. 한쪽을 고치면 다른 쪽도 같은 위치를 함께 수정하세요.
- **색상 변경**: `site/assets/css/style.css` 상단 `:root`의 변수만 바꾸면 전체에 적용됩니다.
  - `--color-bg #F5F5F7` · `--color-text #1D1D1F` · `--color-accent #0071E3` · `--color-surface #FBFBFD`
- **타일 크기**: 12열 그리드입니다. `span-3 / 4 / 5 / 6 / 7 / 8 / 12` 클래스로 너비를 조절합니다.

## 로컬 미리보기

```bash
python3 -m http.server 8000 --directory site
```

브라우저에서 http://localhost:8000 을 엽니다.

## 최초 배포 설정 (1회)

1. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 선택합니다.
2. `main` 브랜치에 push하면 자동으로 배포됩니다. (Actions 탭에서 수동 실행도 가능)
3. **Settings → Pages → Custom domain**에 `evolvix.co.kr`을 입력하고, DNS 확인 후 **Enforce HTTPS**를 켭니다.
4. 도메인 업체 DNS 설정
   - `evolvix.co.kr` A 레코드: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `www` CNAME 레코드: `<GitHub 계정명>.github.io`
   - 값은 설정 직전에 [GitHub 공식 문서](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)에서 다시 확인하세요.
