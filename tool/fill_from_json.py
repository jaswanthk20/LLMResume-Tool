import argparse
import json
from pathlib import Path

from llm_utils import fill_docx_template


def main(json_file: str, output_docx: str, template: str | None = None) -> None:
    """Fill a DOCX template using resume data stored in ``json_file``."""
    try:
        with open(json_file, "r", encoding="utf-8") as jf:
            data = json.load(jf)
    except FileNotFoundError:
        print(f"Error: The file '{json_file}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: The file '{json_file}' is not a valid JSON file.")
        return

    template_path = Path(template) if template else Path(__file__).parent / "templates" / "Final Template.docx"
    fill_docx_template(data, Path(output_docx), template_path=template_path)
    print(f"Generated {output_docx}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fill a DOCX resume template using structured JSON data"
    )
    parser.add_argument("json_file", help="Path to the JSON file with resume data")
    parser.add_argument(
        "output_docx",
        nargs="?",
        default="filled_resume.docx",
        help="Path to the output DOCX file",
    )
    parser.add_argument(
        "--template",
        help="Optional path to a custom DOCX template",
    )
    args = parser.parse_args()
    main(args.json_file, args.output_docx, args.template)
