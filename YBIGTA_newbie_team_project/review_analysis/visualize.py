# -*- coding: utf-8 -*-
"""리뷰 데이터 EDA / 비교분석 시각화 스크립트.

`database/preprocessed_reviews_*.csv` 를 읽어
  1) 개별 사이트 EDA 그래프 (별점/길이/날짜 분포, 이상치, 감성)
  2) 사이트간 비교분석 / 시계열 그래프 (여러 사이트 CSV 가 있을 때 자동 병합)
를 생성하여 `review_analysis/plots/` 에 저장한다.

사이트마다 전처리 산출물의 컬럼명과 별점 척도가 다르므로(왓챠 0.5~5.0,
메가박스·IMDb 1~10), 로드 단계에서 아래 표준 컬럼으로 정규화한 뒤 사용한다.

    _rating    사이트 원래 척도의 별점
    _rating5   5점 만점으로 환산한 별점 (사이트 간 비교는 반드시 이 값으로)
    _date      tz-naive datetime
    _len       리뷰 글자 수
    _sentiment 긍정/중립/부정 (없으면 _rating5 기준으로 파생)
    _text      전처리된 리뷰 텍스트
"""
from __future__ import annotations

import glob
import os
import re
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

# 실행 OS에 실제 설치된 한글 폰트만 선택한다.
for _font in (
    "Apple SD Gothic Neo",
    "AppleGothic",
    "Malgun Gothic",
    "NanumGothic",
    "Noto Sans CJK KR",
):
    try:
        font_manager.findfont(_font, fallback_to_default=False)
        plt.rcParams["font.family"] = _font
        break
    except ValueError:
        continue
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(HERE, "..", "database")
PLOTS_DIR = os.path.join(HERE, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

# 사이트별 별점 만점. 새 사이트가 추가되면 여기에 등록한다.
# 미등록 사이트는 관측된 최댓값으로 5점/10점 척도를 추정한다(아래 rating_scale 참고).
RATING_SCALE: Dict[str, float] = {
    "watcha": 5.0,
    "megabox": 10.0,
    "imdb": 10.0,
}

# 컬럼명이 사이트마다 달라 후보를 순서대로 탐색한다.
RATING_COLS = ("rating", "score")
DATE_COLS = ("created_at", "datetime", "date")
LEN_COLS = ("review_len", "review_length_chars")
TEXT_COLS = ("text_clean", "cleaned_review", "cleaned_text", "text", "review")

# 키워드 비교에서 제외할 어휘. 작품명·매체명처럼 모든 사이트에 공통으로
# 등장하는 단어는 사이트 간 차이를 드러내지 못하므로 뺀다.
STOPWORDS_KO = {
    "영화", "토이", "스토리", "토이스토리", "우디", "정말", "진짜", "너무", "그냥",
    "많이", "조금", "역시", "이번", "그리고", "하지만", "그래도", "때문", "생각",
    "봤는데", "봤습니다", "봤어요", "같아요", "합니다", "입니다", "있는", "없는",
    "보고", "보는", "하는", "되는", "것도", "건데", "인데", "에서", "으로",
}
STOPWORDS_EN = {
    "movie", "movies", "film", "films", "toy", "story", "woody", "just", "like",
    "really", "one", "even", "much", "get", "got", "would", "could", "also",
    "still", "make", "makes", "made", "see", "saw", "seen", "watch", "watching",
    "time", "way", "thing", "things", "lot", "bit", "pretty", "quite", "well",
}

_REL_DATE_RE = re.compile(r"^\s*(\d+)\s*(분|시간|일|주|개월|달|년)\s*전\s*$")


def rating_scale(name: str, series: pd.Series) -> float:
    """사이트의 별점 만점을 반환한다. 미등록 사이트는 관측 최댓값으로 추정."""
    if name in RATING_SCALE:
        return RATING_SCALE[name]
    observed = float(pd.to_numeric(series, errors="coerce").max())
    return 5.0 if observed <= 5.0 else 10.0


def parse_relative_dates(raw: pd.Series, reference: pd.Timestamp) -> pd.Series:
    """'2 분전', '3 시간전' 같은 상대 표기를 reference 기준 절대 날짜로 바꾼다.

    메가박스 크롤러는 최신 리뷰의 작성일을 상대 표기로 내려주는데, 전처리
    단계에서 파싱되지 않아 created_at 이 결측으로 남는다(546건 중 203건).
    분/시간 단위는 크롤링 당일로 보고 reference 날짜를 그대로 쓴다.
    """
    unit_days = {"분": 0, "시간": 0, "일": 1, "주": 7, "개월": 30, "달": 30, "년": 365}
    out: List[Optional[pd.Timestamp]] = []
    for value in raw:
        match = _REL_DATE_RE.match(str(value))
        if match is None:
            out.append(pd.NaT)
            continue
        amount, unit = int(match.group(1)), match.group(2)
        out.append(reference - pd.Timedelta(days=amount * unit_days[unit]))
    return pd.Series(out, index=raw.index)


def _first_col(df: pd.DataFrame, candidates) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _build_dates(df: pd.DataFrame) -> pd.Series:
    """절대 날짜 컬럼을 우선 파싱하고, 남은 결측은 상대 표기로 메운다."""
    parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for col in DATE_COLS:
        if not parsed.isna().any():
            break
        if col not in df.columns:
            continue
        candidate = pd.to_datetime(
            df[col],
            errors="coerce",
            utc=True,
            format="mixed",
        ).dt.tz_localize(None)
        parsed = parsed.fillna(candidate)

    if parsed.isna().any() and "date" in df.columns:
        reference = parsed.max()
        if pd.notna(reference):
            relative = parse_relative_dates(df.loc[parsed.isna(), "date"], reference)
            parsed = parsed.fillna(relative)
    return parsed


def load_sites() -> Dict[str, pd.DataFrame]:
    """database 의 preprocessed_reviews_*.csv 를 site 이름으로 로드/표준화한다."""
    sites: Dict[str, pd.DataFrame] = {}
    for path in sorted(glob.glob(os.path.join(DB_DIR, "preprocessed_reviews_*.csv"))):
        name = os.path.basename(path).replace("preprocessed_reviews_", "").replace(".csv", "")
        df = pd.read_csv(path)

        rating_col = _first_col(df, RATING_COLS)
        if rating_col is None:
            print(f"[skip] {name}: 별점 컬럼을 찾지 못했습니다.")
            continue

        scale = rating_scale(name, df[rating_col])
        df["_rating"] = pd.to_numeric(df[rating_col], errors="coerce")
        df["_rating5"] = df["_rating"] / scale * 5.0
        df["_scale"] = scale
        df["_date"] = _build_dates(df)

        len_col = _first_col(df, LEN_COLS)
        text_col = _first_col(df, TEXT_COLS)
        df["_text"] = df[text_col].fillna("").astype(str) if text_col else ""
        if len_col is not None:
            df["_len"] = pd.to_numeric(df[len_col], errors="coerce")
        else:
            df["_len"] = df["_text"].str.len()

        # 감성 라벨이 없는 사이트는 왓챠 전처리와 동일한 기준으로 파생한다
        # (5점 환산 3.5 이상 긍정 / 2.5 이하 부정 / 그 외 중립).
        if "sentiment" in df.columns:
            df["_sentiment"] = df["sentiment"]
        else:
            df["_sentiment"] = np.where(
                df["_rating5"] >= 3.5, "positive",
                np.where(df["_rating5"] <= 2.5, "negative", "neutral"),
            )

        sites[name] = df
    return sites


def save(fig: plt.Figure, filename: str) -> None:
    path = os.path.join(PLOTS_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("saved:", os.path.relpath(path, HERE))


# --------------------------------------------------------------------- #
# 1) 개별 사이트 EDA — 사이트 고유 척도 그대로 그린다
# --------------------------------------------------------------------- #
def eda_individual(name: str, df: pd.DataFrame) -> None:
    scale = float(df["_scale"].iloc[0])
    low = 0.5 if scale == 5.0 else 1

    # 별점 분포
    fig, ax = plt.subplots(figsize=(7, 4))
    df["_rating"].plot(kind="hist", bins=10, ax=ax, color="#4C78A8", edgecolor="white")
    ax.set_title(f"[{name}] 별점 분포")
    ax.set_xlabel(f"별점 ({low}~{scale:g})")
    ax.set_ylabel("리뷰 수")
    save(fig, f"eda_{name}_rating_hist.png")

    # 텍스트 길이 분포 + 박스플롯
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    df["_len"].plot(kind="hist", bins=40, ax=axes[0], color="#72B7B2", edgecolor="white")
    axes[0].set_title(f"[{name}] 리뷰 길이 분포")
    axes[0].set_xlabel("글자 수")
    axes[0].set_ylabel("리뷰 수")
    axes[1].boxplot(df["_len"].dropna(), patch_artist=True,
                    boxprops=dict(facecolor="#72B7B2"))
    axes[1].set_title(f"[{name}] 리뷰 길이 박스플롯 (이상치)")
    axes[1].set_ylabel("글자 수")
    save(fig, f"eda_{name}_length.png")

    # 감성 파이차트
    counts = df["_sentiment"].value_counts()
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.pie(counts.values, labels=[str(i) for i in counts.index], autopct="%1.1f%%",
           colors=["#54A24B", "#E45756", "#F2CF5B"], startangle=90)
    ax.set_title(f"[{name}] 감성 비율 (별점 기반)")
    save(fig, f"eda_{name}_sentiment_pie.png")

    # 날짜(월별) 분포
    monthly = df.dropna(subset=["_date"]).set_index("_date").resample("ME").size()
    if monthly.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4))
    monthly.plot(kind="bar", ax=ax, color="#B279A2")
    ax.set_title(f"[{name}] 월별 리뷰 수")
    ax.set_xlabel("월")
    ax.set_ylabel("리뷰 수")
    ax.set_xticklabels([d.strftime("%Y-%m") for d in monthly.index], rotation=45, ha="right")
    save(fig, f"eda_{name}_monthly.png")


# --------------------------------------------------------------------- #
# 2) 사이트간 비교 / 시계열 — 5점 환산 별점으로 비교한다
# --------------------------------------------------------------------- #
def comparison(sites: Dict[str, pd.DataFrame]) -> None:
    colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]

    # 별점 평균 비교 (막대)
    fig, ax = plt.subplots(figsize=(7, 4))
    means = {n: d["_rating5"].mean() for n, d in sites.items()}
    ax.bar(list(means.keys()), list(means.values()), color=colors[: len(means)])
    ax.set_title("사이트별 평균 별점 비교 (5점 만점 환산)")
    ax.set_ylabel("평균 별점 (5점 환산)")
    ax.set_ylim(0, 5)
    for i, (n, v) in enumerate(means.items()):
        scale = float(sites[n]["_scale"].iloc[0])
        ax.text(i, v + 0.08, f"{v:.2f}", ha="center", fontweight="bold")
        ax.text(i, 0.15, f"원척도 {scale:g}점 만점", ha="center", fontsize=8, color="white")
    save(fig, "compare_rating_mean.png")

    # 별점 분포 겹쳐 그리기 (5점 환산, 밀도)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.linspace(0, 5, 11)
    for i, (n, d) in enumerate(sites.items()):
        ax.hist(d["_rating5"].dropna(), bins=bins, alpha=0.5, label=n,
                color=colors[i % len(colors)], density=True)
    ax.set_title("사이트별 별점 분포 (5점 만점 환산, 정규화)")
    ax.set_xlabel("별점 (5점 환산)")
    ax.set_ylabel("밀도")
    ax.legend()
    save(fig, "compare_rating_dist.png")

    # 시계열: 월별 리뷰 수. 사이트마다 관측 월이 달라 공통 축으로 맞춘 뒤 그린다.
    monthlies = {
        n: d.dropna(subset=["_date"]).set_index("_date").resample("ME").size()
        for n, d in sites.items()
    }
    monthlies = {n: s for n, s in monthlies.items() if not s.empty}
    if monthlies:
        all_months = sorted({m for s in monthlies.values() for m in s.index})
        labels = [m.strftime("%Y-%m") for m in all_months]
        fig, ax = plt.subplots(figsize=(10, 4.5))
        for i, (n, s) in enumerate(monthlies.items()):
            # 사이트의 관측 범위 밖은 '리뷰 0건'이 아니라 '미수집'이므로
            # NaN으로 두어 선을 억지로 0까지 연결하지 않는다.
            aligned = s.reindex(all_months)
            ax.plot(labels, aligned.values, marker="o", label=n,
                    color=colors[i % len(colors)])
        ax.set_title("사이트별 월별 리뷰 수 추이 (시계열 비교)")
        ax.set_xlabel("월")
        ax.set_ylabel("리뷰 수")
        ax.legend()
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        save(fig, "compare_monthly_trend.png")

    # 리뷰 길이 비교 (박스플롯) — 사이트별 서술 밀도 차이
    fig, ax = plt.subplots(figsize=(8, 4.5))
    data = [d["_len"].dropna().values for d in sites.values()]
    bp = ax.boxplot(
        data,
        tick_labels=list(sites.keys()),
        patch_artist=True,
        showfliers=False,
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_title("사이트별 리뷰 길이 분포 (이상치 제외)")
    ax.set_ylabel("글자 수")
    save(fig, "compare_review_length.png")

    # 감성 구성비 비교 (누적 막대)
    order = ["positive", "neutral", "negative"]
    sent_colors = {"positive": "#54A24B", "neutral": "#F2CF5B", "negative": "#E45756"}
    ratios = pd.DataFrame(
        {n: d["_sentiment"].value_counts(normalize=True) for n, d in sites.items()}
    ).reindex(order).fillna(0.0) * 100
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bottom = np.zeros(len(ratios.columns))
    for label in order:
        values = ratios.loc[label].values
        ax.bar(ratios.columns, values, bottom=bottom, label=label, color=sent_colors[label])
        for x, (v, b) in enumerate(zip(values, bottom)):
            if v >= 4:
                ax.text(x, b + v / 2, f"{v:.1f}%", ha="center", va="center", fontsize=9)
        bottom += values
    ax.set_title("사이트별 감성 구성비 (5점 환산 별점 기준)")
    ax.set_ylabel("비율 (%)")
    ax.set_ylim(0, 100)
    ax.legend(loc="lower right")
    save(fig, "compare_sentiment_ratio.png")


# --------------------------------------------------------------------- #
# 3) 텍스트 비교 — 사이트별 TF-IDF 상위 키워드
# --------------------------------------------------------------------- #
def top_keywords(text: pd.Series, stopwords: set, english: bool = False,
                 topn: int = 12) -> pd.Series:
    docs = [t for t in text.fillna("").astype(str) if len(t.strip()) >= 2]
    if len(docs) < 5:
        return pd.Series(dtype=float)
    # 영어권 사이트는 sklearn 내장 불용어로 관사·전치사류를 먼저 걷어낸다.
    vec = TfidfVectorizer(
        token_pattern=r"(?u)\b\w\w+\b",
        min_df=2,
        max_features=3000,
        stop_words="english" if english else None,
    )
    matrix = vec.fit_transform(docs)
    scores = pd.Series(np.asarray(matrix.mean(axis=0)).ravel(), index=vec.get_feature_names_out())
    scores = scores[~scores.index.isin(stopwords)]
    scores = scores[[not i.isdigit() for i in scores.index]]
    return scores.sort_values(ascending=False).head(topn)


def compare_keywords(sites: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
    results: Dict[str, pd.Series] = {}
    for name, df in sites.items():
        # IMDb 는 영어, 국내 사이트는 한국어라 불용어 사전을 분리한다.
        english = name == "imdb"
        stopwords = STOPWORDS_EN if english else STOPWORDS_KO
        results[name] = top_keywords(df["_text"], stopwords, english=english)

    usable = {n: s for n, s in results.items() if not s.empty}
    if not usable:
        return results

    colors = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2"]
    fig, axes = plt.subplots(1, len(usable), figsize=(5 * len(usable), 5), squeeze=False)
    for i, (name, scores) in enumerate(usable.items()):
        ax = axes[0][i]
        ax.barh(scores.index[::-1], scores.values[::-1], color=colors[i % len(colors)])
        ax.set_title(f"[{name}] 상위 키워드 (TF-IDF)")
        ax.set_xlabel("평균 TF-IDF")
    save(fig, "compare_keywords.png")
    return results


# --------------------------------------------------------------------- #
def summary_table(sites: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in sites.items():
        dated = df["_date"].dropna()
        sent = df["_sentiment"].value_counts(normalize=True) * 100
        rows.append({
            "site": name,
            "n": len(df),
            "scale": f"{float(df['_scale'].iloc[0]):g}점",
            "mean_5": round(df["_rating5"].mean(), 2),
            "median_5": round(df["_rating5"].median(), 2),
            "std_5": round(df["_rating5"].std(), 2),
            "len_mean": round(df["_len"].mean(), 1),
            "len_median": round(df["_len"].median(), 1),
            "pos%": round(sent.get("positive", 0.0), 1),
            "neu%": round(sent.get("neutral", 0.0), 1),
            "neg%": round(sent.get("negative", 0.0), 1),
            "date_from": dated.min().date() if not dated.empty else None,
            "date_to": dated.max().date() if not dated.empty else None,
            "date_missing": int(df["_date"].isna().sum()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    sites = load_sites()
    if not sites:
        print("preprocessed_reviews_*.csv 가 없습니다. 먼저 전처리를 실행하세요.")
        return
    print("사이트:", list(sites.keys()))
    for name, df in sites.items():
        eda_individual(name, df)
    comparison(sites)
    keywords = compare_keywords(sites)

    print()
    print(summary_table(sites).to_string(index=False))
    print()
    for name, scores in keywords.items():
        if not scores.empty:
            print(f"[{name}] 상위 키워드:", ", ".join(scores.index[:12]))
    print("\n완료. plots 폴더를 확인하세요.")


if __name__ == "__main__":
    main()
