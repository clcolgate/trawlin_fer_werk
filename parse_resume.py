#!/usr/bin/env python3
"""
parse_resume.py — Extract structured resume data using OpenAI or Anthropic APIs.

Usage:
    python parse_resume.py resume.pdf
    python parse_resume.py resume.txt
    python parse_resume.py resume.pdf --provider openai
    python parse_resume.py resume.pdf --provider anthropic
    python parse_resume.py resume.pdf --output custom.json
    python parse_resume.py resume.pdf --force
    python parse_resume.py resume.pdf --model gpt-4.1-mini
    python parse_resume.py resume.pdf --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
SCHEMA_PATH = SCRIPT_DIR / "resume_schema.json"
TEMPLATE_PATH = SCRIPT_DIR / "resume.template.json"
DEFAULT_OUTPUT = SCRIPT_DIR / "resume.json"
DEFAULT_PROVIDER = "openai"
DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-haiku-4-5",
}


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_text_pdf(file_path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        print("Error: pdfplumber not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=2)
            if not words:
                continue

            lines = []
            current_line: list[str] = []
            current_y: float | None = None

            for word in words:
                word_y = round(word["top"], 1)
                if current_y is None or abs(word_y - current_y) <= 3:
                    current_line.append(word["text"])
                    current_y = word_y
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word["text"]]
                    current_y = word_y

            if current_line:
                lines.append(" ".join(current_line))

            if lines:
                text_parts.append("\n".join(lines))

    if not text_parts:
        print(
            "Error: Could not extract text from PDF. Your file may be image-based (scanned).\n"
            "Try exporting as text from your PDF viewer, then run:\n"
            "  python parse_resume.py resume.txt"
        )
        sys.exit(1)

    return "\n\n".join(text_parts)


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_pdf(file_path)
    if suffix in (".txt", ".md", ".text"):
        return file_path.read_text(encoding="utf-8")

    print(f"Error: Unsupported file type '{suffix}'. Use a PDF or text file.")
    sys.exit(1)


def build_prompt(resume_text: str) -> str:
    return (
        "Extract all resume information from the following resume text into structured JSON.\n\n"
        "Be thorough — extract every piece of information present. For fields not present "
        "in the resume, use null or empty arrays as appropriate.\n\n"
        "For dates, use ISO 8601 format (YYYY-MM-DD). If only month/year is given, use the "
        "first of the month (e.g., 'May 2020' → '2020-05-01').\n\n"
        "For the preferences section, make reasonable inferences from context (e.g., if the "
        "resume shows only remote jobs, set work_arrangement to ['remote']).\n\n"
        "For form_fill_preferences, use these defaults — do not invent values:\n"
        "  salary_response: 'Open to negotiation'\n"
        "  cover_letter_style: 'always_pause'\n"
        "  essay_questions_style: 'always_pause'\n"
        "  diversity_questions_style: 'use_resume_data'\n"
        "  references_available: true\n"
        "  references_on_request_text: 'Available upon request'\n"
        "  default_availability_text: '2 weeks'\n"
        "  custom_overrides: {}\n\n"
        f"Resume text:\n---\n{resume_text}\n---"
    )


def make_openai_strict_schema(schema: dict) -> dict:
    """Convert a JSON schema into OpenAI strict-json-schema compatible form."""
    if isinstance(schema, dict):
        normalized = {k: make_openai_strict_schema(v) for k, v in schema.items()}

        if normalized.get("type") == "object" and isinstance(normalized.get("properties"), dict):
            keys = list(normalized["properties"].keys())
            normalized["required"] = keys
            normalized.setdefault("additionalProperties", False)

        return normalized

    if isinstance(schema, list):
        return [make_openai_strict_schema(item) for item in schema]

    return schema


def call_openai(resume_text: str, schema: dict, model: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "Error: OPENAI_API_KEY environment variable not set.\n"
            "Set it with: export OPENAI_API_KEY=sk-..."
        )
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    prompt = build_prompt(resume_text)
    strict_schema = make_openai_strict_schema(schema)

    print(f"Calling {model} (OpenAI) to extract resume data...")
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": "You extract resume text into valid JSON that strictly follows the provided schema.",
            },
            {"role": "user", "content": prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "resume_data",
                "schema": strict_schema,
                "strict": True,
            }
        },
    )

    output_text = getattr(response, "output_text", None)
    if not output_text:
        print("Error: OpenAI did not return structured JSON output.")
        sys.exit(1)

    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        print(f"Error: Failed to parse OpenAI JSON output: {exc}")
        sys.exit(1)


def call_claude(resume_text: str, schema: dict, model: str) -> dict:
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable not set.\n"
            "Set it with: export ANTHROPIC_API_KEY=sk-ant-..."
        )
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    tool_def = {
        "name": "save_resume_data",
        "description": "Save the extracted resume data as structured JSON",
        "input_schema": schema,
    }

    prompt = build_prompt(resume_text)

    print(f"Calling {model} (Anthropic) to extract resume data...")
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[tool_def],
        tool_choice={"type": "tool", "name": "save_resume_data"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_block:
        print("Error: Claude did not return structured data. Response:")
        for block in response.content:
            print(f"  {block}")
        sys.exit(1)

    return tool_block.input


def validate_output(data: dict, schema: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []

    errors = []
    validator = jsonschema.Draft7Validator(schema)
    for error in validator.iter_errors(data):
        errors.append(f"{' > '.join(str(p) for p in error.path)}: {error.message}")
    return errors


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_with_template(extracted: dict, template: dict) -> dict:
    return deep_merge(template, extracted)


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured resume data using OpenAI or Anthropic API"
    )
    parser.add_argument("resume_file", help="Path to resume PDF or text file")
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic"],
        default=DEFAULT_PROVIDER,
        help=f"LLM provider to use (default: {DEFAULT_PROVIDER})",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(DEFAULT_OUTPUT),
        help=f"Output JSON file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing output file without prompting",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model to use (defaults by provider: openai=gpt-4.1-mini, anthropic=claude-haiku-4-5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and print resume text only, do not call API",
    )
    args = parser.parse_args()

    model = args.model or DEFAULT_MODELS[args.provider]

    resume_path = Path(args.resume_file)
    if not resume_path.exists():
        print(f"Error: File not found: {resume_path}")
        sys.exit(1)

    output_path = Path(args.output)
    if output_path.exists() and not args.force and not args.dry_run:
        answer = input(f"{output_path} already exists. Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    schema = load_json(SCHEMA_PATH)
    template = load_json(TEMPLATE_PATH)

    print(f"Extracting text from {resume_path}...")
    resume_text = extract_text(resume_path)
    print(f"Extracted {len(resume_text)} characters across the resume.")

    if args.dry_run:
        print("\n--- Extracted Text ---")
        print(resume_text)
        print("--- End of Text ---")
        print("\nDry run complete. No API call made.")
        return

    if args.provider == "openai":
        extracted = call_openai(resume_text, schema, model)
    else:
        extracted = call_claude(resume_text, schema, model)

    merged = merge_with_template(extracted, template)

    validation_errors = validate_output(merged, schema)
    if validation_errors:
        print(f"\nWarning: {len(validation_errors)} validation issue(s) found:")
        for err in validation_errors:
            print(f"  - {err}")
        print("Writing file anyway — review and fix manually if needed.")
        merged["_validation_warnings"] = validation_errors

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nResume data written to {output_path}")
    print("Next steps:")
    print(f"  1. Open {output_path} and review the extracted data")
    print("  2. Update form_fill_preferences.salary_response if needed")
    print("  3. Check personal_info.authorized_to_work and requires_sponsorship")
    print("  4. Open Claude Code in this project directory and start applying!")


if __name__ == "__main__":
    main()
