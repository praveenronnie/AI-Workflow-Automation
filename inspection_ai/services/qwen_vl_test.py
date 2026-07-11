"""
Tests for QwenVL wrapper class.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from inspection_ai.services.qwen_vl import QwenVL


class TestQwenVL:
    def test_init_loads_model(self):
        with patch(
            "inspection_ai.services.qwen_vl.Qwen2_5_VLForConditionalGeneration.from_pretrained"
        ) as mock_model:
            with patch(
                "inspection_ai.services.qwen_vl.AutoProcessor.from_pretrained"
            ) as mock_processor:
                mock_model.return_value = MagicMock()
                mock_processor.return_value = MagicMock()

                qwen = QwenVL()

                assert qwen.model is not None
                assert qwen.processor is not None

    def test_analyze_image_success(self):
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_processor.apply_chat_template.return_value = "test_prompt"
        mock_processor.return_value = MagicMock()
        mock_processor.batch_decode.return_value = [
            '{"room": "kitchen", "category": "interior", "confidence": 0.9}'
        ]

        with patch(
            "inspection_ai.services.qwen_vl.Qwen2_5_VLForConditionalGeneration.from_pretrained",
            return_value=mock_model,
        ):
            with patch(
                "inspection_ai.services.qwen_vl.AutoProcessor.from_pretrained",
                return_value=mock_processor,
            ):
                with patch(
                    "inspection_ai.services.qwen_vl.process_vision_info"
                ) as mock_vision:
                    mock_vision.return_value = (MagicMock(), MagicMock())

                    qwen = QwenVL()
                    result = qwen.analyze_image("test.jpg", "test prompt")

                    assert result["success"] is True
                    assert result["data"]["room"] == "kitchen"
                    assert result["data"]["category"] == "interior"

    def test_analyze_image_json_parsing_failure(self):
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_processor.apply_chat_template.return_value = "test_prompt"
        mock_processor.return_value = MagicMock()
        mock_processor.batch_decode.return_value = ["invalid json response"]

        with patch(
            "inspection_ai.services.qwen_vl.Qwen2_5_VLForConditionalGeneration.from_pretrained",
            return_value=mock_model,
        ):
            with patch(
                "inspection_ai.services.qwen_vl.AutoProcessor.from_pretrained",
                return_value=mock_processor,
            ):
                with patch(
                    "inspection_ai.services.qwen_vl.process_vision_info"
                ) as mock_vision:
                    mock_vision.return_value = (MagicMock(), MagicMock())

                    qwen = QwenVL()
                    result = qwen.analyze_image("test.jpg", "test prompt")

                    assert result["success"] is False
                    assert "error" in result

    def test_normalize_response_removes_code_fences(self):
        qwen = QwenVL.__new__(QwenVL)

        response = '```json\n{"room": "kitchen"}\n```'
        normalized = qwen._normalize_response(response)

        assert normalized == '{"room": "kitchen"}'

    def test_normalize_response_extracts_json(self):
        qwen = QwenVL.__new__(QwenVL)

        response = 'Some text before {"room": "kitchen"} some text after'
        normalized = qwen._normalize_response(response)

        assert normalized == '{"room": "kitchen"}'
