from typing import TypedDict, Dict, Any, List, Optional
from datetime import datetime

class ArticleState(TypedDict):
    # Session and Article Info
    session_id: str
    article_id: str
    
    # User Requirements
    topic: str
    author: str
    target_audience: str
    article_type: str
    tone: str
    requirements: Dict[str, Any]
    
    # Article Content
    content: str
    title: str
    metadata: Dict[str, Any]
    
    # Validation Scores
    scores: Dict[str, float]
    overall_score: float
    
    # Validation Feedback
    feedback: Dict[str, Any]
    
    # Retry Tracking
    retry_counts: Dict[str, int]
    
    # Control Flow
    needs_regeneration: bool
    failed_nodes: List[str]
    current_node: str
    iteration: int
    
    # Flags
    has_code: bool
    has_math: bool
    
    # Status
    status: str
    error: Optional[str]
    
    # Timestamps
    started_at: datetime
    updated_at: datetime

