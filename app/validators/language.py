from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

async def validate_language(state: ArticleState) -> ArticleState:
    """Validate language and tone consistency"""
    logger.info(f"Validating language for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "language",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state.get("scores", {})["language"] = score
        state.get("feedback", {})["language"] = result
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="language",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("language", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("language")
            state["retry_counts"]["language"] = state["retry_counts"].get("language", 0) + 1
            
            if state["retry_counts"]["language"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Language validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Language validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Language validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state