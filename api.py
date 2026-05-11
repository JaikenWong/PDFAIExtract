import os
import tempfile
import logging
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from main import CertificateExtractor
from config import load_config, setup_logging

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


@app.post("/extract", response_model=ExtractResponse)
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ext = get_extractor()
        results = ext.process_pdf(tmp_path)
        return ExtractResponse(
            success=True,
            results=[ExtractResult(**r.model_dump()) for r in results],
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractResponse(success=False, results=[], error=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/extract/base64", response_model=ExtractResponse)
async def extract_pdf_base64(data: BaseModel):
    import base64

    class Request(BaseModel):
        filename: str
        content_base64: str

    req = Request(**data.model_dump())

    pdf_bytes = base64.b64decode(req.content_base64)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        ext = get_extractor()
        results = ext.process_pdf(tmp_path)
        return ExtractResponse(
            success=True,
            results=[ExtractResult(**r.model_dump()) for r in results],
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractResponse(success=False, results=[], error=str(e))
    finally:
        os.unlink(tmp_path)


@app.get("/health")
async def health():
    return {"status": "ok"}
