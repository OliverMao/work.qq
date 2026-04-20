from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from app.services.archive_text_preprocessor import ArchiveTextPreprocessor
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from app.services.archive_text_preprocessor import ArchiveTextPreprocessor


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preprocess archive chat json files.")
    parser.add_argument(
        "--source-dir",
        default="/www/workqq/work.qq/archive_data",
        help="Source directory that contains archive json files.",
    )
    parser.add_argument(
        "--output-dir",
        default="/www/workqq/work.qq/archive_data/save",
        help="Output directory for processed files.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    processor = ArchiveTextPreprocessor(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
    )
    result = processor.run()
    print(result)


if __name__ == "__main__":
    main()
