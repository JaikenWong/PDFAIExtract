from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any, Union
from config import get_config

# Runtime override holder
_RUNTIME_FIELDS: Optional[Dict[str, Any]] = None


def normalize_fields(fields: Union[List[str], Dict[str, Any], None]) -> Dict[str, Any]:
    """Normalize various field input formats to canonical dict.

    Accept:
    - list of str: ["证书编号", "产品名称"]  -> field name auto-gen
    - list of dict: [{"name": "serial", "desc": "序列号"}]
    - dict simple: {"serial": "序列号", "model": "型号"}
    - dict full: {"serial": {"description": "序列号", "required": True, "type": "string"}}
    """
    if not fields:
        return {}

    result = {}
    if isinstance(fields, list):
        for item in fields:
            if isinstance(item, str):
                # str = description, auto-gen name
                key = item.strip().replace(" ", "_").lower()
                result[key] = {"description": item, "required": False}
            elif isinstance(item, dict):
                name = item.get("name") or item.get("key")
                if not name:
                    continue
                result[name] = {
                    "description": item.get("description") or item.get("desc", ""),
                    "required": item.get("required", False),
                    "type": item.get("type", "string"),
                }
    elif isinstance(fields, dict):
        for name, val in fields.items():
            if isinstance(val, str):
                result[name] = {"description": val, "required": False}
            elif isinstance(val, dict):
                result[name] = {
                    "description": val.get("description", ""),
                    "required": val.get("required", False),
                    "type": val.get("type", "string"),
                }
    return result


def get_extraction_fields() -> Dict[str, Any]:
    """Runtime override > config fields"""
    if _RUNTIME_FIELDS is not None:
        return _RUNTIME_FIELDS
    return get_config().get("extraction", {}).get("fields", {})


def set_extraction_fields(fields: Union[List[str], Dict[str, Any], None]):
    """Set runtime field override. None to clear."""
    global _RUNTIME_FIELDS
    _RUNTIME_FIELDS = normalize_fields(fields) if fields else None


class CertificateInfo(BaseModel):
    """Flexible schema. Default fields + allow extra for runtime config."""
    model_config = ConfigDict(extra="allow")

    certificate_number: Optional[str] = None
    product_name: Optional[str] = None
    product_model: Optional[str] = None
    manufacturer: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    certification_type: Optional[str] = None
    standards: Optional[List[str]] = None
    country: Optional[str] = None
    language: Optional[str] = None
    additional_info: Optional[dict] = None


class ExtractionResult(BaseModel):
    file_name: str
    page_number: int
    extraction_method: str
    confidence: float
    data: CertificateInfo
    raw_text: Optional[str] = None
