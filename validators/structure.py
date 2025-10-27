import re
from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

async def validate_structure(state: ArticleState) -> ArticleState:
    """Validate article structure"""
    logger.info(f"Validating structure for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "structure",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state["scores"]["structure"] = score
        state["feedback"]["structure"] = result
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="structure",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("structure", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("structure")
            state["retry_counts"]["structure"] = state["retry_counts"].get("structure", 0) + 1
            
            if state["retry_counts"]["structure"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Structure validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Structure validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Structure validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state