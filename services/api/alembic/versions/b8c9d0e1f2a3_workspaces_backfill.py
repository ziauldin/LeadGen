"""workspaces (backfill): one personal workspace per user; move every row into it

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-16 10:05:00.000000

Plain SQL only (no ORM imports), so this migration keeps working as the models evolve.

* Every user gets a personal workspace (owner), seeded from their old user_settings.
* Rows follow their owner: niche -> user, search/lead/campaign -> niche, step -> campaign,
  message -> lead, reply -> message, credential -> user, audit -> actor.
* Companies used by several users are copied once per workspace, and leads/contacts are
  re-pointed to their workspace's copy. Companies with no leads go to the oldest user.
* Old global suppressions are copied into every workspace (so nobody can be emailed who opted
  out before), keeping only the email for address rows (fixes domain-wide unsubscribes).
* Duplicates that would break the new unique constraints are merged.
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMPANY_COLUMNS = (
    "name",
    "website",
    "domain",
    "industry",
    "country",
    "size_estimate",
    "contact_page_url",
    "about_page_url",
    "robots_checked",
    "enrichment_status",
    "enrichment_message",
    "created_at",
    "updated_at",
)
CONTACT_COLUMNS = (
    "lead_id",
    "email",
    "email_type",
    "confidence",
    "source_url",
    "is_role_based",
    "is_personal",
    "is_verified",
    "opted_out",
    "created_at",
)


def _slug(name: str, user_id: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "workspace"
    return f"{base}-{user_id}"


def upgrade() -> None:
    conn = op.get_bind()
    run = conn.execute
    t = sa.text

    has_user_settings = sa.inspect(conn).has_table("user_settings")

    # 1. Personal workspaces.
    users = run(t("SELECT id, name FROM users ORDER BY id")).all()
    workspace_of_user: dict[int, int] = {}
    for user_id, name in users:
        first = (name or "").split()[0] if (name or "").strip() else "My"
        ws_name = f"{first}'s workspace"
        slug = _slug(ws_name, user_id)
        run(
            t(
                "INSERT INTO workspaces (name, slug, plan, timezone, created_by) "
                "VALUES (:name, :slug, 'free', 'UTC', :uid)",
            ),
            {"name": ws_name, "slug": slug, "uid": user_id},
        )
        ws_id = run(t("SELECT id FROM workspaces WHERE slug = :slug"), {"slug": slug}).scalar_one()
        workspace_of_user[user_id] = ws_id
        run(
            t(
                "INSERT INTO workspace_members (workspace_id, user_id, role) "
                "VALUES (:ws, :uid, 'owner')",
            ),
            {"ws": ws_id, "uid": user_id},
        )
        row = None
        if has_user_settings:
            row = run(
                t(
                    "SELECT sender_name, sender_company, business_address FROM user_settings "
                    "WHERE user_id = :uid",
                ),
                {"uid": user_id},
            ).first()
        run(
            t(
                "INSERT INTO workspace_settings (workspace_id, sender_name, sender_company, "
                "business_address, ai_mode, default_sending_window_start, "
                "default_sending_window_end, sending_days) "
                "VALUES (:ws, :sn, :sc, :ba, 'off', '09:00', '17:00', '[0, 1, 2, 3, 4]')",
            ),
            {
                "ws": ws_id,
                "sn": (row[0] if row and row[0] else name),
                "sc": row[1] if row else None,
                "ba": row[2] if row else None,
            },
        )
        run(
            t("UPDATE users SET last_workspace_id = :ws WHERE id = :uid"),
            {"ws": ws_id, "uid": user_id},
        )

    # 2. Rows that follow their owner.
    for user_id, ws_id in workspace_of_user.items():
        params = {"ws": ws_id, "uid": user_id}
        run(t("UPDATE niches SET workspace_id = :ws WHERE user_id = :uid"), params)
        run(t("UPDATE provider_credentials SET workspace_id = :ws WHERE user_id = :uid"), params)
        run(t("UPDATE audit_logs SET workspace_id = :ws WHERE actor_id = :uid"), params)

    run(
        t(
            "UPDATE search_queries SET workspace_id = "
            "(SELECT niches.workspace_id FROM niches WHERE niches.id = search_queries.niche_id)",
        ),
    )
    run(
        t(
            "UPDATE leads SET workspace_id = "
            "(SELECT niches.workspace_id FROM niches WHERE niches.id = leads.niche_id)",
        ),
    )
    run(
        t(
            "UPDATE campaigns SET workspace_id = "
            "(SELECT niches.workspace_id FROM niches WHERE niches.id = campaigns.niche_id)",
        ),
    )
    run(
        t(
            "UPDATE campaign_steps SET workspace_id = "
            "(SELECT campaigns.workspace_id FROM campaigns "
            "WHERE campaigns.id = campaign_steps.campaign_id)",
        ),
    )
    run(
        t(
            "UPDATE email_messages SET workspace_id = "
            "(SELECT leads.workspace_id FROM leads WHERE leads.id = email_messages.lead_id)",
        ),
    )
    run(
        t(
            "UPDATE replies SET workspace_id = "
            "(SELECT email_messages.workspace_id FROM email_messages "
            "WHERE email_messages.id = replies.email_message_id)",
        ),
    )

    # 3. Companies: one copy per workspace that uses them.
    oldest_ws = workspace_of_user[min(workspace_of_user)] if workspace_of_user else None
    company_ids = [row[0] for row in run(t("SELECT id FROM companies ORDER BY id")).all()]
    cols = ", ".join(COMPANY_COLUMNS)
    contact_cols = ", ".join(CONTACT_COLUMNS)
    for company_id in company_ids:
        users_ws = sorted(
            {
                row[0]
                for row in run(
                    t(
                        "SELECT DISTINCT workspace_id FROM leads "
                        "WHERE company_id = :cid AND workspace_id IS NOT NULL",
                    ),
                    {"cid": company_id},
                ).all()
            },
        )
        if not users_ws:
            if oldest_ws is None:
                run(t("DELETE FROM email_contacts WHERE company_id = :cid"), {"cid": company_id})
                run(t("DELETE FROM companies WHERE id = :cid"), {"cid": company_id})
                continue
            users_ws = [oldest_ws]

        keeper_ws, *others = users_ws
        run(
            t("UPDATE companies SET workspace_id = :ws WHERE id = :cid"),
            {"ws": keeper_ws, "cid": company_id},
        )
        for ws_id in others:
            run(
                t(
                    f"INSERT INTO companies (workspace_id, {cols}) "  # noqa: S608 - fixed names
                    f"SELECT :ws, {cols} FROM companies WHERE id = :cid",
                ),
                {"ws": ws_id, "cid": company_id},
            )
            new_id = run(
                t(
                    "SELECT MAX(id) FROM companies WHERE workspace_id = :ws AND name = "
                    "(SELECT name FROM companies WHERE id = :cid)",
                ),
                {"ws": ws_id, "cid": company_id},
            ).scalar_one()
            run(
                t(
                    "UPDATE email_contacts SET company_id = :new "
                    "WHERE company_id = :cid AND lead_id IN "
                    "(SELECT id FROM leads WHERE workspace_id = :ws)",
                ),
                {"new": new_id, "cid": company_id, "ws": ws_id},
            )
            run(
                t(
                    f"INSERT INTO email_contacts (company_id, {contact_cols}) "  # noqa: S608
                    f"SELECT :new, {contact_cols} FROM email_contacts "
                    "WHERE company_id = :cid AND lead_id IS NULL",
                ),
                {"new": new_id, "cid": company_id},
            )
            run(
                t("UPDATE leads SET company_id = :new WHERE company_id = :cid AND workspace_id = :ws"),
                {"new": new_id, "cid": company_id, "ws": ws_id},
            )

    # 4. Contacts follow their lead, or their company when they have no lead.
    run(
        t(
            "UPDATE email_contacts SET workspace_id = "
            "(SELECT leads.workspace_id FROM leads WHERE leads.id = email_contacts.lead_id) "
            "WHERE lead_id IS NOT NULL",
        ),
    )
    run(
        t(
            "UPDATE email_contacts SET workspace_id = "
            "(SELECT companies.workspace_id FROM companies "
            "WHERE companies.id = email_contacts.company_id) "
            "WHERE lead_id IS NULL",
        ),
    )
    run(t("DELETE FROM email_contacts WHERE workspace_id IS NULL"))

    # 5. Suppressions: copy every old (global) row into every workspace, then drop the originals.
    old_suppressions = run(
        t(
            "SELECT id, email, domain, reason, source, created_at FROM suppressions "
            "WHERE workspace_id IS NULL",
        ),
    ).all()
    for _sid, email, domain, reason, source, created_at in old_suppressions:
        keep_domain = None if email else domain
        for ws_id in workspace_of_user.values():
            run(
                t(
                    "INSERT INTO suppressions (workspace_id, email, domain, reason, source, "
                    "created_at) VALUES (:ws, :email, :domain, :reason, :source, :created)",
                ),
                {
                    "ws": ws_id,
                    "email": email.lower() if email else None,
                    "domain": keep_domain,
                    "reason": reason,
                    "source": source,
                    "created": created_at,
                },
            )
    run(t("DELETE FROM suppressions WHERE workspace_id IS NULL"))

    # 6. Remove duplicates that the contract migration's unique constraints would reject.
    #    Companies: same (workspace, domain) -> merge into the lowest id.
    dupes = run(
        t(
            "SELECT workspace_id, domain, MIN(id) FROM companies WHERE domain IS NOT NULL "
            "GROUP BY workspace_id, domain HAVING COUNT(*) > 1",
        ),
    ).all()
    for ws_id, domain, keeper in dupes:
        losers = [
            row[0]
            for row in run(
                t("SELECT id FROM companies WHERE workspace_id = :ws AND domain = :d AND id <> :k"),
                {"ws": ws_id, "d": domain, "k": keeper},
            ).all()
        ]
        for loser in losers:
            run(t("UPDATE leads SET company_id = :k WHERE company_id = :l"), {"k": keeper, "l": loser})
            run(
                t("UPDATE email_contacts SET company_id = :k WHERE company_id = :l"),
                {"k": keeper, "l": loser},
            )
            run(t("DELETE FROM companies WHERE id = :l"), {"l": loser})

    #    Contacts: same (workspace, lead, email) -> keep the lowest id.
    run(
        t(
            "DELETE FROM email_contacts WHERE lead_id IS NOT NULL AND id NOT IN ("
            "SELECT keep_id FROM (SELECT MIN(id) AS keep_id FROM email_contacts "
            "WHERE lead_id IS NOT NULL GROUP BY workspace_id, lead_id, email) AS keepers)",
        ),
    )
    #    Leads: same (workspace, niche, linkedin_url) -> clear the URL on later duplicates.
    run(
        t(
            "UPDATE leads SET linkedin_url = NULL WHERE linkedin_url IS NOT NULL AND id NOT IN ("
            "SELECT keep_id FROM (SELECT MIN(id) AS keep_id FROM leads "
            "WHERE linkedin_url IS NOT NULL "
            "GROUP BY workspace_id, niche_id, linkedin_url) AS keepers)",
        ),
    )


def downgrade() -> None:
    # Data backfill is not reversible beyond clearing the new columns (done by 0008's downgrade).
    op.execute(sa.text("DELETE FROM usage_counters"))
    op.execute(sa.text("DELETE FROM workspace_settings"))
    op.execute(sa.text("DELETE FROM workspace_members"))
    op.execute(sa.text("UPDATE users SET last_workspace_id = NULL"))
    op.execute(sa.text("DELETE FROM workspaces"))
