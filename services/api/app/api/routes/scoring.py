from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.lead import Lead
from app.models.niche import Niche
from app.models.user import User
from app.schemas.scoring import (
    LeadScoreRead,
    RecalculateRequest,
    RecalculateResponse,
    ScoreBreakdownRead,
    ScoringRuleRead,
)
from app.services.scoring.lead_score import apply_score_result, score_lead
from app.services.scoring.rules import SCORING_RULES

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/rules", response_model=list[ScoringRuleRead])
def get_scoring_rules() -> list[ScoringRuleRead]:
    return [
        ScoringRuleRead(
            key=rule.key,
            label=rule.label,
            points=rule.points,
            description=rule.description,
        )
        for rule in SCORING_RULES
    ]


@router.post("/recalculate", response_model=RecalculateResponse)
def recalculate_scores(
    payload: RecalculateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecalculateResponse:
    if payload.niche_id is None and not payload.lead_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide niche_id or lead_ids",
        )

    query = (
        select(Lead)
        .join(Niche, Lead.niche_id == Niche.id)
        .where(Niche.user_id == current_user.id)
        .options(
            selectinload(Lead.company),
            selectinload(Lead.email_contacts),
            selectinload(Lead.niche),
        )
    )

    if payload.lead_ids:
        query = query.where(Lead.id.in_(payload.lead_ids))
    elif payload.niche_id is not None:
        niche = db.scalar(
            select(Niche).where(Niche.id == payload.niche_id, Niche.user_id == current_user.id),
        )
        if niche is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niche not found")
        query = query.where(Lead.niche_id == payload.niche_id)

    leads = db.scalars(query).all()
    results: list[LeadScoreRead] = []

    for lead in leads:
        niche = lead.niche or db.get(Niche, lead.niche_id)
        if niche is None:
            continue
        score_result = score_lead(lead, niche)
        apply_score_result(lead, score_result)
        results.append(
            LeadScoreRead(
                lead_id=lead.id,
                total=score_result.total,
                breakdown=[
                    ScoreBreakdownRead(
                        rule_key=item.rule_key,
                        label=item.label,
                        points=item.points,
                        reason=item.reason,
                    )
                    for item in score_result.breakdown
                ],
                suggested_status=score_result.suggested_status,
                applied_status=lead.status,
            ),
        )

    db.commit()
    return RecalculateResponse(updated=len(results), results=results)
