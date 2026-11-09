# Evolvix Homepage

(주)이볼빅스 공식 홈페이지 — https://evolvix.co.kr

정적 HTML/CSS 사이트입니다. 공통 레이아웃(헤더·푸터·메타 태그)은 `src/layout.html` 한 곳에서 관리하고,
`build.py`(Python 표준 라이브러리만 사용)가 페이지를 조립해 `_site/`에 결과물을 만듭니다.
`main` 브랜치에 push하면 GitHub Actions가 빌드와 배포를 자동으로 수행합니다.

## 페이지

| 경로 | 한국어 | 영문 |
|---|---|---|
| 홈 | `/` | `/en/` |
| 머신비전 검사 | `/inspection/` | `/en/inspection/` |
| 공정 모니터링 · RMS-ON | `/monitoring/` | `/en/monitoring/` |

기존 RMS-ON 주소 `/product/`, `/en/product/`는 `build.py`의 `REDIRECTS`로 만든 이동 페이지가
`/monitoring/#product`로 보냅니다(검색 제외 noindex, canonical은 `/monitoring/`, 사이트맵 제외).
| 회사소개 | `/about/` | `/en/about/` |
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
    ├── css/style.css          # 색상 변수 · 레이아웃 · 홈 스크롤 장면 · 웨이브 전환 효과
    ├── js/story.js            # 홈 · 머신비전 페이지: sticky 스크롤 연출 · 등장 효과 (없어도 내용은 모두 보임)
    └── img/                   # 로고, 제품 사진, 히어로 배경, 파비콘, OG 이미지
        ├── scenes/            # 홈 장면 이미지
        ├── inspection/        # 머신비전 검사 페이지 이미지 (컨셉 이미지)
        └── monitoring/        # 공정 모니터링 페이지 이미지 (컨셉 이미지 · 데모 관제 화면)
tools/render_hero.py           # 히어로 배경 이미지 생성 스크립트 (numpy 필요, 사이트 빌드와 무관)
docs/copy-guide.md             # 홈페이지 문구 작성 기준
.github/workflows/deploy.yml   # 빌드 → GitHub Pages 배포
```

## 수정 방법

- **문구**: `src/pages/ko/<페이지>.html`과 `src/pages/en/<페이지>.html`을 함께 수정합니다.
  파일 맨 위 주석의 `title`, `description`은 브라우저 제목과 검색 결과 설명에 쓰입니다.
- **문구 작성 기준**: [`docs/copy-guide.md`](docs/copy-guide.md)를 참고하세요.
- **메뉴·회사 정보(푸터)·메일 양식**: `build.py` 상단의 `STRINGS`에서 언어별로 수정합니다.
- **페이지 본문에서 쓰는 치환 토큰**
  - `{{base}}` — 현재 언어의 홈 경로 (예: `{{base}}product/`)
  - `{{root}}` — 사이트 루트 경로 (예: `{{root}}assets/img/...`)
  - `{{email}}` — 대표메일
  - `{{mail_consult}}`, `{{mail_sample}}`, `{{mail_pilot}}`, `{{mail_job}}` — 제목·양식이 채워진 메일 링크
  - `{{sparkles}}`, `{{defect_map}}` — 홈 히어로 반짝임, 검사 화면 일러스트
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

## 홈 장면 이미지

| 파일 (`src/assets/img/scenes/`) | 쓰는 곳 | 비율 | 크기(가로 px) | 상태 |
|---|---|---|---|---|
| `line-*.webp` | 현장 섹션 (화면 전체 폭) | 2 : 1 | 1000 / 1774 | 보유 이미지 ("예시 이미지" 표시) |
| `film-*.webp` | 머신비전 장면 (1.6배 확대, 확대 화면 포함) | 16 : 10 | 1000 / 1585 | 보유 이미지 ("예시 이미지" 표시) |
| `testbed-*.webp` | 개발 · 검증 섹션 | 4 : 3 | 800 / 1448 | 보유 이미지 ("예시 이미지" 표시) |
| `install-*.webp` | RMS-ON 장면 | 16 : 10 | 900 / 1419 | 보유 이미지 ("설치 예시 이미지" 표시) |

교체할 때는 같은 비율로 여러 크기를 만들어 덮어쓰고, `src/pages/ko|en/index.html`의 `srcset`·`width`·`height` 값과
이미지 표시 문구(`gen-badge`)를 맞춰 주세요.

- 사진 위 위치 점(검사 위치, 측정 위치 등)은 HTML의 `style="--x:..%;--y:..%"` 값입니다.
- 머신비전 장면의 위치값은 CSS에 있습니다: 확대 기준점 `.mv-zoomer`(transform-origin), 전체 스크래치 범위 `.roi--scratch`,
  확대 화면 `.mv-detail-view img`, 검출 테두리 `.det`, 연결선은 HTML의 `.mv-link` 좌표입니다.
- RMS-ON 대시보드는 이미지가 아니라 HTML/SVG로 만든 **데모 화면**입니다.

## 머신비전 검사 페이지 이미지

| 파일 (`src/assets/img/inspection/`) | 쓰는 곳 | 비율 | 크기(가로 px) |
|---|---|---|---|
| `inspection-hero-*.webp` | 상단 검사 장면 | 16 : 9 (2 : 1로 잘라 표시) | 1000 / 1672 |
| `inspection-defect-*.webp` | 결함 검사 (원본 + 같은 이미지의 확대 창) | 3 : 2 | 1000 / 1536 |
| `inspection-dimension-*.webp` | 치수 검사 (W·H 측정선은 SVG) | 3 : 2 | 1000 / 1536 |
| `inspection-optics-*.webp` | 검사 시스템 구성 | 4 : 3 | 800 / 1448 |

- 모두 컨셉 이미지이며 화면에 캡션으로 표시합니다. 검출선 · 측정선 · 글자는 이미지가 아니라 HTML/CSS/SVG입니다.
- 결함 이미지를 바꾸면 CSS의 `.ins-box`(검출 박스, 이미지 기준 %), `.ins-zoom img`(확대 창), HTML `.ins-link` 좌표를 함께 맞춰 주세요.
- 치수 이미지를 바꾸면 HTML `.ins-measure`의 좌표(이미지 픽셀 기준, viewBox 1536×1024)를 시편 모서리에 맞춰 주세요.

## 전환 효과

- **홈 히어로**: 배경이 어둠 속에서 서서히 밝아지고, 제목이 흐릿한 상태에서 선명해진 뒤 빛이 한 번 지나갑니다.
- **머신비전 페이지 결함 검사** (데스크톱): 원본 → 검출 박스 → 연결선과 확대 창 순서로 바뀌고, 단계 표시(원본 확인 · 결함 위치 · 확대 확인)가 함께 움직입니다.
- **홈 솔루션 장면** (데스크톱): 머신비전과 RMS-ON 장면이 스크롤 구간 동안 화면에 머물며 3단계로 바뀝니다.
  스크롤을 되돌리면 이전 단계로 돌아갑니다. 모바일과 "동작 줄이기" 설정에서는 사진 → 제목 → 설명 순서의 일반 흐름으로 보입니다.
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
