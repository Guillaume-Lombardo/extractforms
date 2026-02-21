"""Extraction backends."""

from extractforms.backends.multimodal_openai import MultimodalLLMBackend
from extractforms.backends.ocr_document_intelligence import OCRBackend
from extractforms.backends.ocr_text_normalizer import OCRTextLLMNormalizer
from extractforms.typing.protocol import ExtractorBackend, PageSource

__all__ = [
    "ExtractorBackend",
    "MultimodalLLMBackend",
    "OCRBackend",
    "OCRTextLLMNormalizer",
    "PageSource",
]
