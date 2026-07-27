# 🎬 YBIGTA 뉴비 팀 프로젝트 — 영화 리뷰 분석: 「토이 스토리 5 (2026)」

여러 리뷰 사이트에서 영화 **토이 스토리 5**의 리뷰를 수집(크롤링)하고, EDA·전처리·FE 를 거쳐
사이트 간 비교분석까지 수행하는 프로젝트입니다.

---

## 1. 팀 소개 · 팀원 자기소개  ⬜ [팀원2 총괄]
> 팀 소개 및 팀원별 자기소개를 작성해주세요.
최윤서: 안녕하세요, 저는 연세대학교에서 컴퓨터과학과와 계량위험관리전공을 공부하고 있습니다. 현재 고려대학교의 VGI 연구실에서 아바타 생성관련 연구를 진행하고 있습니다. 취미로는 동물 구경하는 것, 한강에서 자전거 타기, 옷 구경하는 것을 좋아합니다. 
---

## 2. 분석 주제 & 데이터 소개

- **분석 대상 영화**: 토이 스토리 5 (Toy Story 5, 2026 · 픽사/디즈니 · 2026-06 국내 개봉)
- **분석 목표**: 사이트별 리뷰의 별점/텍스트/시계열 특성을 비교

| 사이트 | 담당 | 링크 | 데이터 형식 | 개수 |
|---|---|---|---|---|
| **왓챠피디아** | ✅ 팀원3 | [토이 스토리 5](https://pedia.watcha.com/ko-KR/contents/m5DPaAD/comments) | CSV (별점·작성일·관람일·내용·좋아요·답글·스포일러) | **603** |
| (사이트1) | ⬜ 팀원1 | | | |
| (사이트2) | ⬜ 팀원2 | | | |

**왓챠피디아 데이터 (`database/reviews_watcha.csv`)** — ✅ [팀원3]
- 컬럼: `id, user, rating(0.5~5.0), created_at, watched_at, likes, replies, spoiler, text`
- 수집 개수: **603개** (최소 조건 500개 충족), 별점·날짜·내용 모두 포함
- 별점 척도: 왓챠 내부 0~10 정수 → 사용자 표기 **0.5~5.0** 로 변환 저장

---

## 3. 실행 방법

### 3-0. 환경 설치
```bash
pip install -r requirements.txt
```

### 3-1. 크롤링 → `database/reviews_{site}.csv`
```bash
# 프로젝트 루트에서 (review_analysis 패키지가 import 가능해야 함)
python review_analysis/crawling/main.py -o database --all
# 또는 특정 사이트만
python review_analysis/crawling/main.py -o database -c watcha
```
> ⚠️ **왓챠 크롤러 로그인 안내**: 왓챠피디아는 코멘트 전체 열람에 로그인이 필요하고, 목록 API 는 봇 요청을
> WAF 로 차단합니다. 따라서 `WatchaCrawler` 는 **로그인된 실제 Chrome(Selenium)** 으로 코멘트 페이지를
> 열고, 스크롤 시 SPA 가 호출하는 API 응답을 Chrome DevTools(성능 로그)로 캡처해 별점·**날짜**·내용을 얻습니다.
> 최초 1회 로그인을 위해 환경변수 `WATCHA_PROFILE` 에 로그인 정보가 저장될 Chrome user-data 디렉터리를 지정하세요.
> ```bash
> # 예) 로그인 세션이 저장된 프로필로 실행
> WATCHA_PROFILE="D:/watcha_profile" python review_analysis/crawling/main.py -o database -c watcha
> ```
> 창이 뜨면 왓챠에 한 번 로그인하면 이후 재실행 시 재로그인이 필요 없습니다.
> (본 레포에는 이미 수집 완료된 `reviews_watcha.csv` 가 포함되어 있습니다.)

### 3-2. 전처리/FE → `database/preprocessed_reviews_{site}.csv`
```bash
cd review_analysis/preprocessing
python main.py --output_dir ../../database --all
```

### 3-3. 시각화 → `review_analysis/plots/*.png`
```bash
python review_analysis/visualize.py
```

### 3-4. (웹 과제) 실행 방법 ⬜ [팀원2]
> 기존 Web 과제(FastAPI) 실행 방법을 정리해주세요.

---

## 4. 개별 분석 — EDA

### 4-1. 왓챠피디아  ✅ [팀원3]

수집한 603개 리뷰의 분포와 이상치를 살펴봤습니다. (그래프는 `review_analysis/plots/`)

| 별점 분포 | 리뷰 길이 분포 & 이상치 |
|---|---|
| ![rating](review_analysis/plots/eda_watcha_rating_hist.png) | ![length](review_analysis/plots/eda_watcha_length.png) |

| 감성 비율 | 월별 리뷰 수 |
|---|---|
| ![sentiment](review_analysis/plots/eda_watcha_sentiment_pie.png) | ![monthly](review_analysis/plots/eda_watcha_monthly.png) |

- **별점**: 평균 **3.76점**(중앙값 4.0, 표준편차 0.71). 3.5~4.0점에 집중된 좌로 치우친(호평) 분포로,
  왓챠 관객 평이 시리즈 최고점을 경신했다는 세간의 평과 일치합니다. 0.5~1.5점의 저평점은 소수(9건)의 이상치성 값.
- **텍스트 길이**: 평균 88자, 중앙값 42자. 한 줄 감상평이 다수이나 최대 950자의 장문 리뷰도 존재 →
  박스플롯 상 상단 이상치. 3자 미만의 초단문/공백성 리뷰도 존재해 전처리에서 제거.
- **감성(별점 기반)**: 긍정 476 / 중립 65 / 부정 35 → **약 83%가 긍정**.
- **날짜**: 2026-06(개봉월)에 리뷰가 폭증하고 7월까지 이어짐. 개봉 이전(2026-02 등) 소수 리뷰와
  개봉 훨씬 이전(2025년) 관심 코멘트는 기간 이상치로 판단.

### 4-2. 사이트1  ⬜ [팀원1]
### 4-3. 사이트2  ⬜ [팀원2]

---

## 5. 전처리 / Feature Engineering

### 5-1. 왓챠피디아  ✅ [팀원3]  (`review_analysis/preprocessing/watcha_processor.py`)

`reviews_watcha.csv`(603행) → `preprocessed_reviews_watcha.csv`(**576행**). 처리 내역:

- **결측치 처리**: 별점·내용·작성일(`rating`/`text`/`created_at`)이 없는 행 제거, 공백-only 텍스트 제거.
- **이상치 처리**
  - 별점: 정상 범위(**0.5~5.0**) 밖 값 제거.
  - 리뷰 길이: 2자 미만(초단문)·1000자 초과(비정상 장문) 제거.
  - 기간: 개봉 이전/미래 등 기간 이상치(2026-01-01 이전, 현재+1일 이후) 제거.
- **텍스트 전처리**: URL 제거, 한글/영문/숫자/기본 문장부호만 남기고 특수문자·이모지 제거, 중복 공백 정리 → `text_clean`.
  간이 한국어 불용어 사전 적용(형태소 분석기는 Java 의존이라 미사용).
- **파생 변수**: `year_month`, `date`, `hour`(시간대), `weekday`(요일), `is_weekend`(주말 여부),
  `review_len`(글자 수), `word_count`(단어 수), `sentiment`(별점 기반 긍정/중립/부정).
- **텍스트 벡터화**: `TfidfVectorizer`(min_df=2, 최대 3000 features) 로 TF-IDF 행렬 생성 후
  `TruncatedSVD` 로 **10차원 임베딩**(`tfidf_svd_0`~`tfidf_svd_9`)으로 축소하여 컬럼으로 저장.

### 5-2. 사이트1  ⬜ [팀원1]
### 5-3. 사이트2  ⬜ [팀원2]

---

## 6. 비교분석 (텍스트 · 시계열)  ✅ [팀원3 담당]

> `review_analysis/visualize.py` 는 `database/preprocessed_reviews_*.csv` 를 **자동으로 모두 병합**해
> 비교 그래프를 그립니다. 팀원1·2 의 `preprocessed_reviews_{site}.csv` 가 추가되면 아래 그래프에
> 해당 사이트가 자동으로 함께 그려집니다(현재는 왓챠 단독).

| 사이트별 평균 별점 | 사이트별 별점 분포 | 월별 리뷰 수 추이(시계열) |
|---|---|---|
| ![mean](review_analysis/plots/compare_rating_mean.png) | ![dist](review_analysis/plots/compare_rating_dist.png) | ![trend](review_analysis/plots/compare_monthly_trend.png) |

- **텍스트 비교 (키워드)**: 왓챠 리뷰 상위 키워드는 `장난감 · 버즈 · 시리즈 · 어른이 · 여전히 · 다시` 등으로,
  캐릭터·시리즈에 대한 애착과 '어른이 된 관객'의 정서가 두드러집니다.
  - 긍정 리뷰: `여전히 · 영원히 · 모든` 등 애정/총평 어휘 중심.
  - 부정 리뷰: `그냥 · 느낌 · 수밖에 · 없는` 등 아쉬움/유보 어휘 중심.
- **시계열**: 개봉월(2026-06) 리뷰가 압도적으로 많고 이후 감소하는 전형적 개봉 직후 패턴.
- ⬜ **사이트 간 비교 해석**: 팀원1·2 데이터 수집 완료 후, 사이트별 평균 별점 차이·별점 분포 차이·
  시계열 추이 차이를 위 그래프 기준으로 함께 해석 예정.

---

## 7. Git 협업 (Branch Protection / PR / Review)  ⬜ [팀원2 총괄]
> 아래 캡처 이미지를 `github/` 폴더에 넣고 첨부해주세요.
> - `github/branch_protection.png` — main 브랜치 보호 규칙
> - `github/push_rejected.png` — main 직접 push 거부 화면
> - `github/review_and_merged.png` — PR 리뷰 후 merge 화면
