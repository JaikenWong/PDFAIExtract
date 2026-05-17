import json
import re
import time
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar

from anthropic import Anthropic
from openai import AzureOpenAI, OpenAI

from models.schemas import CertificateInfo, ExtractionResult, get_extraction_fields
from config import get_config

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _first_balanced_brace_json(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _json_candidates(text: str) -> List[str]:
    stripped = _strip_code_fences(text)
    candidates: List[str] = []
    s = stripped.strip()
    if s.startswith("{") and s.endswith("}"):
        candidates.append(s)
    bal = _first_balanced_brace_json(stripped)
    if bal and bal not in candidates:
        candidates.append(bal)
    m = re.search(r"\{[\s\S]*\}", stripped)
    if m and m.group() not in candidates:
        candidates.append(m.group())
    return candidates


def parse_llm_json(content: str) -> Dict[str, Any]:
    for raw in _json_candidates(content):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return {}


class LLMExtractor:
    def __init__(self):
        cfg = get_config()["llm"]
        self.provider = cfg["provider"]
        self.model = cfg.get("model", "astron-code-latest")
        self.vision_model = cfg.get("vision_model", self.model)

        api_key = cfg.get("api_key", "")
        api_secret = cfg.get("api_secret", "")
        if self.provider == "anthropic":
            self.client = Anthropic(
                api_key=api_key or None,
                base_url=cfg.get("base_url") or None,
            )
            self.vision_client = self.client
        elif self.provider == "openai":
            combined_key = f"{api_key}:{api_secret}" if api_secret else api_key
            self.client = OpenAI(
                api_key=combined_key or None,
                base_url=cfg.get("base_url") or None,
            )
            vision_key = cfg.get("vision_api_key") or combined_key
            vision_url = cfg.get("vision_base_url") or cfg.get("base_url")
            vision_model_id = cfg.get("vision_model_id") or self.vision_model
            self.vision_client = OpenAI(
                api_key=vision_key or None,
                base_url=vision_url or None,
            )
            self.vision_model = vision_model_id
        elif self.provider == "azure_openai":
            combined_key = f"{api_key}:{api_secret}" if api_secret else api_key
            endpoint = (cfg.get("azure_endpoint") or cfg.get("base_url") or "").strip()
            if not endpoint:
                raise ValueError(
                    "azure_openai requires azure_endpoint or base_url (Azure resource URL, e.g. https://xxx.openai.azure.com)"
                )
            api_version = cfg.get("azure_api_version") or "2024-02-15-preview"
            self.client = AzureOpenAI(
                azure_endpoint=endpoint.rstrip("/"),
                api_version=api_version,
                api_key=combined_key or None,
            )
            self.vision_client = self.client
            self.vision_model = cfg.get("vision_model_id") or self.vision_model
            self.model = cfg.get("model") or self.model
        else:
            raise ValueError(f"Unsupported llm provider: {self.provider}")

    def _extract_text_from_response(self, response) -> str:
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            if parts:
                return "".join(parts)
        choice_content = getattr(getattr(response, "choices", [None])[0], "message", None)
        if choice_content is not None:
            text = getattr(choice_content, "content", None)
            if isinstance(text, str):
                return text
        return ""

    def _retry_llm(self, op_name: str, fn: Callable[[], T]) -> T:
        ext = get_config().get("extraction", {})
        max_retries = max(1, int(ext.get("max_retries", 3)))
        delay = float(ext.get("retry_delay", 1.0))
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return fn()
            except Exception as e:
                last_err = e
                logger.warning(
                    "%s failed (%s/%s): %s",
                    op_name,
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt + 1 < max_retries:
                    time.sleep(delay)
        raise last_err  # type: ignore[misc]

    def _build_result(self, content: str, file_name: str, page_num: int,
                      method: str, text_fallback: str = None) -> ExtractionResult:
        raw_text = None
        try:
            data = parse_llm_json(content)
            if isinstance(data.get("standards"), str):
                parts = re.split(r"[,;|]", data["standards"])
                data["standards"] = [p.strip() for p in parts if p.strip()] or None

            for key in ["product_model", "manufacturer", "product_name", "issuing_authority",
                        "certification_type", "country", "language"]:
                if isinstance(data.get(key), list):
                    data[key] = ", ".join(str(v) for v in data[key] if v)

            cert_info = CertificateInfo(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            cert_info = CertificateInfo()
            raw_text = text_fallback

        has_number = cert_info.certificate_number is not None
        confidence = 0.9 if has_number else 0.5
        if method == "vision":
            confidence = 0.85 if has_number else 0.4

        return ExtractionResult(
            file_name=file_name,
            page_number=page_num,
            extraction_method=method,
            confidence=confidence,
            data=cert_info,
            raw_text=raw_text or (content[:500] if method == "text" else None),
        )

    def _build_prompt(self, is_image: bool = False) -> str:
        """Build extraction prompt based on configured fields"""
        fields = get_extraction_fields()

        if not fields:
            if is_image:
                return """Extract certificate information from this certificate image. Return JSON with these fields:
- certificate_number
- product_name
- product_model
- manufacturer
- issuing_authority
- issue_date
- expiry_date
- certification_type (e.g., 3C, CE, FCC, UL)
- standards (list of applicable standards)
- country
- language

Pay attention to text in logos, stamps, seals, and tables. If a field is not found, use null.
Return only a single JSON object, no markdown or extra commentary."""
            else:
                return """Extract certificate information from this text. Return JSON with these fields:
- certificate_number
- product_name
- product_model
- manufacturer
- issuing_authority
- issue_date
- expiry_date
- certification_type (e.g., 3C, CE, FCC, UL)
- standards (list of applicable standards)
- country
- language

If a field is not found, use null. Be precise with dates and numbers.
Return only a single JSON object, no markdown or extra commentary."""

        field_lines = []
        for field_name, field_config in fields.items():
            desc = field_config.get("description", "")
            required = field_config.get("required", False)
            field_type = field_config.get("type", "string")
            type_str = " (list)" if field_type == "list" else ""
            required_str = " (required)" if required else ""
            field_lines.append(f"- {field_name}{type_str}{required_str}: {desc}")

        fields_desc = "\n".join(field_lines)

        if is_image:
            return f"""Extract certificate information from this certificate image. Return JSON with these fields:
{fields_desc}

Pay attention to text in logos, stamps, seals, and tables. If a field is not found, use null.
Return only a single JSON object, no markdown or extra commentary."""
        else:
            return f"""Extract certificate information from this text. Return JSON with these fields:
{fields_desc}

If a field is not found, use null. Be precise with dates and numbers.
Return only a single JSON object, no markdown or extra commentary."""

    def extract_from_text(self, text: str, file_name: str, page_num: int) -> ExtractionResult:
        prompt = self._build_prompt(is_image=False) + f"\n\nText:\n{text}"

        try:
            if self.provider == "anthropic":
                response = self._retry_llm(
                    "extract_from_text",
                    lambda: self.client.messages.create(
                        model=self.model,
                        max_tokens=1024,
                        temperature=0,
                        messages=[{"role": "user", "content": prompt}],
                    ),
                )
                content = self._extract_text_from_response(response)
            else:
                response = self._retry_llm(
                    "extract_from_text",
                    lambda: self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                    ),
                )
                content = response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM text extraction failed: {e}")
            return ExtractionResult(
                file_name=file_name, page_number=page_num,
                extraction_method="text", confidence=0.0,
                data=CertificateInfo(), raw_text=text[:500],
            )

        return self._build_result(content, file_name, page_num, "text", text[:500])

    def extract_from_image(self, image_base64: str, file_name: str, page_num: int) -> ExtractionResult:
        prompt = self._build_prompt(is_image=True)

        try:
            if self.provider == "anthropic":
                response = self._retry_llm(
                    "extract_from_image",
                    lambda: self.client.messages.create(
                        model=self.vision_model,
                        max_tokens=1024,
                        temperature=0,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_base64,
                                    },
                                },
                            ],
                        }],
                    ),
                )
                content = self._extract_text_from_response(response)
            else:
                response = self._retry_llm(
                    "extract_from_image",
                    lambda: self.vision_client.chat.completions.create(
                        model=self.vision_model,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                            ],
                        }],
                        temperature=0,
                    ),
                )
                content = response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM vision extraction failed: {e}")
            return ExtractionResult(
                file_name=file_name, page_number=page_num,
                extraction_method="vision", confidence=0.0,
                data=CertificateInfo(),
            )

        return self._build_result(content, file_name, page_num, "vision")
