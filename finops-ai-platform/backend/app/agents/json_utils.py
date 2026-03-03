"""
Utility to extract JSON from LLM responses that may be
wrapped in markdown code fences (```json ... ```).
"""
import json
import re


def parse_llm_json(text: str) -> dict:
    """
    Parse JSON from an LLM response, stripping markdown fences if present.

    Handles:
        - Raw JSON: {"key": "value"}
        - Markdown-wrapped: ```json\n{"key": "value"}\n```
        - Markdown-wrapped (no lang): ```\n{"key": "value"}\n```
    """
    if not text or not text.strip():
        return {}

    cleaned = text.strip()

    # Strip markdown code fences
    fence_pattern = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)
    match = fence_pattern.match(cleaned)
    if match:
        cleaned = match.group(1).strip()

    # Try to find JSON object in the text
    if not cleaned.startswith("{"):
        # Search for first { ... } block
        brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(0)

    return json.loads(cleaned)
