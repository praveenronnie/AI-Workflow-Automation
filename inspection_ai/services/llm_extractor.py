"""
LLM Extractor - Extracts key-value pairs from text using OpenRouter LLM.
"""

import json
import os

import requests

try:
    from google.colab import userdata

    os.environ["LLM_API_KEY"] = userdata.get("LLM_API_KEY")
    os.environ["LLM_URL"] = userdata.get("LLM_URL")
    os.environ["LLM_MODEL"] = userdata.get("LLM_MODEL")
except ModuleNotFoundError:
    from dotenv import load_dotenv

    load_dotenv()


class LLMExtractor:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.api_url = os.getenv("LLM_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

        if not self.api_key:
            raise ValueError("LLM_API_KEY not found in environment variables")

    def extract_key_value_pairs(self, text: str) -> dict:
        prompt = self._build_prompt(text)
        response = self._call_llm(prompt)
        return self._parse_response(response)

    def _build_prompt(self, text: str) -> str:
        return f"""Extract all explicit key-value pairs from the following text.

        Instructions:
        - Return ONLY a valid JSON object.
        - Do not include markdown, code fences, explanations, or any additional text.
        - Use the field names exactly as they appear in the text whenever possible.
        - Preserve values exactly as written.
        - If a field appears multiple times, return its values as an array.
        - If a field exists but has no value, use null.
        - Ignore text that is not associated with a key.
        - If no key-value pairs are found, return empty dict.
        - Ensure the output is valid JSON.

        Example

        Input:
        Name: John Doe
        Employee ID: EMP-1024
        Department: Engineering
        Email: john.doe@example.com
        Skills: Python, Java, SQL
        Project: Alpha
        Project: Beta
        Status:

        Output:
        {{
        "Name": "John Doe",
        "Employee ID": "EMP-1024",
        "Department": "Engineering",
        "Email": "john.doe@example.com",
        "Skills": "Python, Java, SQL",
        "Project": [
            "Alpha",
            "Beta"
        ],
        "Status": null
        }}

        Now extract the key-value pairs from the following text.

        Text:
        {text}

        Output:"""

    def _call_llm(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = requests.post(
            f"{self.api_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            raise RuntimeError(f"LLM API call failed: {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response, "error": "Failed to parse JSON"}
