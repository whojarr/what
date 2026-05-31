from civsim.ai.text_normalize import normalize_invention_text


def test_cjarcoa_maps_to_charcoal():
    text, note = normalize_invention_text("cjarcoa")
    assert "charcoal" in text.lower()
    assert note is not None


def test_charcoal_unchanged():
    text, note = normalize_invention_text("charcoal")
    assert text == "charcoal"
    assert note is None
