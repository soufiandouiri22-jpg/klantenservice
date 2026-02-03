"""
klantenservice.ai - Question Detection Service
Analyzes call transcripts to detect questions that couldn't be answered.

This service identifies:
- Questions asked by callers
- Responses indicating the AI couldn't answer
- Saves them as "detected" questions for manual review
"""
import re
import logging
from typing import List, Optional, Tuple
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.training import ExampleAnswer

logger = logging.getLogger(__name__)


# Patterns that indicate the AI couldn't answer the question
UNCERTAINTY_PATTERNS = [
    # Dutch uncertainty phrases
    r"ik weet (het )?niet",
    r"dat weet ik niet",
    r"ik ben niet zeker",
    r"ik kan (u|je) daar niet (mee|bij) helpen",
    r"ik heb (daar )?geen informatie over",
    r"dat is mij niet bekend",
    r"ik kan die vraag niet beantwoorden",
    r"ik zal (het |dat )?(moeten )?navragen",
    r"ik geef (u|je) door",
    r"een collega kan (u|je) (beter )?helpen",
    r"neem (alstublieft )?contact op met",
    r"ik verbind (u|je) door",
    r"ik noteer (het|dat|uw vraag)",
    r"belt u (alstublieft )?terug",
    r"ik kom (daar )?later op terug",
    r"ik zal (het |dat )?uitzoeken",
    r"daar moet ik even naar kijken",
    r"ik kan (u|je) daar (nu )?niet (direct )?antwoord op geven",
    r"helaas (kan|weet) ik",
]

# Compiled patterns for efficiency
UNCERTAINTY_REGEX = re.compile(
    "|".join(UNCERTAINTY_PATTERNS),
    re.IGNORECASE
)


def extract_questions(text: str) -> List[str]:
    """
    Extract questions from text.
    
    Args:
        text: The transcript text (from caller/user)
        
    Returns:
        List of detected questions
    """
    if not text:
        return []
    
    questions = []
    
    # Split into sentences
    # Match sentences ending with ? or likely question patterns
    sentences = re.split(r'[.!?]+', text)
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Check if it's a question (ends with ? in original text, or starts with question word)
        is_question = False
        
        # Check if original text had ? after this sentence
        original_pos = text.find(sentence)
        if original_pos >= 0:
            end_pos = original_pos + len(sentence)
            if end_pos < len(text) and text[end_pos] == '?':
                is_question = True
        
        # Check for Dutch question words at start
        question_starters = [
            r'^(wat|wie|waar|wanneer|waarom|hoe|welke?|hoeveel|kunnen?|kun|mag|mogen|is|zijn|heeft|hebben|kan|zou|zouden)',
        ]
        
        for pattern in question_starters:
            if re.match(pattern, sentence, re.IGNORECASE):
                is_question = True
                break
        
        if is_question and len(sentence) > 10:  # Minimum length to be meaningful
            # Clean up the question
            question = sentence.strip()
            if not question.endswith('?'):
                question += '?'
            questions.append(question)
    
    return questions


def response_indicates_uncertainty(response: str) -> bool:
    """
    Check if the AI response indicates it couldn't answer the question.
    
    Args:
        response: The AI's response text
        
    Returns:
        True if the response indicates uncertainty/inability to answer
    """
    if not response:
        return False
    
    return bool(UNCERTAINTY_REGEX.search(response))


def normalize_question(question: str) -> str:
    """
    Normalize a question for comparison (lowercase, remove punctuation, etc.)
    """
    # Lowercase
    normalized = question.lower()
    # Remove punctuation except ?
    normalized = re.sub(r'[^\w\s?]', '', normalized)
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    return normalized


def questions_are_similar(q1: str, q2: str, threshold: float = 0.7) -> bool:
    """
    Check if two questions are similar enough to be considered the same.
    Uses simple word overlap for now (can be enhanced with embeddings later).
    
    Args:
        q1: First question
        q2: Second question
        threshold: Similarity threshold (0-1)
        
    Returns:
        True if questions are similar
    """
    # Normalize both
    n1 = normalize_question(q1)
    n2 = normalize_question(q2)
    
    # Exact match after normalization
    if n1 == n2:
        return True
    
    # Word overlap similarity (Jaccard)
    words1 = set(n1.replace('?', '').split())
    words2 = set(n2.replace('?', '').split())
    
    if not words1 or not words2:
        return False
    
    intersection = words1 & words2
    union = words1 | words2
    
    similarity = len(intersection) / len(union)
    
    return similarity >= threshold


class QuestionDetectorService:
    """
    Service to detect and save unanswered questions from call transcripts.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze_transcript(
        self,
        company_id: str,
        user_transcript: str,
        assistant_transcript: str
    ) -> List[dict]:
        """
        Analyze a call transcript and detect questions that weren't answered.
        
        Args:
            company_id: The company ID
            user_transcript: What the caller said
            assistant_transcript: What the AI responded
            
        Returns:
            List of detected questions that were saved/updated
        """
        if not user_transcript or not assistant_transcript:
            logger.debug("Empty transcript, skipping analysis")
            return []
        
        # Extract questions from user transcript
        questions = extract_questions(user_transcript)
        
        if not questions:
            logger.debug("No questions found in transcript")
            return []
        
        logger.info(f"Found {len(questions)} questions in transcript")
        
        # Check if AI response indicates uncertainty
        if not response_indicates_uncertainty(assistant_transcript):
            logger.debug("AI response seems confident, no unanswered questions detected")
            return []
        
        logger.info("AI response indicates uncertainty, saving detected questions")
        
        detected = []
        
        for question in questions:
            result = self._save_detected_question(company_id, question)
            if result:
                detected.append(result)
        
        return detected
    
    def _save_detected_question(
        self,
        company_id: str,
        question: str
    ) -> Optional[dict]:
        """
        Save a detected question to the database.
        If a similar question exists, increment its count.
        
        Args:
            company_id: The company ID
            question: The question text
            
        Returns:
            Dict with question info if saved/updated
        """
        try:
            # Get existing detected (unverified) questions for this company
            existing_questions = self.db.query(ExampleAnswer).filter(
                ExampleAnswer.company_id == company_id,
                ExampleAnswer.source == "detected",
                ExampleAnswer.is_verified == False
            ).all()
            
            # Check if similar question already exists
            for existing in existing_questions:
                if questions_are_similar(question, existing.question):
                    # Increment count
                    existing.detected_count += 1
                    existing.updated_at = datetime.utcnow()
                    self.db.commit()
                    
                    logger.info(
                        f"Incremented count for existing question: {existing.question[:50]}... "
                        f"(count: {existing.detected_count})"
                    )
                    
                    return {
                        "id": str(existing.id),
                        "question": existing.question,
                        "count": existing.detected_count,
                        "action": "incremented"
                    }
            
            # Create new detected question
            new_question = ExampleAnswer(
                id=uuid4(),
                company_id=company_id,
                question=question,
                answer="",  # No answer yet
                source="detected",
                detected_count=1,
                is_active=False,  # Not active until verified
                is_verified=False,
            )
            
            self.db.add(new_question)
            self.db.commit()
            self.db.refresh(new_question)
            
            logger.info(f"Created new detected question: {question[:50]}...")
            
            return {
                "id": str(new_question.id),
                "question": question,
                "count": 1,
                "action": "created"
            }
            
        except Exception as e:
            logger.error(f"Error saving detected question: {e}")
            self.db.rollback()
            return None
    
    def get_top_detected_questions(
        self,
        company_id: str,
        limit: int = 10
    ) -> List[dict]:
        """
        Get the most frequently detected questions for a company.
        
        Args:
            company_id: The company ID
            limit: Maximum number of questions to return
            
        Returns:
            List of detected questions sorted by count
        """
        questions = self.db.query(ExampleAnswer).filter(
            ExampleAnswer.company_id == company_id,
            ExampleAnswer.source == "detected",
            ExampleAnswer.is_verified == False
        ).order_by(ExampleAnswer.detected_count.desc()).limit(limit).all()
        
        return [
            {
                "id": str(q.id),
                "question": q.question,
                "count": q.detected_count,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in questions
        ]


def analyze_call_transcript(
    db: Session,
    company_id: str,
    user_transcript: str,
    assistant_transcript: str
) -> List[dict]:
    """
    Convenience function to analyze a transcript.
    
    Args:
        db: Database session
        company_id: The company ID
        user_transcript: What the caller said
        assistant_transcript: What the AI responded
        
    Returns:
        List of detected questions
    """
    service = QuestionDetectorService(db)
    return service.analyze_transcript(company_id, user_transcript, assistant_transcript)
