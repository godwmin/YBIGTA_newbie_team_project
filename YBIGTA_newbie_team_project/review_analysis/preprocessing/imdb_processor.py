import csv
import html
import logging
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set

from review_analysis.preprocessing.base_processor import BaseDataProcessor
from utils.logger import setup_logger


class IMDbProcessor(BaseDataProcessor):
    """IMDb 리뷰의 결측치·이상치·텍스트를 처리하고 TF-IDF를 생성한다."""

    MIN_RATING = 1
    MAX_RATING = 10
    MIN_REVIEW_WORDS = 5
    MAX_REVIEW_WORDS = 2000
    MAX_DATE_AGE_YEARS = 10
    TFIDF_FEATURE_COUNT = 50

    STOPWORDS = {
        "a", "about", "after", "again", "all", "also", "am", "an",
        "and", "any", "are", "as", "at", "be", "because", "been",
        "before", "being", "but", "by", "can", "could", "did", "do",
        "does", "doing", "down", "during", "each", "even", "few",
        "for", "from", "further", "get", "had", "has", "have", "having",
        "he", "her", "here", "hers", "herself", "him", "himself",
        "his", "how", "i", "if", "in", "into", "is", "it", "its",
        "itself", "just", "me", "more", "most", "my", "myself", "no",
        "nor", "not", "now", "of", "off", "on", "once", "only", "or",
        "other", "our", "ours", "ourselves", "out", "over", "own",
        "same", "she", "should", "so", "some", "such", "than", "that",
        "the", "their", "theirs", "them", "themselves", "then",
        "there", "these", "they", "this", "those", "through", "to",
        "too", "under", "until", "up", "very", "was", "we", "were",
        "what", "when", "where", "which", "while", "who", "whom", "why",
        "will", "with", "would", "you", "your", "yours", "yourself",
        "yourselves",
    }

    def __init__(self, input_path: str, output_dir: str):
        """입출력 경로, 처리 결과, 통계와 로거를 초기화한다."""
        super().__init__(input_path, output_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.rows: List[Dict[str, Any]] = []
        self.feature_names: List[str] = []
        self.stats: Counter[str] = Counter()
        self.logger: logging.Logger = setup_logger(
            str(output_path / "imdb_processor.log")
        )

    def preprocess(self) -> None:
        """결측치, 중복, 별점·날짜·텍스트 이상치를 제거하고 텍스트를 정제한다."""
        input_path = Path(self.input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"입력 CSV가 없습니다: {input_path}")

        today = date.today()
        oldest_allowed = today - timedelta(
            days=365 * self.MAX_DATE_AGE_YEARS
        )
        seen_reviews: Set[str] = set()

        with input_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as file:
            for raw_row in csv.DictReader(file):
                self.stats["input_rows"] += 1
                rating_text = str(raw_row.get("rating", "")).strip()
                date_text = str(raw_row.get("date", "")).strip()
                review_text = str(raw_row.get("review", "")).strip()

                if not rating_text or not date_text or not review_text:
                    self.stats["removed_missing"] += 1
                    continue

                try:
                    rating = int(float(rating_text))
                except ValueError:
                    self.stats["removed_invalid_rating"] += 1
                    continue
                if not self.MIN_RATING <= rating <= self.MAX_RATING:
                    self.stats["removed_invalid_rating"] += 1
                    continue

                try:
                    review_date = datetime.strptime(
                        date_text, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    self.stats["removed_invalid_date"] += 1
                    continue
                if not oldest_allowed <= review_date <= today:
                    self.stats["removed_date_outlier"] += 1
                    continue

                cleaned_review = self._clean_text(review_text)
                word_count = len(cleaned_review.split())
                if not (
                    self.MIN_REVIEW_WORDS
                    <= word_count
                    <= self.MAX_REVIEW_WORDS
                ):
                    self.stats["removed_length_outlier"] += 1
                    continue

                duplicate_key = cleaned_review.casefold()
                if duplicate_key in seen_reviews:
                    self.stats["removed_duplicate"] += 1
                    continue
                seen_reviews.add(duplicate_key)

                row: Dict[str, Any] = {
                    "site": str(raw_row.get("site", "")).strip(),
                    "target": str(raw_row.get("target", "")).strip(),
                    "rating": rating,
                    "date": review_date.isoformat(),
                    "review_title": self._clean_text(
                        str(raw_row.get("review_title", ""))
                    ),
                    "review": review_text,
                    "source_url": str(
                        raw_row.get("source_url", "")
                    ).strip(),
                    "cleaned_review": cleaned_review,
                }
                self.rows.append(row)

        self.stats["output_rows"] = len(self.rows)
        if not self.rows:
            raise RuntimeError("전처리 후 남은 IMDb 리뷰가 없습니다.")
        self.logger.info(
            "전처리 완료: 입력 %d개, 출력 %d개, 제거 %d개",
            self.stats["input_rows"],
            self.stats["output_rows"],
            self.stats["input_rows"] - self.stats["output_rows"],
        )

    def feature_engineering(self) -> None:
        """길이·날짜 파생변수와 상위 50개 단어의 TF-IDF 변수를 생성한다."""
        if not self.rows:
            raise RuntimeError("preprocess()를 먼저 실행해야 합니다.")

        tokenized_documents: List[List[str]] = []
        document_frequency: Counter[str] = Counter()

        for row in self.rows:
            review_date = datetime.strptime(
                str(row["date"]), "%Y-%m-%d"
            ).date()
            tokens = self._tokens(str(row["cleaned_review"]))
            tokenized_documents.append(tokens)
            document_frequency.update(set(tokens))

            row["rating_normalized"] = round(
                int(row["rating"]) / self.MAX_RATING, 4
            )
            row["review_length_chars"] = len(str(row["cleaned_review"]))
            row["review_length_words"] = len(
                str(row["cleaned_review"]).split()
            )
            row["review_year"] = review_date.year
            row["review_month"] = review_date.month
            row["review_weekday"] = review_date.strftime("%A")
            row["is_weekend"] = int(review_date.weekday() >= 5)

        top_terms = sorted(
            document_frequency,
            key=lambda term: (-document_frequency[term], term),
        )[: self.TFIDF_FEATURE_COUNT]
        self.feature_names = [
            f"tfidf_{self._safe_feature_name(term)}"
            for term in top_terms
        ]

        document_count = len(self.rows)
        for row, tokens in zip(self.rows, tokenized_documents):
            term_counts = Counter(tokens)
            token_count = max(len(tokens), 1)
            for term, feature_name in zip(
                top_terms, self.feature_names
            ):
                term_frequency = term_counts[term] / token_count
                inverse_document_frequency = (
                    math.log(
                        (1 + document_count)
                        / (1 + document_frequency[term])
                    )
                    + 1
                )
                row[feature_name] = round(
                    term_frequency * inverse_document_frequency, 8
                )

        self.logger.info(
            "파생변수 및 TF-IDF 변수 %d개 생성 완료",
            len(self.feature_names),
        )

    def save_to_database(self) -> None:
        """전처리·FE 결과를 명세에 맞는 CSV 파일명으로 저장한다."""
        if not self.rows or not self.feature_names:
            raise RuntimeError(
                "preprocess()와 feature_engineering()을 먼저 실행해야 합니다."
            )

        output_path = (
            Path(self.output_dir) / "preprocessed_reviews_imdb.csv"
        )
        base_fields = [
            "site",
            "target",
            "rating",
            "date",
            "review_title",
            "review",
            "source_url",
            "cleaned_review",
            "rating_normalized",
            "review_length_chars",
            "review_length_words",
            "review_year",
            "review_month",
            "review_weekday",
            "is_weekend",
        ]
        fieldnames = base_fields + self.feature_names

        with output_path.open(
            "w", encoding="utf-8-sig", newline=""
        ) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)
        self.logger.info("전처리 CSV 저장 완료: %s", output_path)

    @staticmethod
    def _clean_text(text: str) -> str:
        """HTML, URL, 특수문자를 제거하고 영문 소문자 공백 텍스트로 만든다."""
        cleaned = html.unescape(text)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"https?://\S+|www\.\S+", " ", cleaned)
        cleaned = cleaned.lower().replace("’", "'")
        cleaned = re.sub(r"[^a-z0-9'\s]", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _tokens(self, text: str) -> List[str]:
        """TF-IDF 계산에 사용할 영문 토큰과 불용어 제거 결과를 반환한다."""
        return [
            token
            for token in re.findall(r"[a-z0-9']{2,}", text)
            if token not in self.STOPWORDS
        ]

    @staticmethod
    def _safe_feature_name(term: str) -> str:
        """단어를 CSV 열 이름에 안전한 문자열로 변환한다."""
        safe_name = re.sub(r"[^a-z0-9]+", "_", term).strip("_")
        return safe_name or "term"
