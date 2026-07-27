# -*- coding: utf-8 -*-
"""왓챠피디아 코멘트 데이터 전처리 / Feature Engineering.

`database/reviews_watcha.csv` 를 입력으로 받아
  - 결측치 처리
  - 이상치 처리(별점 범위, 리뷰 길이, 날짜 기간)
  - 텍스트 전처리(특수문자·중복공백 제거, 너무 길거나 짧은 리뷰 제거)
  - 파생 변수 생성(리뷰 길이, 요일/시간대, 주말 여부, 감성 그룹 등)
  - 텍스트 벡터화(TF-IDF -> TruncatedSVD 임베딩)
를 수행하고 `preprocessed_reviews_watcha.csv` 로 저장한다.
"""
from __future__ import annotations

import os
import re
from typing import List

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.decomposition import TruncatedSVD  # type: ignore[import-untyped]
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

from review_analysis.preprocessing.base_processor import BaseDataProcessor

# 간단한 한국어 불용어(형태소 분석기 미사용, Java 의존 회피)
KOREAN_STOPWORDS = {
    "그리고", "그러나", "하지만", "그래서", "너무", "정말", "진짜", "그냥",
    "영화", "정도", "부분", "생각", "느낌", "이건", "저건", "우리", "내가",
    "나는", "너무너무", "완전", "약간", "조금", "많이", "그런", "이런", "저런",
    "것", "수", "때", "더", "덜", "좀", "잘", "안", "못",
}


class WatchaProcessor(BaseDataProcessor):
    """왓챠피디아 리뷰 전처리기."""

    RATING_MIN = 0.5
    RATING_MAX = 5.0
    TEXT_MIN_LEN = 2       # 너무 짧은 리뷰 제거 기준(글자 수)
    TEXT_MAX_LEN = 1000    # 비정상적으로 긴 리뷰 제거 기준

    def __init__(self, input_path: str, output_dir: str) -> None:
        """
        Args:
            input_path: `reviews_watcha.csv` 경로.
            output_dir: 결과 저장 디렉터리.
        """
        super().__init__(input_path, output_dir)
        self.site_name = "watcha"
        self.df: pd.DataFrame = pd.read_csv(input_path)

    # ------------------------------------------------------------------ #
    def preprocess(self) -> None:
        """결측치·이상치·텍스트 전처리를 수행한다."""
        df = self.df.copy()
        n0 = len(df)

        # --- 날짜 파싱 ---
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        df["watched_at"] = pd.to_datetime(df["watched_at"], errors="coerce", utc=True)

        # --- 결측치 처리: 별점/내용/작성일 없는 행 제거 ---
        df["text"] = df["text"].astype("string").str.strip()
        df = df.dropna(subset=["rating", "text", "created_at"])
        df = df[df["text"].str.len() > 0]

        # --- 이상치: 별점 범위(0.5~5.0) ---
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df = df[(df["rating"] >= self.RATING_MIN) & (df["rating"] <= self.RATING_MAX)]

        # --- 텍스트 정제: URL 제거, 허용 문자만(한글/영문/숫자/일부 문장부호) 남기고 공백 정리 ---
        df["text_clean"] = df["text"].map(self._clean_text)
        df = df[df["text_clean"].str.len() > 0]

        # --- 이상치: 리뷰 길이(너무 짧거나 김) ---
        lengths = df["text_clean"].str.len()
        df = df[(lengths >= self.TEXT_MIN_LEN) & (lengths <= self.TEXT_MAX_LEN)]

        # --- 이상치: 날짜 기간(개봉 이전 or 미래) ---
        lower = pd.Timestamp("2026-01-01", tz="UTC")
        upper = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
        df = df[(df["created_at"] >= lower) & (df["created_at"] <= upper)]

        df = df.reset_index(drop=True)
        self.df = df
        print(f"[preprocess] {n0} -> {len(df)} rows (결측/이상치 제거)")

    @staticmethod
    def _clean_text(text: str) -> str:
        """URL·특수문자 제거 및 공백 정리."""
        if not isinstance(text, str):
            return ""
        text = re.sub(r"https?://\S+", " ", text)
        # 한글, 영문, 숫자, 기본 문장부호(. ! ?)만 남김
        text = re.sub(r"[^0-9A-Za-z가-힣\s.!?]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ------------------------------------------------------------------ #
    def feature_engineering(self) -> None:
        """파생 변수 생성 및 텍스트 벡터화."""
        df = self.df

        # --- 파생 변수 (시간/길이/감성) ---
        created_local = df["created_at"].dt.tz_convert("Asia/Seoul")
        df["year_month"] = created_local.dt.tz_localize(None).dt.to_period("M").astype(str)
        df["date"] = created_local.dt.date.astype(str)
        df["hour"] = created_local.dt.hour
        df["weekday"] = created_local.dt.day_name()
        df["is_weekend"] = created_local.dt.weekday >= 5
        df["review_len"] = df["text_clean"].str.len()
        df["word_count"] = df["text_clean"].str.split().map(len)
        # 감성 그룹: 3.5 이상 긍정 / 2.5 이하 부정 / 그 외 중립
        df["sentiment"] = np.where(
            df["rating"] >= 3.5, "positive",
            np.where(df["rating"] <= 2.5, "negative", "neutral"),
        )

        # --- 텍스트 벡터화: TF-IDF -> TruncatedSVD(10차원 임베딩) ---
        self._vectorize_text(df)

        self.df = df
        print(f"[feature_engineering] 파생변수/벡터화 완료, columns={list(df.columns)}")

    def _vectorize_text(self, df: pd.DataFrame) -> None:
        """TF-IDF 후 TruncatedSVD 로 축소한 임베딩을 컬럼으로 추가한다."""
        stop_words: List[str] = sorted(KOREAN_STOPWORDS)
        vectorizer = TfidfVectorizer(
            token_pattern=r"(?u)\b[0-9A-Za-z가-힣]{2,}\b",
            stop_words=stop_words,
            max_features=3000,
            min_df=2,
        )
        corpus = df["text_clean"].fillna("").tolist()
        tfidf = vectorizer.fit_transform(corpus)

        n_components = min(10, tfidf.shape[1] - 1) if tfidf.shape[1] > 1 else 1
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        emb = svd.fit_transform(tfidf)
        for i in range(emb.shape[1]):
            df[f"tfidf_svd_{i}"] = emb[:, i]

    # ------------------------------------------------------------------ #
    def save_to_database(self) -> None:
        """전처리 결과를 `preprocessed_reviews_watcha.csv` 로 저장한다."""
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, f"preprocessed_reviews_{self.site_name}.csv")
        self.df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[save] {path} ({len(self.df)} rows)")
