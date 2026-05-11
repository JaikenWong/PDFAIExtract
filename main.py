import os
import json
import logging
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from processors.pdf_processor import PDFProcessor
from extractors.llm_extractor import LLMExtractor
from models.schemas import CertificateInfo, ExtractionResult
from config import load_config

logger = logging.getLogger(__name__)


class CertificateExtractor:
    def __init__(self, config_path: str = None):
        cfg = load_config(config_path)
        llm_cfg = cfg["llm"]
        ext_cfg = cfg["extraction"]
        self.pdf_processor = PDFProcessor(dpi=ext_cfg.get("dpi", 150),
                                          min_text_length=ext_cfg.get("min_text_length", 100))
        self.llm_extractor = LLMExtractor()
        self.max_workers = ext_cfg.get("concurrent_workers", 4)

    def _process_page(self, page_num: int, text: str, image_base64: str, 
                      file_name: str) -> ExtractionResult:
        try:
            if self.pdf_processor.is_text_sufficient(text):
                result = self.llm_extractor.extract_from_text(text, file_name, page_num)
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

    def process_pdf(self, pdf_path: str) -> List[ExtractionResult]:
        file_name = os.path.basename(pdf_path)
        pages = list(self.pdf_processor.extract_all_pages(pdf_path))
        total = len(pages)
        print(f"Processing {total} pages with {self.max_workers} workers...")

        results = [None] * total
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, (page_num, text, image_base64) in enumerate(pages):
                future = executor.submit(
                    self._process_page, page_num, text, image_base64, file_name
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
