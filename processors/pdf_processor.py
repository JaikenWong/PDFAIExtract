import fitz
import base64
from typing import Tuple, Optional, Iterator
import logging

logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(
        self,
        dpi: int = 150,
        min_text_length: int = 100,
        min_text_alpha_ratio: float = 0.22,
    ):
        self.dpi = dpi
        self.min_text_length = min_text_length
        self.min_text_alpha_ratio = min_text_alpha_ratio

    def extract_text(self, pdf_path: str, page_num: int) -> str:
        try:
            with fitz.open(pdf_path) as doc:
                if page_num >= len(doc):
                    raise ValueError(f"Page {page_num} out of range (total: {len(doc)})")
                page = doc[page_num]
                text = page.get_text()
                return text.strip()
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path} page {page_num}: {e}")
            return ""

    @staticmethod
    def meaningful_char_ratio(text: str) -> float:
        clean = "".join(text.split())
        if not clean:
            return 0.0
        meaningful = 0
        for c in clean:
            if c.isalnum():
                meaningful += 1
            elif "\u4e00" <= c <= "\u9fff":
                meaningful += 1
        return meaningful / len(clean)

    def is_text_sufficient(self, text: str) -> bool:
        clean = "".join(text.split())
        if len(clean) < self.min_text_length:
            return False
        return self.meaningful_char_ratio(text) >= self.min_text_alpha_ratio

    def page_to_image_base64(self, pdf_path: str, page_num: int) -> Optional[str]:
        try:
            with fitz.open(pdf_path) as doc:
                if page_num >= len(doc):
                    raise ValueError(f"Page {page_num} out of range")
                page = doc[page_num]
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                base64_str = base64.b64encode(img_data).decode()
                return base64_str
        except Exception as e:
            logger.error(f"Failed to render page {page_num} to image: {e}")
            return None

    def get_page_count(self, pdf_path: str) -> int:
        try:
            with fitz.open(pdf_path) as doc:
                return len(doc)
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path}: {e}")
            return 0

    def extract_all_pages(self, pdf_path: str) -> Iterator[Tuple[int, str, Optional[str]]]:
        try:
            with fitz.open(pdf_path) as doc:
                total_pages = len(doc)
                logger.info(f"Processing {pdf_path}: {total_pages} pages")

                for page_num in range(total_pages):
                    page = doc[page_num]
                    text = page.get_text().strip()
                    image_base64 = None

                    if not self.is_text_sufficient(text):
                        logger.debug(f"Page {page_num + 1}: text insufficient, rendering image")
                        mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                        pix = page.get_pixmap(matrix=mat)
                        img_data = pix.tobytes("png")
                        image_base64 = base64.b64encode(img_data).decode()

                    yield page_num + 1, text, image_base64
        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_path}: {e}")
            raise