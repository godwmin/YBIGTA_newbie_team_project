import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver

from review_analysis.crawling.base_crawler import BaseCrawler
from utils.logger import setup_logger


class IMDbReviewRecord(TypedDict):
    """CSV 한 행에 저장할 IMDb 사용자 리뷰 구조."""

    site: str
    target: str
    rating: int
    date: str
    review_title: str
    review: str
    source_url: str


class IMDbCrawler(BaseCrawler):
    """IMDb의 Toy Story 5 사용자 리뷰를 수집하는 크롤러."""

    TITLE_ID = "tt29355505"
    MIN_REVIEW_COUNT = 500
    TARGET_REVIEW_COUNT = 500
    PAGE_SIZE = 50
    REQUEST_RETRIES = 3
    REQUEST_DELAY_SECONDS = 1.0

    GRAPHQL_URL = "https://api.graphql.imdb.com/"
    GRAPHQL_QUERY = """
    query Reviews($id: ID!, $first: Int!, $after: ID) {
      title(id: $id) {
        reviews(first: $first, after: $after) {
          total
          edges {
            node {
              id
              summary { originalText }
              text { originalText { plainText } }
              authorRating
              submissionDate
            }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """

    def __init__(self, output_dir: str):
        """출력 경로, IMDb 주소, 브라우저와 결과 저장소를 초기화한다."""
        super().__init__(output_dir)
        self.base_url = (
            f"https://www.imdb.com/title/{self.TITLE_ID}/"
        )
        self.reviews_url = f"{self.base_url}reviews/"
        self.driver: Optional[WebDriver] = None
        self.reviews: List[IMDbReviewRecord] = []

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.logger: logging.Logger = setup_logger(
            str(output_path / "imdb_crawler.log")
        )
        logging.getLogger("selenium").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    def start_browser(self) -> None:
        """Selenium으로 IMDb 영화 페이지를 열고 HTML 제목을 확인한다."""
        options = Options()
        options.add_argument("--window-size=1440,1000")
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(60)
        self.driver.get(self.base_url)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        self.logger.info("IMDb 페이지 확인: %s", page_title or self.base_url)

    def scrape_reviews(self) -> None:
        """IMDb GraphQL 페이지를 순회하며 유효 리뷰 500개를 수집한다."""
        partial_path = Path(self.output_dir) / "reviews_imdb_partial.csv"
        seen_review_ids: Set[str] = set()
        cursor: Optional[str] = None
        has_next_page = True
        page_number = 0

        try:
            self.start_browser()

            while (
                len(self.reviews) < self.TARGET_REVIEW_COUNT
                and has_next_page
            ):
                page_number += 1
                page_data = self._request_page(cursor)
                edges = page_data.get("edges", [])
                page_info = page_data.get("pageInfo", {})
                if not isinstance(edges, list) or not isinstance(
                    page_info, dict
                ):
                    raise RuntimeError(
                        "IMDb 리뷰 응답 형식이 예상과 다릅니다."
                    )

                for edge in edges:
                    if not isinstance(edge, dict):
                        continue
                    node = edge.get("node")
                    if not isinstance(node, dict):
                        continue

                    review_id = str(node.get("id", "")).strip()
                    if not review_id or review_id in seen_review_ids:
                        continue

                    record = self._record_from_node(node)
                    if record is None:
                        continue
                    seen_review_ids.add(review_id)
                    self.reviews.append(record)

                self.reviews = self.reviews[
                    : self.TARGET_REVIEW_COUNT
                ]
                cursor_value = page_info.get("endCursor")
                cursor = str(cursor_value) if cursor_value else None
                has_next_page = bool(
                    page_info.get("hasNextPage", False)
                )

                self._write_records(partial_path, self.reviews)
                self.logger.info(
                    "%d페이지 처리: 유효 리뷰 %d개(목표 %d개)",
                    page_number,
                    len(self.reviews),
                    self.TARGET_REVIEW_COUNT,
                )
                if len(self.reviews) < self.TARGET_REVIEW_COUNT:
                    time.sleep(self.REQUEST_DELAY_SECONDS)
        finally:
            if self.driver is not None:
                self.driver.quit()
                self.driver = None

        if len(self.reviews) < self.MIN_REVIEW_COUNT:
            raise RuntimeError(
                "별점, 날짜, 본문이 있는 IMDb 리뷰가 "
                f"{len(self.reviews)}개입니다. 최소 "
                f"{self.MIN_REVIEW_COUNT}개가 필요합니다."
            )

        self.logger.info("IMDb 리뷰 %d개 수집 완료", len(self.reviews))

    def save_to_database(self) -> None:
        """수집한 IMDb 리뷰를 UTF-8 CSV로 저장한다."""
        if len(self.reviews) < self.MIN_REVIEW_COUNT:
            raise RuntimeError(
                "500개 이상의 리뷰를 수집한 뒤 저장할 수 있습니다."
            )

        output_path = Path(self.output_dir) / "reviews_imdb.csv"
        self._write_records(output_path, self.reviews)

        partial_path = Path(self.output_dir) / "reviews_imdb_partial.csv"
        if partial_path.exists():
            partial_path.unlink()
        self.logger.info("CSV 저장 완료: %s", output_path)

    def _request_page(
        self, cursor: Optional[str]
    ) -> Dict[str, Any]:
        """IMDb GraphQL에서 리뷰 한 페이지를 재시도와 함께 가져온다."""
        body = json.dumps(
            {
                "query": self.GRAPHQL_QUERY,
                "variables": {
                    "id": self.TITLE_ID,
                    "first": self.PAGE_SIZE,
                    "after": cursor,
                },
            }
        ).encode("utf-8")
        request = Request(
            self.GRAPHQL_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://www.imdb.com",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
                ),
            },
            method="POST",
        )

        last_error: Optional[Exception] = None
        for attempt in range(1, self.REQUEST_RETRIES + 1):
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )
                if not isinstance(payload, dict):
                    raise RuntimeError("IMDb JSON 응답이 올바르지 않습니다.")
                if payload.get("errors"):
                    raise RuntimeError(
                        f"IMDb GraphQL 오류: {payload['errors']}"
                    )

                title_data = payload.get("data", {}).get("title", {})
                reviews_data = title_data.get("reviews")
                if not isinstance(reviews_data, dict):
                    raise RuntimeError(
                        "IMDb 리뷰 데이터가 응답에 없습니다."
                    )
                return reviews_data
            except (
                HTTPError,
                URLError,
                TimeoutError,
                json.JSONDecodeError,
                RuntimeError,
            ) as error:
                last_error = error
                self.logger.warning(
                    "IMDb 요청 재시도(%d/%d): %s",
                    attempt,
                    self.REQUEST_RETRIES,
                    error,
                )
                if attempt < self.REQUEST_RETRIES:
                    time.sleep(float(attempt * 2))

        raise RuntimeError(
            "IMDb 리뷰 요청에 반복해서 실패했습니다."
        ) from last_error

    def _record_from_node(
        self, node: Dict[str, Any]
    ) -> Optional[IMDbReviewRecord]:
        """GraphQL 리뷰 한 건을 필수값이 있는 CSV 행으로 변환한다."""
        rating_value = node.get("authorRating")
        date = str(node.get("submissionDate", "")).strip()

        summary_data = node.get("summary", {})
        title = (
            str(summary_data.get("originalText", "")).strip()
            if isinstance(summary_data, dict)
            else ""
        )

        text_data = node.get("text", {})
        original_data = (
            text_data.get("originalText", {})
            if isinstance(text_data, dict)
            else {}
        )
        review = (
            str(original_data.get("plainText", "")).strip()
            if isinstance(original_data, dict)
            else ""
        )
        review = re.sub(r"\s+", " ", review)

        if not isinstance(rating_value, int):
            return None
        if not 1 <= rating_value <= 10 or not date or not review:
            return None

        return {
            "site": "IMDb",
            "target": "Toy Story 5",
            "rating": rating_value,
            "date": date,
            "review_title": re.sub(r"\s+", " ", title),
            "review": review,
            "source_url": self.reviews_url,
        }

    @staticmethod
    def _write_records(
        output_path: Path, records: List[IMDbReviewRecord]
    ) -> None:
        """리뷰 목록을 지정된 CSV 경로에 저장한다."""
        fieldnames = list(IMDbReviewRecord.__annotations__.keys())
        with output_path.open(
            "w", encoding="utf-8-sig", newline=""
        ) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
