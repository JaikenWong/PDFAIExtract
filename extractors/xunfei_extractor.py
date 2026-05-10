import base64
import json
import logging
import re
import requests
from models.schemas import CertificateInfo, ExtractionResult
from config import get_config

logger = logging.getLogger(__name__)

_API_TIMEOUT = 60


class XunfeiExtractor:
    def __init__(self):
        cfg = get_config()["llm"]
        self.api_key = cfg.get("api_key", "")
        self.api_secret = cfg.get("api_secret", "")
        self.base_url = cfg.get("base_url", "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2")
        self.model = cfg.get("model", "astron-code-latest")

    def _get_headers(self):
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        return {
            "Authorization": f"Bearer {auth_base64}",
            "Content-Type": "application/json",
        }

    def _call_api(self, payload: dict) -> str:
        url = f"{self.base_url}/chat/completions"
        resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=_API_TIMEOUT)
        logger.debug(f"API response status: {resp.status_code}")
        try:
            result = resp.json()
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return resp.text

    def _build_result(self, content: str, file_name: str, page_num: int,
                      method: str, text_fallback: str = None) -> ExtractionResult:
        raw_text = None
        try:
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {}
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
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
            content = self._call_api(payload)
        except requests.RequestException as e:
            logger.error(f"API call failed: {e}")
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
            payload = {
                "model": self.model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                    ],
                }],
                "temperature": 0,
            }
            content = self._call_api(payload)
        except requests.RequestException as e:
            logger.error(f"API call failed: {e}")
            return ExtractionResult(
                file_name=file_name, page_number=page_num,
                extraction_method="vision", confidence=0.0,
                data=CertificateInfo(),
            )

        return self._build_result(content, file_name, page_num, "vision")