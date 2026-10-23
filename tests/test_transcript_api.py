import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests

with patch.dict(
    os.environ,
    {
        "GOOGLE_API_KEY": "unit-test-key",
        "GROQ_API_KEY": "unit-test-key",
    },
):
    from rag import main


class TranscriptApiTests(unittest.TestCase):
    def setUp(self):
        self.response = Mock(status_code=200)
        self.response.headers = {}

    def retrieve(self, payload):
        self.response.json.return_value = payload
        with patch.dict(os.environ, {"TRANSCRIPT_API_KEY": "unit-test-transcript-key"}), patch.object(
            main.requests, "get", return_value=self.response
        ) as get:
            transcript = main.get_transcript("RE3_PGwDwhw")
        return transcript, get

    def test_retrieves_and_normalizes_caption_segments(self):
        transcript, get = self.retrieve({
            "video_id": "RE3_PGwDwhw",
            "language": "en",
            "transcript": [
                {"text": "  Example\u200b   caption ", "start": 0, "duration": 2.5},
                {"text": "Another\ncaption", "start": 2.5, "duration": 3},
            ],
        })

        self.assertEqual(transcript, "Example caption Another caption")
        get.assert_called_once_with(
            main.TRANSCRIPT_API_URL,
            params={"video_url": "RE3_PGwDwhw", "format": "json"},
            headers={"Authorization": "Bearer unit-test-transcript-key"},
            timeout=30,
        )

    def test_retrieves_and_normalizes_string_transcript(self):
        transcript, _ = self.retrieve({"transcript": "  Hello\n  world  "})
        self.assertEqual(transcript, "Hello world")

    def test_missing_api_key_fails_before_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(main.requests, "get") as get:
            with self.assertRaises(main.TranscriptFetchError) as raised:
                main.get_transcript("RE3_PGwDwhw")

        self.assertEqual(raised.exception.category, "transcript_api_not_configured")
        self.assertEqual(raised.exception.status_code, 500)
        get.assert_not_called()

    def test_provider_statuses_have_safe_actionable_messages(self):
        cases = [
            (401, "transcript_api_auth", "Check TRANSCRIPT_API_KEY"),
            (402, "transcript_api_credits", "no credits remaining"),
            (404, "transcript_unavailable", "No transcript is available"),
            (422, "transcript_invalid_video", "rejected the supplied YouTube"),
            (408, "transcript_provider_timeout", "temporarily timed out"),
            (500, "transcript_provider_failure", "encountered an error"),
            (503, "transcript_provider_failure", "unexpected error"),
        ]
        for status, category, message_part in cases:
            with self.subTest(status=status):
                self.response.status_code = status
                self.response.text = "provider body must not escape"
                with patch.dict(os.environ, {"TRANSCRIPT_API_KEY": "test-key"}), patch.object(
                    main.requests, "get", return_value=self.response
                ):
                    with self.assertRaises(main.TranscriptFetchError) as raised:
                        main.get_transcript("RE3_PGwDwhw")
                self.assertEqual(raised.exception.category, category)
                self.assertIn(message_part, str(raised.exception))
                self.assertNotIn("provider body", str(raised.exception))

    def test_rate_limit_includes_retry_after_or_safe_default(self):
        self.response.status_code = 429
        self.response.headers = {"Retry-After": "12"}
        with patch.dict(os.environ, {"TRANSCRIPT_API_KEY": "test-key"}), patch.object(
            main.requests, "get", return_value=self.response
        ):
            with self.assertRaises(main.TranscriptFetchError) as raised:
                main.get_transcript("RE3_PGwDwhw")
        self.assertEqual(raised.exception.category, "transcript_api_rate_limited")
        self.assertIn("retry in 12 seconds", str(raised.exception))

        self.response.headers = {"Retry-After": "not-a-number"}
        with patch.dict(os.environ, {"TRANSCRIPT_API_KEY": "test-key"}), patch.object(
            main.requests, "get", return_value=self.response
        ):
            with self.assertRaises(main.TranscriptFetchError) as raised:
                main.get_transcript("RE3_PGwDwhw")
        self.assertIn("retry in 5 seconds", str(raised.exception))

    def test_provider_timeout_and_connection_errors_are_safe(self):
        cases = [
            (requests.Timeout("private transport details"), "transcript_provider_timeout"),
            (requests.ConnectionError("private transport details"), "transcript_provider_connection"),
        ]
        for error, category in cases:
            with self.subTest(category=category), patch.dict(
                os.environ, {"TRANSCRIPT_API_KEY": "test-key"}
            ), patch.object(main.requests, "get", side_effect=error):
                with self.assertRaises(main.TranscriptFetchError) as raised:
                    main.get_transcript("RE3_PGwDwhw")
                self.assertEqual(raised.exception.category, category)
                self.assertNotIn("private transport details", str(raised.exception))

    def test_invalid_json_and_unexpected_shapes_fail_clearly(self):
        invalid_json = Mock(status_code=200)
        invalid_json.json.side_effect = ValueError("raw decoder detail")
        malformed_payloads = [
            [],
            {"transcript": None},
            {"transcript": [{"start": 0, "duration": 2}]},
            {"transcript": "   "},
            {"transcript": []},
        ]
        responses = [invalid_json] + [
            Mock(status_code=200, **{"json.return_value": payload})
            for payload in malformed_payloads
        ]
        for response in responses:
            with patch.dict(os.environ, {"TRANSCRIPT_API_KEY": "test-key"}), patch.object(
                main.requests, "get", return_value=response
            ):
                with self.assertRaises(main.TranscriptFetchError) as raised:
                    main.get_transcript("RE3_PGwDwhw")
            self.assertIn(raised.exception.category, {
                "transcript_invalid_json",
                "transcript_invalid_response",
                "transcript_empty",
            })

    def test_rag_pipeline_chunks_normalized_string(self):
        splitter = Mock()
        splitter.create_documents.return_value = ["document"]
        vector_store = Mock()
        main.vector_store_cache.clear()

        with patch.object(main, "get_transcript", return_value="first part second part"), patch.object(
            main, "RecursiveCharacterTextSplitter", return_value=splitter
        ), patch.object(main.Chroma, "from_documents", return_value=vector_store):
            result = main.create_vector_store("RE3_PGwDwhw")

        self.assertIs(result, vector_store)
        splitter.create_documents.assert_called_once_with(["first part second part"])

    def test_normal_retrieval_has_no_youtube_transcript_api_dependency(self):
        self.assertFalse(hasattr(main, "YouTubeTranscriptApi"))
        requirements = Path("requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("youtube-transcript-api", requirements)


if __name__ == "__main__":
    unittest.main()
