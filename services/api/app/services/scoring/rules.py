from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringRuleDefinition:
    key: str
    label: str
    points: int
    description: str


SCORING_RULES: list[ScoringRuleDefinition] = [
    ScoringRuleDefinition(
        key="target_role_match",
        label="Target role match",
        points=25,
        description="Lead job title matches a niche target role",
    ),
    ScoringRuleDefinition(
        key="niche_keyword_match",
        label="Niche keyword match",
        points=30,
        description="Lead or company text matches a niche keyword",
    ),
    ScoringRuleDefinition(
        key="company_website_exists",
        label="Company website exists",
        points=10,
        description="Linked company has a website URL",
    ),
    ScoringRuleDefinition(
        key="public_email_found",
        label="Public email found",
        points=20,
        description="Lead has a non-generic public email contact",
    ),
    ScoringRuleDefinition(
        key="company_size_match",
        label="Company size match",
        points=15,
        description="Company size estimate falls within niche range",
    ),
    ScoringRuleDefinition(
        key="generic_email_only",
        label="Generic email only",
        points=5,
        description="Lead only has a generic inbox email (info@, contact@)",
    ),
    ScoringRuleDefinition(
        key="no_website",
        label="No website",
        points=-20,
        description="Linked company has no website",
    ),
    ScoringRuleDefinition(
        key="exclusion_keyword",
        label="Exclusion keyword found",
        points=-30,
        description="Lead or company text matches an exclusion keyword",
    ),
    ScoringRuleDefinition(
        key="opted_out",
        label="Opted out",
        points=0,
        description="Contact opted out — score set to 0 and status opted_out",
    ),
]

RULES_BY_KEY = {rule.key: rule for rule in SCORING_RULES}
