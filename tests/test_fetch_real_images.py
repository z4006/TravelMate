from scripts.fetch_real_images import IMAGE_SUFFIX, PLACEHOLDER_URL


def test_image_validation_rules():
    assert IMAGE_SUFFIX.search("https://example.test/photo.JPG")
    assert IMAGE_SUFFIX.search("https://example.test/photo.png")
    assert not IMAGE_SUFFIX.search("https://example.test/photo.png?download=1")
    assert not IMAGE_SUFFIX.search("https://example.test/photo.webp")
    assert PLACEHOLDER_URL.endswith(".svg")
