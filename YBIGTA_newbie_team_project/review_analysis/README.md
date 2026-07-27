# 토이 스토리 5 IMDb 리뷰 크롤링

IMDb의 토이 스토리 5 사용자 리뷰를 수집합니다.

## 데이터 소개

- 사이트: IMDb
- 리뷰 페이지:
  <https://www.imdb.com/title/tt29355505/reviews/>
- 대상 영화: Toy Story 5
- 목표 개수: 유효 리뷰 500개
- 최소 개수: 500개
- 출력 파일: `reviews_imdb.csv`

CSV에는 다음 열이 포함됩니다.

| 열 | 설명 |
| --- | --- |
| `site` | 리뷰 사이트 |
| `target` | 영화 제목 |
| `rating` | 10점 만점 사용자 별점 |
| `date` | 리뷰 날짜 |
| `review_title` | 리뷰 제목 |
| `review` | 리뷰 내용 |
| `source_url` | 리뷰 출처 URL |

별점, 날짜, 내용이 없는 리뷰는 제외하며 리뷰 ID를 기준으로 중복도
제거합니다. IMDb의 공개 GraphQL 응답을 50개씩 페이지네이션합니다.

## 설치

Python 3.9 이상과 Chrome이 필요합니다.

```bash
python -m pip install -r requirements.txt
```

## 실행

프로젝트 최상위 디렉토리에서 실행합니다.

```bash
python -m review_analysis.crawling.main \
  -o database \
  --crawler imdb
```

등록된 모든 크롤러를 실행할 때는 다음 명령을 사용합니다.

```bash
python -m review_analysis.crawling.main -o database --all
```

실행 중 Selenium 확인용 Chrome 창이 잠시 표시됩니다. 리뷰 수집이 끝나면
자동으로 닫히므로 실행 중에는 창을 직접 닫지 마세요.

실행이 끝나면 지정한 출력 폴더에 다음 파일이 생성됩니다.

```text
database/
├── reviews_imdb.csv
└── imdb_crawler.log
```

수집 도중 네트워크 오류로 중단되면, 그 시점까지 검증된 데이터는
`database/reviews_imdb_partial.csv`에
보존됩니다. 최종 파일은 유효 리뷰가 최소 500개 모였을 때만 생성됩니다.

## 4회차 전처리 및 Feature Engineering

IMDb 원본 리뷰 500개에 대해
`review_analysis/preprocessing/imdb_processor.py`에서 다음 처리를
수행합니다.

- 결측치 처리: 별점, 날짜, 리뷰 본문이 비어 있는 행 제거
- 이상치 처리:
  - IMDb 별점 범위인 1~10점을 벗어난 행 제거
  - 미래 또는 수집일 기준 10년보다 오래된 날짜 제거
  - 5단어 미만 또는 2,000단어 초과 리뷰 제거
- 중복 처리: 정제된 리뷰 본문이 같은 행 제거
- 텍스트 전처리:
  - HTML 태그와 URL 제거
  - 영문 소문자 변환
  - 특수문자 제거 및 연속 공백 정리
  - TF-IDF 계산 시 영문 불용어 제거
- 파생변수:
  - `rating_normalized`: 별점을 0.1~1.0 범위로 정규화
  - `review_length_chars`, `review_length_words`: 리뷰 길이
  - `review_year`, `review_month`, `review_weekday`: 작성 시점
  - `is_weekend`: 주말 작성 여부
- 텍스트 벡터화: 전체 문서에서 자주 등장한 상위 50개 단어에 대한
  TF-IDF 변수를 생성

현재 데이터는 결측치, 중복 및 설정한 이상치가 없어 입력 500개가 모두
유지되었습니다. 결과는 `database/preprocessed_reviews_imdb.csv`에
저장됩니다.

프로젝트 최상위 디렉토리에서 전체 전처리기를 실행합니다.

```bash
python review_analysis/preprocessing/main.py \
  --output_dir database \
  --all
```

IMDb 전처리기만 실행할 수도 있습니다.

```bash
python review_analysis/preprocessing/main.py \
  --output_dir database \
  --preprocessor reviews_imdb
```
