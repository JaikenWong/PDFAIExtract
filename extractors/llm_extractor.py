import json
import re
import logging

from anthropic import Anthropic
from openai import OpenAI
from models.schemas import CertificateInfo, ExtractionResult
from config import get_config

logger = logging.getLogger(__name__)


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
        elif self.provider in {"openai", "azure_openai"}:
            combined_key = f"{api_key}:{api_secret}" if api_secret else api_key
            self.client = OpenAI(api_key=combined_key or None, base_url=cfg.get("base_url") or None)
            
            vision_key = cfg.get("vision_api_key") or combined_key
            vision_url = cfg.get("vision_base_url") or cfg.get("base_url")
            vision_model_id = cfg.get("vision_model_id") or self.vision_model
            self.vision_client = OpenAI(api_key=vision_key or None, base_url=vision_url or None)
            self.vision_model = vision_model_id
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

    def _build_result(self, content: str, file_name: str, page_num: int,
                      method: str, text_fallback: str = None) -> ExtractionResult:
        raw_text = None
        try:
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {}
            
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

    def extract_from_text(self, text: str, file_name: str, page_num: int) -> ExtractionResult:
        prompt = f"""Extract certificate information from this text. Return JSON with these fields:
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

Text:
{text}"""

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = self._extract_text_from_response(response)
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM text extraction failed: {e}")
            return ExtractionResult(
                file_name=file_name, page_number=page_num,
                extraction_method="text", confidence=0.0,
                data=CertificateInfo(), raw_text=text[:500],
            )

        return self._build_result(content, file_name, page_num, "text", text[:500])

    def extract_from_image(self, image_base64: str, file_name: str, page_num: int) -> ExtractionResult:
        prompt = """Extract certificate information from this certificate image. Return JSON with these fields:
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

Pay attention to text in logos, stamps, seals, and tables. If a field is not found, use null."""

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
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
                )
                content = self._extract_text_from_response(response)
            else:
                response = self.vision_client.chat.completions.create(
                    model=self.vision_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                        ],
                    }],
                    temperature=0,
                )
                content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM vision extraction failed: {e}")
            return ExtractionResult(
                file_name=file_name, page_number=page_num,
                extraction_method="vision", confidence=0.0,
                data=CertificateInfo(),
            )

        return self._build_result(content, file_name, page_num, "vision")
