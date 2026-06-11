from src.models import SiteMetadata
from src.services.helpers import build_search_text


def test_build_search_text_includes_assessment() -> None:
    text = build_search_text(
        SiteMetadata(
            summary="Payments infrastructure for the internet.",
            sentiment="Polished and trustworthy.",
            site_category="saas-product",
            industry="fintech",
            primary_topics=["payments", "billing"],
            business_model="saas-subscription",
            target_audience="developers",
            content_tone="technical",
            has_public_api=True,
        )
    )
    # The embedded text must carry the agent's prose assessment plus the queryable facets.
    assert "Payments infrastructure for the internet." in text
    assert "Polished and trustworthy." in text
    assert "fintech" in text and "developers" in text
    assert "payments, billing" in text
    assert "Has a public API" in text
