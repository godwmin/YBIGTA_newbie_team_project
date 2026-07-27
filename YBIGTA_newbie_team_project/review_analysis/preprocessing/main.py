from argparse import ArgumentParser
from pathlib import Path
import sys
from typing import Dict, Type

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from review_analysis.preprocessing.base_processor import BaseDataProcessor
from review_analysis.preprocessing.imdb_processor import IMDbProcessor


# 모든 preprocessing 클래스를 예시 형식으로 적어주세요. 
# key는 "reviews_사이트이름"으로, value는 해당 처리를 위한 클래스
PREPROCESS_CLASSES: Dict[str, Type[BaseDataProcessor]] = {
    "reviews_imdb": IMDbProcessor,
    # key는 크롤링한 csv파일 이름으로 적어주세요! ex. reviews_naver.csv -> reviews_naver
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "database"


def create_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=False,
        default=str(DATABASE_DIR),
        help="Output file dir. Example: ../../database",
    )
    parser.add_argument(
        "-c",
        "--preprocessor",
        type=str,
        required=False,
        choices=PREPROCESS_CLASSES.keys(),
        help=(
            "Which processor to use. Choices: "
            f"{', '.join(PREPROCESS_CLASSES.keys())}"
        ),
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Run all data preprocessors. Default to False.",
    )
    return parser


def run_processor(processor_name: str, output_dir: str) -> None:
    """등록된 전처리기를 원본 CSV와 출력 폴더에 맞춰 실행한다."""
    input_path = DATABASE_DIR / f"{processor_name}.csv"
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    processor_class = PREPROCESS_CLASSES[processor_name]
    processor = processor_class(str(input_path), output_dir)
    processor.preprocess()
    processor.feature_engineering()
    processor.save_to_database()


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    if args.all:
        for processor_name in PREPROCESS_CLASSES:
            run_processor(processor_name, args.output_dir)
    elif args.preprocessor:
        run_processor(args.preprocessor, args.output_dir)
    else:
        raise ValueError("No preprocessor selected. Use --all or -c.")
