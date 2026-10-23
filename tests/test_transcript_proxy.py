import logging
import os
import unittest
from unittest.mock import Mock, patch

from requests.exceptions import ProxyError
from youtube_transcript_api._errors import (
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

with patch.dict(
    os.environ,
    {"GOOGLE_API_KEY": "unit-test-key", "GROQ_API_KEY": "unit-test-key"},
):
    from rag import main


class TranscriptProxyTests(unittest.TestCase):
    def test_client_uses_direct_mode_when_proxy_is_blank(self):
        with patch.dict(os.environ, {"TRANSCRIPT_PROXY_URL": ""}), patch.object(
            main, "YouTubeTranscriptApi"
        ) as api_class:
            main.create_transcript_api()

        api_class.assert_called_once_with()

    def test_client_uses_configured_proxy_for_http_and_https(self):
        proxy_url = "http://proxy-user:proxy-password@proxy.example:8080"
        with patch.dict(os.environ, {"TRANSCRIPT_PROXY_URL": proxy_url}), patch.object(
            main, "YouTubeTranscriptApi"
        ) as api_class, patch.object(main, "GenericProxyConfig") as proxy_config:
            main.create_transcript_api()

        proxy_config.assert_called_once_with(http_url=proxy_url, https_url=proxy_url)
        api_class.assert_called_once_with(proxy_config=proxy_config.return_value)

    def test_transcript_keeps_existing_cleaned_snippet_format(self):
        api = Mock()
        api.fetch.return_value.to_raw_data.return_value = [
            {"text": "  Hello\u200b   world ", "start": 1.25, "duration": 2.5}
        ]
        with patch.object(main, "create_transcript_api", return_value=api):
            result = main.get_transcript("RE3_PGwDwhw")

        api.fetch.assert_called_once_with("RE3_PGwDwhw", languages=["en"])
        self.assertEqual(
            result,
            [{"text": "Hello world", "start": 1.25, "duration": 2.5}],
        )

    def test_rag_pipeline_joins_existing_snippet_text_for_chunking(self):
        snippets = [
            {"text": "first part", "start": 0.0, "duration": 1.0},
            {"text": "second part", "start": 1.0, "duration": 1.0},
        ]
        splitter = Mock()
        splitter.create_documents.return_value = ["document"]
        vector_store = Mock()
        main.vector_store_cache.clear()

        with patch.object(main, "get_transcript", return_value=snippets), patch.object(
            main, "RecursiveCharacterTextSplitter", return_value=splitter
        ), patch.object(main.Chroma, "from_documents", return_value=vector_store):
            result = main.create_vector_store("RE3_PGwDwhw")

        self.assertIs(result, vector_store)
        splitter.create_documents.assert_called_once_with(["first part second part"])

    def test_proxy_authentication_error_is_sanitized_in_logs(self):
        secret_url = "http://private-user:private-password@proxy.example:8080"
        error = ProxyError(
            f"Tunnel failed for {secret_url}: 407 Proxy Authentication Required"
        )
        with self.assertLogs(main.logger, level=logging.WARNING) as logs:
            with patch.object(main, "create_transcript_api", side_effect=error):
                with self.assertRaises(main.TranscriptFetchError) as raised:
                    main.get_transcript("RE3_PGwDwhw")

        self.assertEqual(raised.exception.category, "proxy_authentication")
        self.assertIn("proxy_authentication", " ".join(logs.output))
        self.assertNotIn("private-user", " ".join(logs.output))
        self.assertNotIn("private-password", " ".join(logs.output))
        self.assertNotIn(secret_url, " ".join(logs.output))

    def test_youtube_ip_block_is_reported_as_a_safe_category(self):
        with self.assertLogs(main.logger, level=logging.WARNING) as logs:
            with patch.object(
                main, "create_transcript_api", side_effect=IpBlocked("RE3_PGwDwhw")
            ):
                with self.assertRaises(main.TranscriptFetchError) as raised:
                    main.get_transcript("RE3_PGwDwhw")

        self.assertEqual(raised.exception.category, "youtube_ip_blocked")
        self.assertIn("proxy IP may also be blocked", " ".join(logs.output))

    def test_common_transcript_errors_have_distinct_categories(self):
        cases = [
            (TranscriptsDisabled("RE3_PGwDwhw"), "captions_disabled"),
            (NoTranscriptFound("RE3_PGwDwhw", ["en"], Mock()), "transcript_missing"),
            (InvalidVideoId("bad-id"), "invalid_video_id"),
            (VideoUnavailable("RE3_PGwDwhw"), "video_unavailable"),
            (RuntimeError("unexpected"), "transcript_api_failure"),
        ]
        for error, category in cases:
            with self.subTest(category=category), patch.object(
                main, "create_transcript_api", side_effect=error
            ), self.assertRaises(main.TranscriptFetchError) as raised:
                main.get_transcript("RE3_PGwDwhw")
            self.assertEqual(raised.exception.category, category)


if __name__ == "__main__":
    unittest.main()
