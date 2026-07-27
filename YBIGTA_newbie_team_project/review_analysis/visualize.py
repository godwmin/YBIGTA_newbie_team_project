# -*- coding: utf-8 -*-
"""리뷰 데이터 EDA / 비교분석 시각화 스크립트.

`database/preprocessed_reviews_*.csv` 를 읽어
  1) 개별 사이트 EDA 그래프 (별점/길이/날짜 분포, 이상치, 감성)
  2) 사이트간 비교분석 / 시계열 그래프 (여러 사이트 CSV 가 있을 때 자동 병합)
를 생성하여 `review_analysis/plots/` 에 저장한다.

팀원 1·2 의 preprocessed_reviews_*.csv 가 database 에 추가되면 비교 그래프에
자동으로 함께 그려지도록 작성되어 있다(확장형).
"""
from __future__ import annotations

import glob
import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd  # type: ignore[import-untyped]

# 한글 폰트 (Windows: Malgun Gothic)
for _font in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    try:
        plt.rcParams["font.family"] = _font
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(HERE, "..", "database")
PLOTS_DIR = os.path.join(HERE, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)


def load_sites() -> Dict[str, pd.DataFrame]:
    """database 의 preprocessed_reviews_*.csv 를 site 이름으로 로드한다."""
    sites: Dict[str, pd.DataFrame] = {}
    for path in sorted(glob.glob(os.path.join(DB_DIR, "preprocessed_reviews_*.csv"))):
        name = os.path.basename(path).replace("preprocessed_reviews_", "").replace(".csv", "")
        df = pd.read_csv(path)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        sites[name] = df
    return sites


def save(fig: plt.Figure, filename: str) -> None:
    path = os.path.join(PLOTS_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("saved:", os.path.relpath(path, HERE))


# --------------------------------------------------------------------- #
# 1) 개별 사이트 EDA
# --------------------------------------------------------------------- #
def eda_individual(name: str, df: pd.DataFrame) -> None:
    # 별점 분포
    fig, ax = plt.subplots(figsize=(7, 4))
    df["rating"].plot(kind="hist", bins=10, ax=ax, color="#4C78A8", edgecolor="white")
    ax.set_title(f"[{name}] 별점 분포")
    ax.set_xlabel("별점 (0.5~5.0)")
    ax.set_ylabel("리뷰 수")
    save(fig, f"eda_{name}_rating_hist.png")

    # 텍스트 길이 분포 + 박스플롯
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    df["review_len"].plot(kind="hist", bins=40, ax=axes[0], color="#72B7B2", edgecolor="white")
    axes[0].set_title(f"[{name}] 리뷰 길이 분포")
    axes[0].set_xlabel("글자 수")
    axes[0].set_ylabel("리뷰 수")
    axes[1].boxplot(df["review_len"].dropna(), vert=True, patch_artist=True,
                    boxprops=dict(facecolor="#72B7B2"))
    axes[1].set_title(f"[{name}] 리뷰 길이 박스플롯 (이상치)")
    axes[1].set_ylabel("글자 수")
    save(fig, f"eda_{name}_length.png")

    # 감성 파이차트
    if "sentiment" in df.columns:
        counts = df["sentiment"].value_counts()
        fig, ax = plt.subplots(figsize=(5.5, 5.5))
        ax.pie(counts.values, labels=[str(i) for i in counts.index], autopct="%1.1f%%",
               colors=["#54A24B", "#E45756", "#F2CF5B"], startangle=90)
        ax.set_title(f"[{name}] 감성 비율 (별점 기반)")
        save(fig, f"eda_{name}_sentiment_pie.png")

    # 날짜(월별) 분포
    monthly = df.set_index("created_at").resample("ME").size()
    fig, ax = plt.subplots(figsize=(9, 4))
    monthly.plot(kind="bar", ax=ax, color="#B279A2")
    ax.set_title(f"[{name}] 월별 리뷰 수")
    ax.set_xlabel("월")
    ax.set_ylabel("리뷰 수")
    ax.set_xticklabels([d.strftime("%Y-%m") for d in monthly.index], rotation=45, ha="right")
    save(fig, f"eda_{name}_monthly.png")


# --------------------------------------------------------------------- #
# 2) 사이트간 비교 / 시계열
# --------------------------------------------------------------------- #
def comparison(sites: Dict[str, pd.DataFrame]) -> None:
    colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]

    # 별점 평균 비교 (막대)
    fig, ax = plt.subplots(figsize=(7, 4))
    means = {n: d["rating"].mean() for n, d in sites.items()}
    ax.bar(list(means.keys()), list(means.values()), color=colors[: len(means)])
    ax.set_title("사이트별 평균 별점 비교")
    ax.set_ylabel("평균 별점")
    ax.set_ylim(0, 5)
    for i, (n, v) in enumerate(means.items()):
        ax.text(i, v + 0.05, f"{v:.2f}", ha="center")
    save(fig, "compare_rating_mean.png")

    # 별점 분포 겹쳐 그리기
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (n, d) in enumerate(sites.items()):
        d["rating"].plot(kind="hist", bins=10, alpha=0.5, ax=ax,
                         label=n, color=colors[i % len(colors)], density=True)
    ax.set_title("사이트별 별점 분포 (정규화)")
    ax.set_xlabel("별점")
    ax.legend()
    save(fig, "compare_rating_dist.png")

    # 시계열: 월별 리뷰 수 라인 비교 (사이트별 겹쳐서)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for i, (n, d) in enumerate(sites.items()):
        monthly = d.set_index("created_at").resample("ME").size()
        ax.plot([dt.strftime("%Y-%m") for dt in monthly.index], monthly.values,
                marker="o", label=n, color=colors[i % len(colors)])
    ax.set_title("사이트별 월별 리뷰 수 추이 (시계열 비교)")
    ax.set_xlabel("월")
    ax.set_ylabel("리뷰 수")
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    save(fig, "compare_monthly_trend.png")


def main() -> None:
    sites = load_sites()
    if not sites:
        print("preprocessed_reviews_*.csv 가 없습니다. 먼저 전처리를 실행하세요.")
        return
    print("사이트:", list(sites.keys()))
    for name, df in sites.items():
        eda_individual(name, df)
    comparison(sites)
    print("완료. plots 폴더를 확인하세요.")


if __name__ == "__main__":
    main()
