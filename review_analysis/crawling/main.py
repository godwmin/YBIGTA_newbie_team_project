import os
import sys
from argparse import ArgumentParser
from typing import Dict, Type

# 파이썬 경로 인식 처리 (최상단)
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../")

from review_analysis.crawling.base_crawler import BaseCrawler
from review_analysis.crawling.imdb_crawler import IMDbCrawler
from review_analysis.crawling.megabox_crawler import MegaboxCrawler
from review_analysis.crawling.watcha_crawler import WatchaCrawler

# 모든 크롤링 클래스를 예시 형식으로 적어주세요.
CRAWLER_CLASSES: Dict[str, Type[BaseCrawler]] = {
    "watcha": WatchaCrawler,
    "megabox": MegaboxCrawler,
    "imdb": IMDbCrawler,
}


def create_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="Output file directory. Example: ../../database",
    )
    parser.add_argument(
        "-c",
        "--crawler",
        type=str,
        required=False,
        choices=CRAWLER_CLASSES.keys(),
        help=f"Which crawler to use. Choices: {', '.join(CRAWLER_CLASSES.keys())}",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Run all crawlers. Default to False.",
    )
    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    if args.all:
        for crawler_name in CRAWLER_CLASSES.keys():
            Crawler_class = CRAWLER_CLASSES[crawler_name]
            crawler = Crawler_class(args.output_dir)
            crawler.scrape_reviews()
            crawler.save_to_database()

    elif args.crawler:
        Crawler_class = CRAWLER_CLASSES[args.crawler]
        crawler = Crawler_class(args.output_dir)
        crawler.scrape_reviews()
        crawler.save_to_database()

    else:
        raise ValueError("No crawlers.")