import os
import json
import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from processors.pdf_processor import PDFProcessor
from extractors.llm_extractor import LLMExtractor
from models.schemas import CertificateInfo, ExtractionResult
from config import load_config

logger = logging.getLogger(__name__)

_CORE_FIELDS = (
    "certificate_number",
    "product_name",
    "product_model",
    "manufacturer",
    "issuing_authority",
)


def _filled_core_count(cert_info) -> int:
    d = cert_info.model_dump()
    return sum(1 for k in _CORE_FIELDS if d.get(k))


class CertificateExtractor:
    def __init__(self, config_path: str = None):
        cfg = load_config(config_path)
        llm_cfg = cfg["llm"]
        ext_cfg = cfg["extraction"]
        self.pdf_processor = PDFProcessor(
            dpi=ext_cfg.get("dpi", 150),
            min_text_length=ext_cfg.get("min_text_length", 100),
            min_text_alpha_ratio=float(ext_cfg.get("min_text_alpha_ratio", 0.22)),
        )
        self.llm_extractor = LLMExtractor()
        self.max_workers = ext_cfg.get("concurrent_workers", 4)
        self.vision_fallback_min_chars = int(ext_cfg.get("vision_fallback_min_chars", 30))

    def _should_retry_with_vision(self, text_result: ExtractionResult, text: str) -> bool:
        if text_result.extraction_method != "text":
            return False
        if text_result.data.certificate_number:
            return False
        clean = "".join(text.split())
        if len(clean) < self.vision_fallback_min_chars:
            return False
        if _filled_core_count(text_result.data) >= 3:
            return False
        return True

    @staticmethod
    def _vision_preferred(text_r: ExtractionResult, vision_r: ExtractionResult) -> bool:
        if vision_r.data.certificate_number and not text_r.data.certificate_number:
            return True
        return _filled_core_count(vision_r.data) > _filled_core_count(text_r.data)

    def _process_page(
        self,
        page_num: int,
        text: str,
        image_base64: Optional[str],
        file_name: str,
        pdf_path: str,
    ) -> ExtractionResult:
        try:
            if self.pdf_processor.is_text_sufficient(text):
                result = self.llm_extractor.extract_from_text(text, file_name, page_num)
                if self._should_retry_with_vision(result, text):
                    img = image_base64 or self.pdf_processor.page_to_image_base64(
                        pdf_path, page_num - 1
                    )
                    if img:
                        vision_result = self.llm_extractor.extract_from_image(
                            img, file_name, page_num
                        )
                        if self._vision_preferred(result, vision_result):
                            result = vision_result
            else:
                if not image_base64:
                    raise ValueError("Missing page image for vision extraction")
                result = self.llm_extractor.extract_from_image(image_base64, file_name, page_num)
            return result
        except Exception as e:
            logger.error(f"Failed to process page {page_num}: {e}")
            return ExtractionResult(
                file_name=file_name, page_number=page_num,
                extraction_method="error", confidence=0.0,
                data=CertificateInfo(),
            )

    def process_pdf(self, pdf_path: str, display_name: Optional[str] = None) -> List[ExtractionResult]:
        file_name = display_name or os.path.basename(pdf_path)
        pages = list(self.pdf_processor.extract_all_pages(pdf_path))
        total = len(pages)
        print(f"Processing {total} pages with {self.max_workers} workers...")

        results = [None] * total
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, (page_num, text, image_base64) in enumerate(pages):
                future = executor.submit(
                    self._process_page,
                    page_num,
                    text,
                    image_base64,
                    file_name,
                    pdf_path,
                )
                futures[future] = idx

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                    print(f"  Page {pages[idx][0]} done ({idx+1}/{total})")
                except Exception as e:
                    logger.error(f"Page {pages[idx][0]} failed: {e}")
                    results[idx] = ExtractionResult(
                        file_name=file_name, page_number=pages[idx][0],
                        extraction_method="error", confidence=0.0,
                        data=CertificateInfo(),
                    )

        return results

    def _check_missing_fields(self, cert_info) -> List[str]:
        missing = []
        for field_name, value in cert_info.model_dump().items():
            if value is None and field_name != "additional_info":
                missing.append(field_name)
        return missing

    def save_results(self, results: List[ExtractionResult], output_path: str):
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        data = [r.model_dump() for r in results]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        for r in results:
            missing = self._check_missing_fields(r.data)
            if missing:
                logger.debug("Page %s missing fields: %s", r.page_number, ", ".join(missing))

        print(f"Results saved to {output_path}")

    def process_directory(self, input_dir: str, output_dir: str = "output"):
        os.makedirs(output_dir, exist_ok=True)

        for filename in os.listdir(input_dir):
            if not filename.lower().endswith(".pdf"):
                continue
            pdf_path = os.path.join(input_dir, filename)
            print(f"\n{'=' * 50}")
            print(f"Processing: {filename}")
            print("=" * 50)

            try:
                results = self.process_pdf(pdf_path)
                output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_extracted.json")
                self.save_results(results, output_path)
            except Exception as e:
                logger.error(f"Skipping {filename} due to error: {e}")
