from app.services.ingestion_service import SUPPORTED_EXTENSIONS, extract_text


def test_markdown_uses_utf8_text_extractor():
    markdown = "# Installation\n\nRun `npm install`.\n"

    assert ".md" in SUPPORTED_EXTENSIONS
    assert extract_text("guide.md", markdown.encode("utf-8")) == markdown.strip()
