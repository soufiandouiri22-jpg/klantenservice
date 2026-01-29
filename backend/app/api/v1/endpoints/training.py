"""
klantenservice.ai - Training Endpoints
"""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.training import TrainingRule, ExampleAnswer
from app.schemas.training import (
    TrainingRuleUpdate,
    TrainingRuleResponse,
    ExampleAnswerCreate,
    ExampleAnswerUpdate,
    ExampleAnswerResponse,
    ToneOfVoiceUpdate,
)
from app.api.deps import get_current_user, get_current_company, require_manager

router = APIRouter()


# Training Rules
@router.get("/rules", response_model=List[TrainingRuleResponse])
async def list_training_rules(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all training rules.
    """
    rules = db.query(TrainingRule).filter(
        TrainingRule.company_id == company.id
    ).order_by(TrainingRule.display_order).all()
    return rules


@router.patch("/rules/{rule_id}", response_model=TrainingRuleResponse)
async def update_training_rule(
    rule_id: UUID,
    data: TrainingRuleUpdate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update a training rule (enable/disable).
    """
    rule = db.query(TrainingRule).filter(
        TrainingRule.id == rule_id,
        TrainingRule.company_id == company.id
    ).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trainingsregel niet gevonden",
        )
    
    rule.is_enabled = data.is_enabled
    db.commit()
    db.refresh(rule)
    
    return rule


# Example Answers (Q&A)
@router.get("/answers", response_model=List[ExampleAnswerResponse])
async def list_example_answers(
    category: str = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all example answers (Q&A pairs).
    """
    query = db.query(ExampleAnswer).filter(ExampleAnswer.company_id == company.id)
    
    if category:
        query = query.filter(ExampleAnswer.category == category)
    
    if active_only:
        query = query.filter(ExampleAnswer.is_active == True)
    
    answers = query.order_by(ExampleAnswer.category, ExampleAnswer.question).all()
    return answers


@router.post("/answers", response_model=ExampleAnswerResponse, status_code=status.HTTP_201_CREATED)
async def create_example_answer(
    data: ExampleAnswerCreate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Create a new example answer.
    """
    answer = ExampleAnswer(
        id=uuid4(),
        company_id=company.id,
        question=data.question,
        question_variations=data.question_variations or [],
        answer=data.answer,
        category=data.category,
        tags=data.tags or [],
        source="manual",
        is_active=True,
        is_verified=True,
    )
    
    db.add(answer)
    db.commit()
    db.refresh(answer)
    
    return answer


@router.get("/answers/{answer_id}", response_model=ExampleAnswerResponse)
async def get_example_answer(
    answer_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific example answer.
    """
    answer = db.query(ExampleAnswer).filter(
        ExampleAnswer.id == answer_id,
        ExampleAnswer.company_id == company.id
    ).first()
    
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voorbeeldantwoord niet gevonden",
        )
    
    return answer


@router.patch("/answers/{answer_id}", response_model=ExampleAnswerResponse)
async def update_example_answer(
    answer_id: UUID,
    data: ExampleAnswerUpdate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update an example answer.
    """
    answer = db.query(ExampleAnswer).filter(
        ExampleAnswer.id == answer_id,
        ExampleAnswer.company_id == company.id
    ).first()
    
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voorbeeldantwoord niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(answer, field, value)
    
    db.commit()
    db.refresh(answer)
    
    return answer


@router.delete("/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example_answer(
    answer_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete an example answer.
    """
    answer = db.query(ExampleAnswer).filter(
        ExampleAnswer.id == answer_id,
        ExampleAnswer.company_id == company.id
    ).first()
    
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voorbeeldantwoord niet gevonden",
        )
    
    db.delete(answer)
    db.commit()


@router.get("/categories")
async def list_categories(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all unique categories.
    """
    categories = db.query(ExampleAnswer.category).filter(
        ExampleAnswer.company_id == company.id,
        ExampleAnswer.category.isnot(None)
    ).distinct().all()
    
    return [c[0] for c in categories if c[0]]


@router.get("/detected-questions")
async def list_detected_questions(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List frequently asked questions detected from calls.
    """
    # Get unverified/detected questions sorted by occurrence
    questions = db.query(ExampleAnswer).filter(
        ExampleAnswer.company_id == company.id,
        ExampleAnswer.source == "detected",
        ExampleAnswer.is_verified == False
    ).order_by(ExampleAnswer.detected_count.desc()).limit(limit).all()
    
    return [
        {
            "id": str(q.id),
            "question": q.question,
            "occurrences": q.detected_count,
            "suggested_answer": q.answer,
        }
        for q in questions
    ]


@router.post("/detected-questions/{question_id}/approve")
async def approve_detected_question(
    question_id: UUID,
    answer: str = None,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Approve a detected question and add it to the knowledge base.
    """
    question = db.query(ExampleAnswer).filter(
        ExampleAnswer.id == question_id,
        ExampleAnswer.company_id == company.id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vraag niet gevonden",
        )
    
    if answer:
        question.answer = answer
    
    question.is_verified = True
    question.is_active = True
    db.commit()
    
    return {"message": "Vraag goedgekeurd en toegevoegd aan kennisbank"}


@router.post("/detected-questions/{question_id}/dismiss")
async def dismiss_detected_question(
    question_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Dismiss a detected question (don't add to knowledge base).
    """
    question = db.query(ExampleAnswer).filter(
        ExampleAnswer.id == question_id,
        ExampleAnswer.company_id == company.id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vraag niet gevonden",
        )
    
    db.delete(question)
    db.commit()
    
    return {"message": "Vraag verwijderd"}
