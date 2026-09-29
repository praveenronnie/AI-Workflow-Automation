import asyncio
import json
import re
import time
from typing import Optional, Dict, Any, List

from openai import OpenAI

from backend.ai.config import get_rag_config
from backend.utils.token_tracker import (
    increment_tokens,
    get_token_stats,
    reset_token_stats,
    save_token_stats,
)

settings = get_rag_config()


class CircuitBreaker:
    def __init__(self, failure_threshold: int = None, timeout: int = None):
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else settings.llm_circuit_break_threshold
        )
        self.timeout = (
            timeout if timeout is not None else settings.llm_circuit_break_timeout
        )
        self.failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}

    def is_open(self, model: str) -> bool:
        failures = self.failures.get(model, 0)
        if failures < self.failure_threshold:
            return False
        last = self.last_failure_time.get(model, 0)
        if time.time() - last > self.timeout:
            self.reset(model)
            return False
        return True

    def record_failure(self, model: str):
        self.failures[model] = self.failures.get(model, 0) + 1
        self.last_failure_time[model] = time.time()

    def record_success(self, model: str):
        self.failures.pop(model, None)
        self.last_failure_time.pop(model, None)

    def reset(self, model: str):
        self.failures.pop(model, None)
        self.last_failure_time.pop(model, None)


class ModelRouter:
    FLOWS = {
        "intent_detection": ("llm_intent_primary", "llm_intent_fallback"),
        "field_mapping": ("llm_field_mapping_primary", "llm_field_mapping_fallback"),
        "pdf_extraction": ("llm_pdf_primary", "llm_pdf_fallback"),
        "image_extraction": ("llm_image_primary", "llm_image_fallback"),
        "legacy_mapping": ("llm_legacy_map_primary", "llm_legacy_map_fallback"),
    }

    def __init__(self, circuit_breaker: CircuitBreaker = None):
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def _model_for(self, key: str) -> str:
        return getattr(settings, key, None) or settings.openai_base_model

    def prime(self, flow_type: str = None) -> str:
        keys = self.FLOWS.get(
            flow_type,
            ("llm_default_primary", "llm_default_fallback"),
        )
        primary = self._model_for(keys[0])
        fallback = self._model_for(keys[1])

        if not self.circuit_breaker.is_open(primary):
            return primary
        if not self.circuit_breaker.is_open(fallback):
            return fallback
        # Both degraded; return the best of the two and let retries cope.
        return primary

    def with_fallback(self, flow_type: str = None) -> tuple:
        # Return (primary, fallback) model names for a flow.
        keys = self.FLOWS.get(
            flow_type,
            ("llm_default_primary", "llm_default_fallback"),
        )
        return self._model_for(keys[0]), self._model_for(keys[1])


class LLMClient:
    def __init__(
        self,
        primary_model: str = None,
        fallback_model: str = None,
        circuit_breaker: CircuitBreaker = None,
        router: ModelRouter = None,
    ):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = primary_model
        self.fallback_model = fallback_model
        self.max_retries = settings.llm_max_retries
        self.backoff_factor = settings.llm_retry_backoff_factor
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.router = router or ModelRouter(self.circuit_breaker)
        # Cache of per-model OpenAI clients (keyed by model name).
        self._clients: Dict[str, OpenAI] = {}

    # ------------------------------------------------------------------
    # Provider client management
    # ------------------------------------------------------------------
    def _get_client(self, model: str) -> OpenAI:
        """Return (and cache) an OpenAI-compatible client for a model."""
        if model in self._clients:
            return self._clients[model]

        if model.startswith("nvidia/"):
            client = OpenAI(
                api_key=settings.nvidia_api_key,
                base_url=settings.nvidia_url,
            )
        else:  # kr/ or anything else -> default OpenAI-compatible endpoint
            client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        self._clients[model] = client
        return client

    def _call_model(
        self, model: str, content: Any, max_tokens: int, temperature: float = 0.0
    ) -> Dict[str, Any]:
        client = self.client
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        usage = response.usage
        increment_tokens(usage.prompt_tokens, usage.completion_tokens)
        save_token_stats()
        return self.clean_llm_json(response.choices[0].message.content)

    @staticmethod
    def _is_transient_error(e: Exception) -> bool:
        error_str = str(e).lower()
        return (
            "429" in error_str
            or "rate limit" in error_str
            or "quota" in error_str
            or "server error" in error_str
            or "temporarily" in error_str
            or ("5" in error_str[:3] and "error" in error_str)
        )

    def process_llm_request(
        self,
        content: Any,
        max_tokens: int = 4096,
        flow_type: str = None,
        model: str = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        target = model or self.router.prime(flow_type)
        _, fallback = self.router.with_fallback(flow_type)

        for attempt in range(self.max_retries):
            try:
                result = self._call_model(target, content, max_tokens, temperature)
                if result is not None:
                    self.circuit_breaker.record_success(target)
                    return result
                return {}
            except Exception as e:
                self.circuit_breaker.record_failure(target)
                if attempt < self.max_retries - 1 and self._is_transient_error(e):
                    time.sleep(self.backoff_factor**attempt)
                    continue
                break

        if (
            fallback
            and fallback != target
            and not self.circuit_breaker.is_open(fallback)
        ):
            try:
                result = self._call_model(fallback, content, max_tokens, temperature)
                if result is not None:
                    self.circuit_breaker.record_success(fallback)
                    return result
            except Exception:
                self.circuit_breaker.record_failure(fallback)

        default = settings.openai_base_model
        if default not in (target, fallback) and not self.circuit_breaker.is_open(
            default
        ):
            try:
                result = self._call_model(default, content, max_tokens, temperature)
                if result is not None:
                    return result
            except Exception:
                self.circuit_breaker.record_failure(default)

        return {}

    def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.0,
        flow_type: str = None,
        **kwargs,
    ) -> str:
        """Simple text-generation wrapper used by UniversalMapper.

        Returns the raw text payload (JSON string) or an empty string.
        """
        content = (
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            if system
            else prompt
        )

        result = self.process_llm_request(
            content,
            flow_type=flow_type or "intent_detection",
            **kwargs,
        )
        if isinstance(result, dict):
            try:
                return json.dumps(result)
            except Exception:
                return ""
        return str(result) if result else ""

    async def process_llm_request_async(
        self,
        content: Any,
        max_tokens: int = 4096,
        flow_type: str = None,
        model: str = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.process_llm_request,
            content,
            max_tokens,
            flow_type,
            model,
            temperature,
        )

    async def generate_async(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.0,
        flow_type: str = None,
        **kwargs,
    ) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.generate(prompt, system, temperature, flow_type, **kwargs),
        )

    async def batch_map_fields_async(
        self,
        fields: List[Any],
        evidence_packs: List[Dict],
        flow_type: str = "field_mapping",
        batch_size: int = None,
        section_name: str = "",
    ) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.batch_map_fields,
            fields,
            evidence_packs,
            flow_type,
            batch_size,
            section_name,
        )

    def clean_llm_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Clean and parse LLM JSON response."""
        if not response_text:
            return {}
        cleaned = re.sub(
            r"^```json\s*|\s*```$", "", response_text.strip(), flags=re.DOTALL
        )

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            return None

    # ------------------------------------------------------------------
    # Batching
    # ------------------------------------------------------------------
    def batch_map_fields(
        self,
        fields: List[Any],
        evidence_packs: List[Dict],
        flow_type: str = "field_mapping",
        batch_size: int = None,
        section_name: str = "",
    ) -> List[Dict]:
        if batch_size is None:
            batch_size = settings.llm_field_mapping_batch_size

        all_results: List[Dict] = []
        total = len(fields)

        for i in range(0, total, batch_size):
            batch_fields = fields[i : i + batch_size]
            batch_packs = evidence_packs[i : i + batch_size]

            prompt = self._build_batch_prompt(batch_fields, batch_packs, section_name)
            response = self.process_llm_request(
                prompt,
                max_tokens=3000,
                flow_type=flow_type,
            )

            parsed = self._parse_batch_response(response, batch_fields)

            for field in batch_fields:
                fid = self._field_id(field)
                entry = parsed.get(fid)
                if isinstance(entry, dict):
                    value = entry.get("value")
                    confidence = entry.get("confidence", 0.0)
                else:
                    value = entry
                    confidence = 0.0
                all_results.append(
                    {
                        "field_id": fid,
                        "value": value,
                        "confidence": confidence,
                    }
                )

        return all_results

    @staticmethod
    def _field_id(field) -> str:
        return (
            getattr(field, "id", None)
            or getattr(field, "fieldName", None)
            or str(field)
        )

    def _build_batch_prompt(
        self, fields: List[Any], evidence_packs: List[Dict], section_name: str = ""
    ) -> str:
        lines = [
            "Map the following form fields to the extracted evidence.",
            f"Section: {section_name}",
            "Return ONLY valid JSON of the form:",
            '{"field_id_1": {"value": "...", "confidence": 0.0}, "field_id_2": {...}}',
            "If a field has no supporting evidence, use value null.",
            "",
        ]
        for idx, field in enumerate(fields):
            fid = self._field_id(field)
            label = getattr(field, "label", None) or getattr(
                field, "fieldName", str(field)
            )
            ftype = getattr(field, "type", "text")
            options = getattr(field, "options", None)
            opts_str = ", ".join(str(o) for o in options) if options else "N/A"
            pack = evidence_packs[idx] if idx < len(evidence_packs) else {}
            summary = pack.get("summary") or pack.get("content") or str(pack)[:300]

            # Field description (optional) – taken from the field metadata so the
            # LLM has extra context per field.
            description = ""
            metadata = getattr(field, "metadata", None) or {}
            if isinstance(metadata, dict):
                description = metadata.get("description", "")

            lines.append(f"[Field {fid}] {label} (type: {ftype})")
            if description:
                lines.append(f"  Description: {description}")
            lines.append(f"  Options: {opts_str}")
            lines.append(f"  Evidence: {summary}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _parse_batch_response(response: Dict, fields: List[Any]) -> Dict:
        if not isinstance(response, dict):
            return {}
        parsed = {}
        for key in ("fields", "mappings", "results"):
            nested = response.get(key)
            if isinstance(nested, dict):
                parsed.update(nested)
        for fid in (LLMClient._field_id(f) for f in fields):
            if fid in response:
                parsed[fid] = response[fid]
        if not parsed and response:
            parsed = response
        return parsed

    def get_token_stats(self) -> Dict[str, int]:
        """Get current token statistics."""
        return get_token_stats()

    def reset_token_stats(self):
        """Reset token statistics."""
        reset_token_stats()
