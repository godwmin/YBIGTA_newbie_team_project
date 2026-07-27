import os
import re
import pandas as pd
from review_analysis.preprocessing.base_processor import BaseDataProcessor


class MegaboxProcessor(BaseDataProcessor):
    """메가박스 크롤링 데이터 전처리 클래스"""

    def __init__(self, input_file_path: str, output_dir: str):
        super().__init__(input_file_path, output_dir)
        self.input_file_path = input_file_path
        self.output_dir = output_dir
        self.df = pd.DataFrame()

    def clean_text(self, text: str) -> str:
        """텍스트 정제 (특수문자 제거 및 공백 정리)"""
        if not isinstance(text, str):
            return ""
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r"[^\w\s가-힣]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def preprocess(self) -> None:
        """데이터 정제 및 결측치 처리"""
        if not os.path.exists(self.input_file_path):
            self.input_file_path = "database/reviews_megabox.csv"

        if not os.path.exists(self.input_file_path):
            print(f"[MegaboxProcessor] 파일을 찾을 수 없습니다: {self.input_file_path}")
            return

        self.df = pd.read_csv(self.input_file_path)
        print(f"[MegaboxProcessor] 원본 데이터 로드 완료: {len(self.df)}개")

        # 1. 결측치 및 중복 제거
        self.df = self.df.dropna(subset=["review"]).copy()
        self.df = self.df.drop_duplicates(subset=["review"]).copy()

        # 2. 텍스트 정제
        self.df["cleaned_review"] = self.df["review"].apply(self.clean_text)
        self.df = self.df[self.df["cleaned_review"] != ""].copy()

        # 3. 평점 수치형 변환 및 rating 컬럼 생성 (visualize.py 호환)
        if "score" in self.df.columns:
            self.df["rating"] = pd.to_numeric(self.df["score"], errors="coerce")
            self.df["score"] = self.df["rating"]
        elif "rating" in self.df.columns:
            self.df["rating"] = pd.to_numeric(self.df["rating"], errors="coerce")

        # 4. created_at 컬럼 생성 (visualize.py 호환)
        if "date" in self.df.columns:
            self.df["created_at"] = pd.to_datetime(self.df["date"], errors="coerce")

        print(f"[MegaboxProcessor] 텍스트 정제 완료: {len(self.df)}개 남음")
    def feature_engineering(self) -> None:
        """파생변수 생성 (Feature Engineering)"""
        if self.df.empty:
            return

        # 리뷰 글자 수 및 단어 수
        self.df["review_len"] = self.df["cleaned_review"].apply(len)
        self.df["word_count"] = self.df["cleaned_review"].apply(lambda x: len(x.split()))

        # 날짜 파생변수
        if "date" in self.df.columns:
            self.df["datetime"] = pd.to_datetime(self.df["date"], errors="coerce")
            self.df["year"] = self.df["datetime"].dt.year
            self.df["month"] = self.df["datetime"].dt.month
            self.df["day"] = self.df["datetime"].dt.day
            self.df["weekday"] = self.df["datetime"].dt.weekday

        print("[MegaboxProcessor] 파생변수 생성 완료")

    def save_to_database(self) -> None:
        """전처리된 데이터를 CSV로 저장"""
        if self.df.empty:
            print("[MegaboxProcessor] 저장할 데이터가 없습니다.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        save_path = os.path.join(self.output_dir, "preprocessed_reviews_megabox.csv")
        self.df.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"[MegaboxProcessor] 전처리 완료 파일 저장 성공: {save_path}")