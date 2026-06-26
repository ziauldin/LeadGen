LeadPilot — a Next.js + Python app that helps you:

choose a niche,
generate search queries,
collect public lead/company URLs through approved search APIs,
enrich company records from websites,
extract role-based contact emails where publicly available,
score and qualify leads,
generate personalised first-touch emails,
send controlled low-volume campaigns,
track opens/replies/statuses,
move qualified replies to discovery calls.

For your WellPredict use case, the first niche should not be generic “marketing agencies.” Start with a niche that matches your founder goal:

UK regulated organisations — food manufacturing, healthcare, legal, financial services, education — targeting Technical Managers, Quality Managers, Operations Directors, HR/People leaders, Governance/Risk leaders.

2. Important build rules

Do not automate LinkedIn login, scraping, profile visiting, connection requests, or message sending. Store LinkedIn profile URLs only when found via approved search APIs or manual CSV upload.

Do not scrape Google search result HTML. Use a provider layer so the app can use Google Programmable Search, Bing Search API, SerpAPI, or manual CSV imports. Google’s Custom Search JSON API is designed for programmatic search result retrieval. ** send mass email through raw Gmail SMTP as the main production method. Use provider APIs such as Resend, SendGrid, Mailgun, Postmark, or Gmail API for controlled low-volume use. Gmail requires authentication and stricter requirements for larger senders, including unsubscribe support for high-volume marketing/subscribed messages. tbound email should include sender identity, company identity, postal/business address where required, a clear opt-out/unsubscribe link, and suppression-list handling. The FTC’s CAN-SPAM guidance says commercial emails must avoid deceptive headers/subjects, identify the message appropriately, include a valid physical postal address, and honour opt-outs. U B2B outreach, include compliance checks for PECR/GDPR-style rules: role relevance, lawful basis notes, source URL, opt-out status, and suppression list. ICO guidance states B2B direct marketing rules vary by method and recipient type, and sometimes consent is needed. 3. System architecture

Frontend

Use:

Next.js 15 or 16
TypeScript
Tailwind CSS
shadcn/ui
TanStack Query
React Hook Form
Zod
Recharts for dashboards

Frontend screens:

Dashboard
total leads
qualified leads
emails sent
replies
booked calls
conversion rate
Niches
create niche
target country
target roles
target industry
company-size filters
keywords
exclusion keywords
Lead Search
generate Google X-Ray style queries
run search through provider API
preview results
save selected results
Leads
table view
filters by score, niche, company, country, status
lead detail drawer
source URL
compliance notes
Companies
website
sector
size estimate
extracted emails
contact page
privacy/robots status
qualification notes
Qualification
scoring rules
lead score
company score
manual override
“ready for outreach” status
Email Studio
AI-assisted email generation
templates
variables
preview
compliance footer
opt-out link
Campaigns
select leads
create sequence
schedule sending
throttle limits
pause/resume
Inbox / Replies
sync replies
classify replies: positive, neutral, objection, unsubscribe, bounce
mark discovery call booked
Settings
sender identity
email provider keys
company address
compliance settings
suppression list
4. Backend architecture

Use:

Python 3.12+
FastAPI
PostgreSQL
SQLAlchemy 2
Alembic
Redis
Celery
Pydantic
httpx
BeautifulSoup/selectolax
tldextract
email-validator
python-dotenv
structlog/loguru

Backend modules:

backend/
  app/
    main.py
    core/
      config.py
      security.py
      logging.py
      database.py
      celery_app.py
    models/
      user.py
      niche.py
      lead.py
      company.py
      email_contact.py
      campaign.py
      email_message.py
      reply.py
      suppression.py
      audit_log.py
    schemas/
    api/
      routes/
        auth.py
        niches.py
        searches.py
        leads.py
        companies.py
        scoring.py
        emails.py
        campaigns.py
        replies.py
        settings.py
    services/
      search/
        base.py
        google_cse.py
        serpapi.py
        bing.py
        manual_import.py
      enrichment/
        website_finder.py
        website_crawler.py
        email_extractor.py
        robots_checker.py
      scoring/
        rules.py
        lead_score.py
      email_generation/
        templates.py
        personalisation.py
      sending/
        base.py
        resend_provider.py
        smtp_provider.py
        gmail_provider.py
      tracking/
        reply_sync.py
        webhook_handlers.py
      compliance/
        suppression.py
        consent_notes.py
        opt_out.py
    workers/
      search_jobs.py
      enrichment_jobs.py
      campaign_jobs.py
      reply_jobs.py
5. Database entities

Core tables:

users
id
name
email
hashed_password
role
created_at
niches
id
user_id
name
country
industry
target_roles
keywords
exclusion_keywords
company_size_min
company_size_max
created_at
search_queries
id
niche_id
query
provider
status
result_count
created_at
leads
id
niche_id
full_name
job_title
linkedin_url
source_url
source_provider
company_id
status
score
qualification_notes
compliance_source_note
created_at
companies
id
name
website
domain
industry
country
size_estimate
contact_page_url
about_page_url
robots_checked
enrichment_status
created_at
email_contacts
id
lead_id
company_id
email
email_type
confidence
source_url
is_role_based
is_personal
is_verified
opted_out
created_at
campaigns
id
niche_id
name
status
daily_send_limit
sending_window_start
sending_window_end
created_at
campaign_steps
id
campaign_id
step_number
delay_days
subject_template
body_template
email_messages
id
campaign_id
lead_id
recipient_email
subject
body
status
sent_at
provider_message_id
reply_status
bounce_status
unsubscribe_token
replies
id
email_message_id
from_email
body
classification
received_at
suppressions
id
email
domain
reason
source
created_at
audit_logs
id
actor_id
action
entity_type
entity_id
metadata
created_at
6. MVP build phases
Phase 1 — Foundation

Build:

auth
dashboard shell
niche creation
database models
API client setup
basic lead table
CSV import/export
Phase 2 — Search and lead collection

Build:

search provider abstraction
Google/Bing/SerpAPI-compatible provider interface
query generator
result preview
save leads from results
deduplication by LinkedIn URL/domain/name
Phase 3 — Company enrichment

Build:

website finder
domain normaliser
website fetcher
contact/about page finder
public email extractor
robots.txt check
enrichment status tracking
Phase 4 — Lead scoring

Build scoring rules:

correct niche: +30
target role match: +25
company website exists: +10
company size match: +15
public work email found: +20
generic email only: +5
no website: -20
excluded keyword found: -30

Lead statuses:

new
enriched
qualified
ready_for_outreach
contacted
replied
meeting_booked
client
disqualified
opted_out
Phase 5 — Email generation

Build:

email template editor
variable insertion
email preview
one-click regenerate
compliance footer
opt-out text
manual approval before sending

For WellPredict, the default style should be:

calm
founder-led
short
non-salesy
UK English
no hype
no emojis
soft question at the end
Phase 6 — Sending and tracking

Build:

email provider interface
Resend or SendGrid first
SMTP only as dev fallback
daily send limit
per-domain throttle
unsubscribe endpoint
suppression list
bounce handling
reply webhook/import
Phase 7 — Reply management

Build:

reply inbox
reply classification
positive/neutral/negative/unsubscribe/bounce
discovery-call status
notes
export to CSV