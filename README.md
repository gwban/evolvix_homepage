# Evolvix Homepage

(주)이볼빅스 공식 홈페이지 — https://evolvix.co.kr

정적 HTML/CSS 사이트입니다. 공통 레이아웃(헤더·푸터·메타 태그)은 `src/layout.html` 한 곳에서 관리하고,
`build.py`(Python 표준 라이브러리만 사용)가 페이지를 조립해 `_site/`에 결과물을 만듭니다.
`main` 브랜치에 push하면 GitHub Actions가 빌드와 배포를 자동으로 수행합니다.

## 페이지

| 경로 | 한국어 | 영문 |
|---|---|---|
| 홈 | `/` | `/en/` |
| 회사소개 | `/about/` | `/en/about/` |
| 제품 | `/product/` | `/en/product/` |
| 채용 | `/careers/` | `/en/careers/` |
| 문의 | `/contact/` | `/en/contact/` |

## 구조

```
build.py                       # src/ → _site/ 빌드 + 링크/이미지 검증 + sitemap.xml/robots.txt 생성
src/
├── layout.html                # 모든 페이지 공통 레이아웃
├── pages/ko/*.html            # 한국어 페이지 본문
├── pages/en/*.html            # 영문 페이지 본문 (ko와 같은 파일명)
├── pages/404.html
└── assets/
    ├── css/style.css          # 색상 변수 · Bento Grid · 웨이브 전환 효과
    └── img/                   # 로고, 제품 사진, 파비콘, OG 이미지, wave-mask.svg
.github/workflows/deploy.yml   # 빌드 → GitHub Pages 배포
```

## 수정 방법

- **문구**: `src/pages/ko/<페이지>.html`과 `src/pages/en/<페이지>.html`을 함께 수정합니다.
  파일 맨 위 주석의 `title`, `description`은 브라우저 제목과 검색 결과 설명에 쓰입니다.
- **메뉴·회사 정보(푸터)**: `build.py` 상단의 `STRINGS`에서 언어별로 수정합니다.
- **페이지 본문에서 쓰는 치환 토큰**
  - `{{base}}` — 현재 언어의 홈 경로 (예: `{{base}}product/`)
  - `{{root}}` — 사이트 루트 경로 (예: `{{root}}assets/img/...`)
  - `{{email}}` — 대표메일
  - `{{waves}}` — 히어로 하단 웨이브 애니메이션
  - `{{wave_lines}}` — 그라데이션 타일 안의 웨이브 라인
  - `{{icon:이름}}` — 아이콘 (`build.py`의 `ICONS` 참고)
- **색상**: `src/assets/css/style.css` 상단 `:root` 변수만 바꾸면 전체에 적용됩니다.

## 로컬 빌드 · 미리보기 (Python 3.9+)

```bash
python3 build.py
```

```bash
python3 -m http.server 8000 --directory _site
```

브라우저에서 http://localhost:8000 을 엽니다. 빌드 중 깨진 링크나 이미지가 발견되면 오류와 함께 중단됩니다.

## 전환 효과

- **페이지 전환**: 메뉴로 이동하면 새 페이지가 물결 모양 경계로 아래에서 차오릅니다
  (View Transitions API). 지원하지 않는 브라우저에서는 일반 페이지 이동으로 동작합니다.
- **히어로 웨이브**와 **스크롤 등장 효과**는 CSS만으로 동작합니다.
- 운영체제에서 "동작 줄이기"를 켠 사용자에게는 모든 애니메이션이 꺼집니다.

## 최초 배포 설정 (1회)

1. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 선택합니다.
2. `main` 브랜치에 push하면 자동으로 빌드·배포됩니다. (Actions 탭에서 수동 실행도 가능)
3. **Settings → Pages → Custom domain**에 `evolvix.co.kr`을 입력하고, DNS 확인 후 **Enforce HTTPS**를 켭니다.
4. 도메인 업체 DNS 설정
   - `evolvix.co.kr` A 레코드: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `www` CNAME 레코드: `<GitHub 계정명>.github.io`
   - 값은 설정 직전에 [GitHub 공식 문서](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)에서 다시 확인하세요.
