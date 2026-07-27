import os
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from review_analysis.crawling.base_crawler import BaseCrawler


class MegaboxCrawler(BaseCrawler):
    """메가박스 영화 관람평 수집을 위한 크롤러 클래스입니다."""

    def __init__(self, output_dir: str, movie_no: str = "26033300", max_pages: int = 55):
        """MegaboxCrawler 초기화

        Args:
            output_dir (str): 결과 CSV 파일이 저장될 디렉토리 경로
            movie_no (str): 메가박스 영화 고유 번호 (기본값: 토이 스토리 5)
            max_pages (int): 수집할 최대 페이지 수 (55페이지 -> 약 550개)
        """
        self.output_dir = output_dir
        self.movie_no = movie_no
        self.max_pages = max_pages
        self.url = f"https://www.megabox.co.kr/movie-detail/comment?rpstMovieNo={self.movie_no}"
        self.reviews_df = pd.DataFrame()
        self.driver = None

    def start_browser(self) -> None:
        """BaseCrawler의 추상 메서드 구현: 셀레니움 브라우저를 시작합니다."""
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless") # 필요 시 주석 해제하여 백그라운드 실행
        options.add_argument("window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )

    def scrape_reviews(self) -> None:
        """BaseCrawler의 추상 메서드 구현: 관람평 데이터를 수집합니다."""
        if self.driver is None:
            self.start_browser()

        print(f"[MegaboxCrawler] 영화 페이지 접속: {self.url}")
        self.driver.get(self.url)
        time.sleep(3)

        reviews = []

        for target_page in range(1, self.max_pages + 1):
            print(
                f"[MegaboxCrawler] === {target_page} / {self.max_pages} 페이지 수집 중 ==="
            )

            if target_page > 1:
                try:
                    self.driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight - 500);"
                    )
                    time.sleep(0.5)

                    # 10페이지 단위 넘어갈 때 '>' 버튼 클릭
                    if (target_page - 1) % 10 == 0:
                        next_selectors = [
                            '//a[contains(@class, "btn-next")]',
                            '//a[contains(@class, "page-next")]',
                            '//a[contains(@class, "next")]',
                            '//a[@title="다음 페이지"]',
                            '//a[text()=">"]',
                        ]

                        next_btn = None
                        for sel in next_selectors:
                            btns = self.driver.find_elements(By.XPATH, sel)
                            if btns:
                                next_btn = btns[0]
                                break

                        if next_btn:
                            self.driver.execute_script(
                                "arguments[0].click();", next_btn
                            )
                            time.sleep(2)
                        else:
                            print(
                                "[MegaboxCrawler] '다음' 버튼을 찾지 못해 종료합니다."
                            )
                            break
                    else:
                        page_btn = self.driver.find_element(
                            By.XPATH,
                            f'//div[contains(@class, "pagination")]//a[text()="{target_page}"] | //nav[contains(@class, "pagination")]//a[text()="{target_page}"] | //a[text()="{target_page}"]',
                        )
                        self.driver.execute_script(
                            "arguments[0].click();", page_btn
                        )
                        time.sleep(1.5)

                except Exception as e:
                    print(
                        f"[MegaboxCrawler] {target_page}페이지 이동 중 오류 발생: {e}"
                    )
                    break

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            items = (
                soup.select(".movie-idv-story ul > li")
                or soup.select("#mainOneLineList > li")
                or soup.select(".story-area .one-line-list > li")
            )

            if not items:
                print(
                    "[MegaboxCrawler] 리뷰 항목이 더 이상 없어 종료합니다."
                )
                break

            for item in items:
                try:
                    score = item.select_one(".story-point, .point")
                    text = item.select_one(".story-txt, .txt, .story-cnt")
                    date = item.select_one(".story-date, .date")

                    review_text = text.text.strip() if text else ""

                    if review_text:
                        reviews.append(
                            {
                                "score": score.text.strip() if score else "",
                                "review": review_text,
                                "date": date.text.strip() if date else "",
                            }
                        )
                except Exception:
                    continue

        if self.driver:
            self.driver.quit()
            self.driver = None

        self.reviews_df = pd.DataFrame(reviews)
        print(
            f"[MegaboxCrawler] 총 {len(self.reviews_df)}개 수집 완료!"
        )

    def save_to_database(self) -> None:
        """BaseCrawler의 추상 메서드 구현: 수집된 리뷰를 지정 경로에 저장합니다."""
        if self.reviews_df.empty:
            print("[MegaboxCrawler] 저장할 리뷰가 없습니다.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        save_path = os.path.join(self.output_dir, "reviews_megabox.csv")
        self.reviews_df.to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"[MegaboxCrawler] 🎉 저장 완료: {save_path}")