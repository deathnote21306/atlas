from atlas_api.services.news.nlp import classify_event, extract_country, is_relevant


def test_extract_country_finds_ghana():
    assert extract_country("Ghana GDP growth slows", "The economy of Ghana...") == "GHA"


def test_extract_country_finds_cote_divoire():
    assert extract_country("Côte d'Ivoire bond issuance", "...") == "CIV"


def test_extract_country_returns_none_for_unknown():
    assert extract_country("Weather in Mars", "Space news") is None


def test_is_relevant_true_for_sovereign():
    assert is_relevant("IMF approves Ghana debt restructuring", "The fiscal deficit...") is True


def test_is_relevant_false_for_sports():
    assert is_relevant("Ghana wins football match", "The Black Stars scored...") is False


def test_classify_event_fiscal():
    assert classify_event("Budget deficit widens in Kenya", "Fiscal spending...") == "Fiscal"


def test_classify_event_rating():
    assert classify_event("S&P downgrades Nigeria", "Credit rating action...") == "Rating"


def test_classify_event_imf():
    assert classify_event("IMF completes review of Ethiopia program", "Disbursement...") == "IMF"


def test_classify_event_political():
    assert classify_event("Election results in Senegal", "The new president...") == "Political"
