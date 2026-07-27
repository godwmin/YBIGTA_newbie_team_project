import os
import re

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from review_analysis.preprocessing.base_processor import BaseDataProcessor


class MegaboxProcessor(BaseDataProcessor):
    """메가박스 리뷰의 결측치·이상치·텍스트를 처리하고 FE를 수행한다."""

    RATING_MIN = 1
    RATING_MAX = 10
    TEXT_MIN_LEN = 2
    TEXT_MAX_LEN = 1000
    DATE_MIN = pd.Timestamp("2026-01-01")
    RELATIVE_DATE_PATTERN = re.compile(
        r"^\s*(\d+)\s*(분|시간|일|주|개월|달|년)\s*전\s*$"
    )

    def __init__(self, input_file_path: str, output_dir: str):
        super().__init__(input_file_path, output_dir)
        self.input_file_path = input_file_path
        self.output_dir = output_dir
        self.df = pd.DataFrame()

    @staticmethod
    def clean_text(text: str) -> str:
        """텍스트 정제 (특수문자 제거 및 공백 정리)"""
        if not isinstance(text, str):
            return ""
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"[^\w\s가-힣]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def parse_dates(cls, values: pd.Series) -> pd.Series:
        """절대 날짜와 한국어 상대 날짜를 모두 날짜로 변환한다.

        메가박스가 ``2 분전``·``4 일전``처럼 제공한 값은 CSV 안에서
        확인되는 가장 최신 절대 날짜(크롤링일)를 기준으로 환산한다.
        분·시간 단위는 정확한 수집 시각이 없으므로 크롤링일 당일로
        정규화한다.
        """
        raw = values.astype("string").str.strip()
        parsed = pd.to_datetime(
            raw,
            format="%Y.%m.%d",
            errors="coerce",
        )
        reference = parsed.max()
        if pd.isna(reference):
            reference = pd.Timestamp.now().normalize()

        for index in raw[parsed.isna()].index:
            match = cls.RELATIVE_DATE_PATTERN.match(str(raw.loc[index]))
            if match is None:
                continue
            amount = int(match.group(1))
            unit = match.group(2)
            if unit in {"분", "시간"}:
                converted = reference
            elif unit == "일":
                converted = reference - pd.Timedelta(days=amount)
            elif unit == "주":
                converted = reference - pd.Timedelta(weeks=amount)
            elif unit in {"개월", "달"}:
                converted = reference - pd.DateOffset(months=amount)
            else:
                converted = reference - pd.DateOffset(years=amount)
            parsed.loc[index] = pd.Timestamp(converted).normalize()

        return parsed

    def preprocess(self) -> None:
        """결측치·중복·별점/날짜/길이 이상치와 텍스트를 처리한다."""
        if not os.path.exists(self.input_file_path):
            raise FileNotFoundError(
                f"[MegaboxProcessor] 파일을 찾을 수 없습니다: "
                f"{self.input_file_path}"
            )

        self.df = pd.read_csv(self.input_file_path)
        print(f"[MegaboxProcessor] 원본 데이터 로드 완료: {len(self.df)}개")

        required = {"score", "review", "date"}
        missing_columns = required.difference(self.df.columns)
        if missing_columns:
            raise ValueError(
                "메가박스 CSV 필수 컬럼이 없습니다: "
                + ", ".join(sorted(missing_columns))
            )

        # 결측치 및 자료형 처리
        self.df["review"] = self.df["review"].astype("string").str.strip()
        self.df["rating"] = pd.to_numeric(
            self.df["score"],
            errors="coerce",
        )
        self.df["created_at"] = self.parse_dates(self.df["date"])
        self.df = self.df.dropna(
            subset=["review", "rating", "created_at"]
        ).copy()
        self.df = self.df[self.df["review"].str.len() > 0].copy()

        # 별점 및 날짜 이상치 처리
        tomorrow = pd.Timestamp.now().normalize() + pd.Timedelta(days=1)
        self.df = self.df[
            self.df["rating"].between(
                self.RATING_MIN,
                self.RATING_MAX,
            )
        ].copy()
        self.df = self.df[
            self.df["created_at"].between(self.DATE_MIN, tomorrow)
        ].copy()

        # 텍스트 정제, 길이 이상치 및 중복 처리
        self.df["cleaned_review"] = self.df["review"].apply(self.clean_text)
        lengths = self.df["cleaned_review"].str.len()
        self.df = self.df[
            lengths.between(self.TEXT_MIN_LEN, self.TEXT_MAX_LEN)
        ].copy()
        self.df = self.df.drop_duplicates(
            subset=["cleaned_review"]
        ).reset_index(drop=True)
        self.df["score"] = self.df["rating"]

        print(f"[MegaboxProcessor] 텍스트 정제 완료: {len(self.df)}개 남음")

    def feature_engineering(self) -> None:
        """날짜·길이·감성 파생변수와 TF-IDF/SVD 임베딩을 생성한다."""
        if self.df.empty:
            raise RuntimeError("preprocess()를 먼저 실행해야 합니다.")

        self.df["review_len"] = self.df["cleaned_review"].apply(len)
        self.df["word_count"] = self.df["cleaned_review"].apply(lambda x: len(x.split()))
        self.df["datetime"] = self.df["created_at"]
        self.df["year_month"] = (
            self.df["created_at"].dt.to_period("M").astype(str)
        )
        self.df["year"] = self.df["created_at"].dt.year
        self.df["month"] = self.df["created_at"].dt.month
        self.df["day"] = self.df["created_at"].dt.day
        self.df["weekday"] = self.df["created_at"].dt.day_name()
        self.df["is_weekend"] = self.df["created_at"].dt.weekday >= 5
        rating5 = self.df["rating"] / 2.0
        self.df["sentiment"] = np.where(
            rating5 >= 3.5,
            "positive",
            np.where(rating5 <= 2.5, "negative", "neutral"),
        )

        vectorizer = TfidfVectorizer(
            token_pattern=r"(?u)\b[0-9A-Za-z가-힣]{2,}\b",
            min_df=2,
            max_features=1000,
        )
        tfidf = vectorizer.fit_transform(
            self.df["cleaned_review"].fillna("")
        )
        if tfidf.shape[1] == 0:
            raise RuntimeError("메가박스 리뷰에서 TF-IDF 어휘를 만들 수 없습니다.")
        component_count = min(
            10,
            tfidf.shape[0] - 1,
            tfidf.shape[1] - 1,
        )
        if component_count < 1:
            embedding = tfidf.toarray()[:, :1]
        else:
            embedding = TruncatedSVD(
                n_components=component_count,
                algorithm="arpack",
                random_state=42,
            ).fit_transform(tfidf)
        for index in range(embedding.shape[1]):
            self.df[f"tfidf_svd_{index}"] = embedding[:, index]

        print("[MegaboxProcessor] 파생변수 및 TF-IDF/SVD 생성 완료")

    def save_to_database(self) -> None:
        """전처리된 데이터를 CSV로 저장"""
        if self.df.empty:
            print("[MegaboxProcessor] 저장할 데이터가 없습니다.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        save_path = os.path.join(self.output_dir, "preprocessed_reviews_megabox.csv")
        self.df.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"[MegaboxProcessor] 전처리 완료 파일 저장 성공: {save_path}")
