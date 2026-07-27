import os
import glob
from argparse import ArgumentParser
from typing import Dict, Type
from review_analysis.preprocessing.base_processor import BaseDataProcessor
from review_analysis.preprocessing.watcha_processor import WatchaProcessor
from review_analysis.preprocessing.megabox_processor import MegaboxProcessor


PREPROCESS_CLASSES: Dict[str, Type[BaseDataProcessor]] = {
    "reviews_watcha": WatchaProcessor,
    "reviews_megabox": MegaboxProcessor,
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


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. 단일 사이트 전처리 실행 (-c 옵션)
    if args.preprocessor:
        base_name = args.preprocessor
        csv_file = os.path.join(args.output_dir, f"{base_name}.csv")
        preprocessor_class = PREPROCESS_CLASSES[base_name]
        preprocessor = preprocessor_class(csv_file, args.output_dir)
        preprocessor.preprocess()
        preprocessor.feature_engineering()
        preprocessor.save_to_database()

    # 2. 모든 사이트 전처리 실행 (-a 옵션)
    elif args.all:
        review_collections = glob.glob(os.path.join(args.output_dir, "reviews_*.csv"))
        for csv_file in review_collections:
            base_name = os.path.splitext(os.path.basename(csv_file))[0]
            if base_name in PREPROCESS_CLASSES:
                preprocessor_class = PREPROCESS_CLASSES[base_name]
                preprocessor = preprocessor_class(csv_file, args.output_dir)
                preprocessor.preprocess()
                preprocessor.feature_engineering()
                preprocessor.save_to_database()
    else:
        print("옵션을 지정해 주세요. 예: -c reviews_megabox 또는 -a")