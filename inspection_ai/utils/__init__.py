import json
import re


def extract_json_safe(response_text: str):
    # Remove code fences
    cleaned = re.sub(r"```json|```", "", response_text, flags=re.IGNORECASE)

    # Find first JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if not match:
        raise ValueError("No JSON object found")

    return json.loads(match.group(0))
