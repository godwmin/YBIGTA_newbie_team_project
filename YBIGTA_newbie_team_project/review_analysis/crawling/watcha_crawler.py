# -*- coding: utf-8 -*-
"""왓챠피디아(Watcha Pedia) 영화 코멘트 크롤러.

토이 스토리 5(Toy Story 5) 페이지의 사용자 코멘트(별점 / 날짜 / 내용)를 수집한다.

왓챠피디아는
  (1) 코멘트 목록을 무한 스크롤로 로딩하고,
  (2) 목록 API(`/api/contents/{code}/comments`)를 데이터센터 IP/봇 요청에 대해 WAF 로 차단하며,
  (3) 화면(DOM)에는 별점·내용은 렌더링하지만 '작성 날짜'는 표시하지 않는다.

따라서 본 크롤러는 **로그인된 실제 브라우저(Selenium)** 로 코멘트 페이지를 열고,
스크롤로 SPA 가 스스로 호출하는 코멘트 API 응답을 **Chrome DevTools Protocol(성능 로그)**
로 네트워크 레벨에서 가로채(=WAF 통과) JSON 을 파싱한다. 이 JSON 에는 화면에 없는
`created_at`(작성일)·`watched_at`(관람일)까지 포함되어 별점·날짜·내용을 모두 확보할 수 있다.

주의: 왓챠피디아 코멘트 전체 열람은 로그인이 필요하다. 환경변수 `WATCHA_PROFILE` 로
로그인 정보가 저장된 Chrome user-data 디렉터리를 지정하면 재실행 시 재로그인이 필요 없다.
(로그인 방법은 README 참고)
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from review_analysis.crawling.base_crawler import BaseCrawler
from utils.logger import setup_logger


class WatchaCrawler(BaseCrawler):
    """왓챠피디아 코멘트를 수집하여 CSV 로 저장하는 크롤러."""

    #: 토이 스토리 5 왓챠피디아 콘텐츠 코드
    CONTENT_CODE = "m5DPaAD"

    def __init__(self, output_dir: str) -> None:
        """
        Args:
            output_dir: 결과 CSV(`reviews_watcha.csv`)를 저장할 디렉터리.
        """
        super().__init__(output_dir)
        self.site_name: str = "watcha"
        self.base_url: str = f"https://pedia.watcha.com/ko-KR/contents/{self.CONTENT_CODE}/comments"
        self.target_count: int = 600  # 최소 조건(500) 이상 확보
        self.profile_dir: str = os.environ.get(
            "WATCHA_PROFILE",
            os.path.join(os.path.dirname(__file__), ".watcha_profile"),
        )
        self.driver: Optional[webdriver.Chrome] = None
        self.reviews: List[Dict[str, Any]] = []
        self._seen: set[str] = set()
        self.logger = setup_logger("watcha_crawler.log")

    # ------------------------------------------------------------------ #
    # browser
    # ------------------------------------------------------------------ #
    def start_browser(self) -> None:
        """Chrome 브라우저를 실행한다(로그인 프로필 + 성능 로그 활성화)."""
        opts = Options()
        opts.add_argument(f"--user-data-dir={self.profile_dir}")
        opts.add_argument("--window-size=1200,1000")
        opts.add_argument("--lang=ko-KR")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        # SPA 가 호출하는 API 응답을 캡처하기 위해 성능 로그를 켠다.
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        self.driver = webdriver.Chrome(options=opts)
        self.driver.set_page_load_timeout(60)
        self.logger.info("브라우저 실행 완료 (profile=%s)", self.profile_dir)

    # ------------------------------------------------------------------ #
    # scrape
    # ------------------------------------------------------------------ #
    def scrape_reviews(self) -> None:
        """코멘트 페이지를 스크롤하며 별점·날짜·내용을 수집한다."""
        if self.driver is None:
            self.start_browser()
        assert self.driver is not None
        driver = self.driver

        try:
            driver.get(self.base_url)
            time.sleep(5)

            # 로그인/코멘트 렌더 대기 (최대 3분)
            deadline = time.time() + 180
            while time.time() < deadline and not driver.find_elements(
                By.CSS_SELECTOR, 'a[href*="/comments/"]'
            ):
                self.logger.info("코멘트/로그인 대기중...")
                time.sleep(6)

            self._drain_network_logs()  # 최초 로딩 응답 캡처

            stagnant = 0
            it = 0
            while len(self.reviews) < self.target_count and it < 600:
                it += 1
                # 맨 아래로 스크롤하여 무한 스크롤 트리거
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.6)
                added = self._drain_network_logs()
                # 네트워크 지연으로 이번 스크롤 응답이 늦게 올 수 있으므로 한 번 더 대기 후 재확인
                if added == 0:
                    # 위로 살짝 올렸다 다시 내려 lazy-load 재트리거
                    driver.execute_script("window.scrollBy(0, -400);")
                    time.sleep(0.6)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.6)
                    added = self._drain_network_logs()
                if added:
                    self.logger.info("수집 %d개 (+%d)", len(self.reviews), added)
                    self._save_partial()  # 중간 저장
                    stagnant = 0
                else:
                    stagnant += 1
                    self.logger.debug("정체 %d회 (total=%d)", stagnant, len(self.reviews))
                # 목표(500) 이상 확보한 뒤에는 조금만 더 시도, 아직 부족하면 끈질기게 재시도
                limit = 8 if len(self.reviews) >= 500 else 25
                if stagnant >= limit:
                    self.logger.warning("더 이상 새 코멘트가 로딩되지 않아 종료합니다. (total=%d)", len(self.reviews))
                    break

            self.logger.info("스크래핑 종료: 총 %d개", len(self.reviews))
        finally:
            driver.quit()
            self.driver = None

    def _drain_network_logs(self) -> int:
        """성능 로그에서 코멘트 API 응답을 찾아 파싱하고 self.reviews 에 누적한다.

        Returns:
            이번 호출에서 새로 추가된 코멘트 수.
        """
        assert self.driver is not None
        try:
            logs = self.driver.get_log("performance")
        except Exception as exc:  # pragma: no cover - 방어적 처리
            self.logger.debug("성능 로그 조회 실패: %r", exc)
            return 0

        added = 0
        for entry in logs:
            try:
                message = json.loads(entry["message"])["message"]
            except (KeyError, ValueError):
                continue
            if message.get("method") != "Network.responseReceived":
                continue
            response = message.get("params", {}).get("response", {})
            url = response.get("url", "")
            if f"/contents/{self.CONTENT_CODE}/comments" not in url:
                continue
            request_id = message["params"]["requestId"]
            payload = self._response_body(request_id)
            if payload is None:
                continue
            added += self._collect_from_payload(payload)
        return added

    def _response_body(self, request_id: str) -> Optional[Dict[str, Any]]:
        """CDP 로 응답 본문을 가져와 JSON 으로 파싱한다."""
        assert self.driver is not None
        try:
            body = self.driver.execute_cdp_cmd(
                "Network.getResponseBody", {"requestId": request_id}
            )
        except Exception:
            return None
        raw = body.get("body", "")
        if body.get("base64Encoded"):
            try:
                raw = base64.b64decode(raw).decode("utf-8", "replace")
            except Exception:
                return None
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None

    def _collect_from_payload(self, payload: Dict[str, Any]) -> int:
        """API 응답(payload)에서 코멘트들을 추출한다."""
        result = payload.get("result", payload)
        items = result.get("result") or result.get("comments") or []
        if isinstance(items, dict):
            items = items.get("result") or items.get("comments") or []
        if not isinstance(items, list):
            return 0

        added = 0
        for c in items:
            if not isinstance(c, dict):
                continue
            code = c.get("code") or c.get("id")
            if not code or code in self._seen:
                continue
            self._seen.add(code)
            self.reviews.append(
                {
                    "id": code,
                    "user": (c.get("user") or {}).get("name"),
                    "rating": self._extract_rating(c),
                    "created_at": c.get("created_at"),
                    "watched_at": c.get("watched_at"),
                    "likes": c.get("likes_count"),
                    "replies": c.get("replies_count"),
                    "spoiler": c.get("spoiler"),
                    "text": (c.get("text") or "").replace("\r", " ").replace("\n", " ").strip(),
                }
            )
            added += 1
        return added

    @staticmethod
    def _extract_rating(comment: Dict[str, Any]) -> Optional[float]:
        """코멘트 작성자의 별점을 0.5~5.0 척도로 추출한다.

        왓챠 API 는 별점을 0~10 정수 척도(별 5.0 = 10)로 반환하므로 2 로 나눠
        사용자에게 보이는 0.5~5.0 별점 척도로 변환한다.
        """
        raw: Optional[Any] = None
        for key in ("user_content_action", "user_content_rating"):
            node = comment.get(key)
            if isinstance(node, dict) and node.get("rating") is not None:
                raw = node["rating"]
                break
        if raw is None:
            raw = comment.get("rating")
        if raw is None:
            return None
        try:
            return float(raw) / 2.0
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------ #
    # save
    # ------------------------------------------------------------------ #
    def _output_path(self) -> str:
        return os.path.join(self.output_dir, f"reviews_{self.site_name}.csv")

    def _save_partial(self) -> None:
        """중간 저장(장애 대비)."""
        self._write_csv(self._output_path())

    def save_to_database(self) -> None:
        """수집한 코멘트를 `reviews_watcha.csv` 로 저장한다."""
        os.makedirs(self.output_dir, exist_ok=True)
        path = self._output_path()
        self._write_csv(path)
        self.logger.info("저장 완료: %s (%d개)", path, len(self.reviews))

    def _write_csv(self, path: str) -> None:
        import csv

        os.makedirs(self.output_dir, exist_ok=True)
        fields = ["id", "user", "rating", "created_at", "watched_at", "likes", "replies", "spoiler", "text"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.reviews)
