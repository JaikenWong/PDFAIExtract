import base64
import binascii
import os
import tempfile
import logging
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from main import CertificateExtractor
from config import get_config, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF Certificate Extractor API",
    description="Extract structured information from certificate PDFs using LLM",
    version="1.0.0",
)

extractor = None


def get_extractor() -> CertificateExtractor:
    global extractor
    if extractor is None:
        extractor = CertificateExtractor()
    return extractor


def _max_upload_bytes() -> int:
    return int(get_config().get("extraction", {}).get("max_upload_bytes", 52428800))


class ExtractResult(BaseModel):
    file_name: str
    page_number: int
    extraction_method: str
    confidence: float
    data: dict
    raw_text: Optional[str] = None


class ExtractResponse(BaseModel):
    success: bool
    results: List[ExtractResult]
    error: Optional[str] = None


class ExtractBase64Request(BaseModel):
    filename: str = Field(..., description="Original PDF filename (for logging / display)")
    content_base64: str = Field(..., description="PDF file bytes encoded as standard base64")


@app.post("/extract", response_model=ExtractResponse)
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    limit = _max_upload_bytes()
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content)} bytes (max {limit})",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ext = get_extractor()
        results = ext.process_pdf(tmp_path, display_name=file.filename)
        return ExtractResponse(
            success=True,
            results=[ExtractResult(**r.model_dump()) for r in results],
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractResponse(success=False, results=[], error=str(e))
    finally:
        if os.path.isfile(tmp_path):
            os.unlink(tmp_path)


@app.post("/extract/base64", response_model=ExtractResponse)
async def extract_pdf_base64(body: ExtractBase64Request):
    if "." in body.filename and not body.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        pdf_bytes = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}") from e

    limit = _max_upload_bytes()
    if len(pdf_bytes) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(pdf_bytes)} bytes (max {limit})",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        ext = get_extractor()
        results = ext.process_pdf(tmp_path, display_name=body.filename)
        return ExtractResponse(
            success=True,
            results=[ExtractResult(**r.model_dump()) for r in results],
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractResponse(success=False, results=[], error=str(e))
    finally:
        if os.path.isfile(tmp_path):
            os.unlink(tmp_path)


@app.get("/health")
async def health():
    return {"status": "ok"}
