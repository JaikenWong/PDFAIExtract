from pydantic import BaseModel
from typing import Optional, List


class CertificateInfo(BaseModel):
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
