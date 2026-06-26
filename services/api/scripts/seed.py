"""Database seed script for local development."""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.campaign import Campaign, CampaignStep
from app.models.company import Company
from app.models.email_contact import EmailContact
from app.models.email_message import EmailMessage
from app.models.enums import (
    CampaignStatus,
    EmailMessageStatus,
    EmailType,
    EnrichmentStatus,
    LeadStatus,
    ReplyClassification,
    ReplyStatus,
    SearchProvider,
    SearchStatus,
    UserRole,
)
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.reply import Reply
from app.models.search_query import SearchQuery
from app.models.suppression import Suppression
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.provider_credentials.service import ensure_default_mock_credentials

DEMO_EMAIL = "demo@wellpredict.io"
DEMO_PASSWORD = "demo1234"

SAMPLE_LEADS = [
    {
        "full_name": "Sarah Mitchell",
        "job_title": "Head of Quality",
        "company": "Northern Grain Co",
        "website": "https://northerngrain.co.uk",
        "domain": "northerngrain.co.uk",
        "email": "sarah.mitchell@northerngrain.co.uk",
        "industry": "Food Manufacturing",
        "status": LeadStatus.QUALIFIED,
        "score": 85.0,
    },
    {
        "full_name": "James Patel",
        "job_title": "Compliance Manager",
        "company": "Harbour Foods Ltd",
        "website": "https://harbourfoods.co.uk",
        "domain": "harbourfoods.co.uk",
        "email": "j.patel@harbourfoods.co.uk",
        "industry": "Food Manufacturing",
        "status": LeadStatus.READY_FOR_OUTREACH,
        "score": 90.0,
        "approved_outreach": True,
    },
    {
        "full_name": "Emma Clarke",
        "job_title": "Operations Director",
        "company": "Valley Fresh Produce",
        "website": "https://valleyfreshproduce.com",
        "domain": "valleyfreshproduce.com",
        "email": "emma@valleyfreshproduce.com",
        "industry": "Food Manufacturing",
        "status": LeadStatus.CONTACTED,
        "score": 78.0,
        "sent_outreach": True,
    },
    {
        "full_name": "David Hughes",
        "job_title": "Quality Assurance Lead",
        "company": "Cotswold Dairy",
        "website": "https://cotswolddairy.co.uk",
        "domain": "cotswolddairy.co.uk",
        "email": "david.hughes@cotswolddairy.co.uk",
        "industry": "Food Manufacturing",
        "status": LeadStatus.REPLIED,
        "score": 82.0,
        "sent_outreach": True,
        "with_reply": True,
    },
    {
        "full_name": "Rachel Green",
        "job_title": "Regulatory Affairs Manager",
        "company": "Summit Ingredients",
        "website": "https://summitingredients.co.uk",
        "domain": "summitingredients.co.uk",
        "email": "rachel.green@summitingredients.co.uk",
        "industry": "Food Manufacturing",
        "status": LeadStatus.NEW,
        "score": 55.0,
    },
    {
        "full_name": "Tom Wright",
        "job_title": "Plant Manager",
        "company": "Eastbridge Meats",
        "website": "https://eastbridgemeats.co.uk",
        "domain": "eastbridgemeats.co.uk",
        "email": "info@eastbridgemeats.co.uk",
        "industry": "Food Manufacturing",
        "status": LeadStatus.ENRICHED,
        "score": 60.0,
    },
    {
        "full_name": "Priya Sharma",
        "job_title": "Technical Director",
        "company": "Blue River Beverages",
        "website": "https://blueriverbeverages.com",
        "domain": "blueriverbeverages.com",
        "email": "priya.sharma@blueriverbeverages.com",
        "industry": "Food Manufacturing",
        "status": LeadStatus.QUALIFIED,
        "score": 88.0,
    },
    {
        "full_name": "Michael O'Brien",
        "job_title": "Food Safety Manager",
        "company": "Lakeside Bakery",
        "website": "https://lakesidebakery.co.uk",
        "domain": "lakesidebakery.co.uk",
        "email": "michael.obrien@lakesidebakery.co.uk",
        "industry": "Food Manufacturing",
        "status": LeadStatus.MEETING_BOOKED,
        "score": 95.0,
    },
    {
        "full_name": "Helen Fraser",
        "job_title": "Head of People",
        "company": "Riverside NHS Trust",
        "website": "https://riversidenhstrust.nhs.uk",
        "domain": "riversidenhstrust.nhs.uk",
        "email": "helen.fraser@riversidenhstrust.nhs.uk",
        "industry": "Healthcare / NHS",
        "status": LeadStatus.QUALIFIED,
        "score": 80.0,
    },
    {
        "full_name": "Oliver Chen",
        "job_title": "Technical Manager",
        "company": "MedCore Devices Ltd",
        "website": "https://medcoredevices.co.uk",
        "domain": "medcoredevices.co.uk",
        "email": "oliver.chen@medcoredevices.co.uk",
        "industry": "Healthcare / MedTech",
        "status": LeadStatus.READY_FOR_OUTREACH,
        "score": 86.0,
    },
]

MOCK_SEARCH_RESULTS = [
    {
        "title": "Quality Manager at Northern Grain Co — UK",
        "url": "https://www.linkedin.com/in/sarah-mitchell-demo",
        "snippet": "Mock search result for regulated organisations niche",
        "provider": "mock",
    },
    {
        "title": "Compliance Manager at Harbour Foods — UK",
        "url": "https://www.linkedin.com/in/james-patel-demo",
        "snippet": "Mock search result for regulated organisations niche",
        "provider": "mock",
    },
]

WELLPREDICT_STEP = {
    "step_number": 1,
    "delay_days": 0,
    "subject_template": "Quick question about {{company}}",
    "body_template": """Hi {{first_name}},

I came across {{company}} while looking at organisations where {{pain_point}} appear especially important.

Would it be unreasonable to ask whether this is something worth a brief conversation?

Regards,
{{sender_name}}

If this is not relevant, reply "not relevant" and I will not contact you again.
To opt out: {{unsubscribe_link}}""",
}


def reset_demo_data(db) -> None:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        return

    niche_ids = list(db.scalars(select(Niche.id).where(Niche.user_id == user.id)).all())
    if niche_ids:
        lead_ids = list(db.scalars(select(Lead.id).where(Lead.niche_id.in_(niche_ids))).all())
        if lead_ids:
            db.execute(delete(EmailMessage).where(EmailMessage.lead_id.in_(lead_ids)))

    db.delete(user)
    db.commit()


def seed(db, *, force: bool = False) -> None:
    existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing:
        if not force:
            print(f"Demo user already exists ({DEMO_EMAIL}). Skipping seed.")
            print("Run with --reset to replace demo data.")
            return
        reset_demo_data(db)

    user = User(
        name="Demo Operator",
        email=DEMO_EMAIL,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        role=UserRole.OPERATOR,
    )
    db.add(user)
    db.flush()

    db.add(
        UserSettings(
            user_id=user.id,
            sender_name="Alex Founder",
            sender_company="WellPredict",
            business_address="London, UK",
        ),
    )
    ensure_default_mock_credentials(db, user.id)

    niche = Niche(
        user_id=user.id,
        name="UK Regulated Organisations — WellPredict",
        country="UK",
        industry="Food Manufacturing, Healthcare, NHS",
        target_roles=[
            "Technical Manager",
            "Quality Manager",
            "Head of People",
            "Operations Director",
            "Compliance Manager",
        ],
        keywords=[
            "food safety",
            "BRC",
            "governance evidence",
            "regulated manufacturing",
            "operational risk",
        ],
        exclusion_keywords=["recruitment", "agency", "reseller"],
        company_size_min=50,
        company_size_max=5000,
    )
    db.add(niche)
    db.flush()

    db.add(
        SearchQuery(
            niche_id=niche.id,
            query='site:linkedin.com/in "Quality Manager" "Food Manufacturing" "UK"',
            provider=SearchProvider.MOCK,
            status=SearchStatus.COMPLETED,
            result_count=len(MOCK_SEARCH_RESULTS),
            results=MOCK_SEARCH_RESULTS,
        ),
    )

    active_campaign = Campaign(
        niche_id=niche.id,
        name="WellPredict Q2 outreach",
        status=CampaignStatus.ACTIVE,
        daily_send_limit=20,
        sending_window_start="09:00",
        sending_window_end="17:00",
    )
    db.add(active_campaign)
    db.flush()
    db.add(CampaignStep(campaign_id=active_campaign.id, **WELLPREDICT_STEP))

    draft_campaign = Campaign(
        niche_id=niche.id,
        name="Healthcare pilot outreach",
        status=CampaignStatus.DRAFT,
        daily_send_limit=15,
        sending_window_start="09:00",
        sending_window_end="17:00",
    )
    db.add(draft_campaign)
    db.flush()
    db.add(CampaignStep(campaign_id=draft_campaign.id, **WELLPREDICT_STEP))

    now = datetime.now(UTC)

    for item in SAMPLE_LEADS:
        company = Company(
            name=item["company"],
            website=item["website"],
            domain=item["domain"],
            industry=item["industry"],
            country="UK",
            size_estimate=220,
            enrichment_status=EnrichmentStatus.COMPLETED,
            robots_checked=True,
            enrichment_message="Seed data — enrichment completed",
        )
        db.add(company)
        db.flush()

        lead = Lead(
            niche_id=niche.id,
            full_name=item["full_name"],
            job_title=item["job_title"],
            company_id=company.id,
            status=item["status"],
            score=item["score"],
            source_url=f"https://example.com/directory/{item['domain']}",
            source_provider="manual",
            compliance_source_note="Found via public company directory listing",
        )
        db.add(lead)
        db.flush()

        db.add(
            EmailContact(
                lead_id=lead.id,
                company_id=company.id,
                email=item["email"],
                email_type=(
                    EmailType.GENERIC
                    if item["email"].startswith("info@")
                    else EmailType.NAMED
                ),
                confidence=0.85,
                source_url=item["website"],
                is_personal=not item["email"].startswith("info@"),
                is_verified=False,
            ),
        )

        if item.get("approved_outreach"):
            db.add(
                EmailMessage(
                    campaign_id=active_campaign.id,
                    lead_id=lead.id,
                    recipient_email=item["email"],
                    subject=f"Quick question about {item['company']}",
                    body="Approved seed message ready for sending.",
                    status=EmailMessageStatus.APPROVED,
                    unsubscribe_token=secrets.token_urlsafe(32),
                ),
            )

        if item.get("sent_outreach"):
            message = EmailMessage(
                campaign_id=active_campaign.id,
                lead_id=lead.id,
                recipient_email=item["email"],
                subject=f"Quick question about {item['company']}",
                body="Sent seed message for reply sync testing.",
                status=EmailMessageStatus.SENT,
                sent_at=now - timedelta(days=1),
                reply_status=ReplyStatus.RECEIVED if item.get("with_reply") else ReplyStatus.NONE,
                unsubscribe_token=secrets.token_urlsafe(32),
            )
            db.add(message)
            db.flush()

            if item.get("with_reply"):
                db.add(
                    Reply(
                        email_message_id=message.id,
                        from_email=item["email"],
                        body="Thanks for reaching out — happy to chat next week if you have 15 minutes.",
                        classification=ReplyClassification.POSITIVE,
                        notes="Interested in governance evidence angle",
                        received_at=now - timedelta(hours=6),
                    ),
                )

    db.add(
        Suppression(
            email="blocked@spam.example",
            domain="spam.example",
            reason="manual",
            source="seed",
        ),
    )

    db.commit()
    print(f"Seeded demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"Niche: {niche.name} ({len(SAMPLE_LEADS)} leads, 2 campaigns, 1 search query)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed LeadsGen demo data")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo user and re-seed",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed(db, force=args.reset)
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
