import os
import sys
import glob
import os
from argparse import ArgumentParser
from typing import Dict, Type

# 파이썬 경로 인식 처리 (최상단) — crawling/main.py 와 동일하게,
# 스크립트를 직접 실행해도 review_analysis 패키지를 import 할 수 있게 한다.
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/../../")

from review_analysis.preprocessing.base_processor import BaseDataProcessor
from review_analysis.preprocessing.imdb_processor import IMDbProcessor
from review_analysis.preprocessing.megabox_processor import MegaboxProcessor
from review_analysis.preprocessing.imdb_processor import IMDbProcessor


PREPROCESS_CLASSES: Dict[str, Type[BaseDataProcessor]] = {
    "reviews_watcha": WatchaProcessor,
    "reviews_megabox": MegaboxProcessor,
    "reviews_imdb": IMDbProcessor,
}


def create_parser() -> ArgumentParser:
    parser = ArgumentParser()

    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=False,
        default="database",
        help="Output file dir. Example: database",
    )

    parser.add_argument(
        "-c",
        "--preprocessor",
        type=str,
        required=False,
        choices=PREPROCESS_CLASSES.keys(),
        help=f"Which processor to use. Choices: {', '.join(PREPROCESS_CLASSES.keys())}",
    )

    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Run all data preprocessors. Default to False.",
    )

    return parser


def run_preprocessor(
    processor_name: str,
    input_path: str,
    output_dir: str,
) -> None:
    """Run one registered review preprocessor."""
    preprocessor_class = PREPROCESS_CLASSES[processor_name]
    preprocessor = preprocessor_class(input_path, output_dir)

    preprocessor.preprocess()
    preprocessor.feature_engineering()
    preprocessor.save_to_database()


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 단일 사이트 전처리 실행
    if args.preprocessor:
        base_name = args.preprocessor
        csv_file = os.path.join(
            args.output_dir,
            f"{base_name}.csv",
        )

        if not os.path.exists(csv_file):
            raise FileNotFoundError(
                f"Input CSV not found: {csv_file}"
            )

        run_preprocessor(
            base_name,
            csv_file,
            args.output_dir,
        )

    # 등록된 모든 사이트 전처리 실행
    elif args.all:
        review_collections = glob.glob(
            os.path.join(
                args.output_dir,
                "reviews_*.csv",
            )
        )

        for csv_file in review_collections:
            base_name = os.path.splitext(
                os.path.basename(csv_file)
            )[0]

            if base_name in PREPROCESS_CLASSES:
                run_preprocessor(
                    base_name,
                    csv_file,
                    args.output_dir,
                )

    else:
        print(
            "옵션을 지정해 주세요. "
            "예: -c reviews_imdb 또는 -a"
        )
