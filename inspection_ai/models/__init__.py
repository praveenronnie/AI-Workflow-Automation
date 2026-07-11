"""
Models package for AI Inspection Report Automation.
Contains DTO definitions and Qwen model wrapper.
"""

from .dto import FieldDTO, ProcessingStep, DocumentOutput, ImageOutput, MappingOutput

__all__ = [
    "FieldDTO",
    "ProcessingStep",
    "DocumentOutput",
    "ImageOutput",
    "MappingOutput",
]
