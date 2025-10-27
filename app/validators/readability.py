from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

async def validate_readability(state: ArticleState) -> ArticleState:
    """Validate readability for multiple audience levels"""
    logger.info(f"Validating readability for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "readability",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state.get("scores", {})["readability"] = score
        state.get("feedback", {})["readability"] = result
        
        # Store readability metrics in metadata
        state.get("metadata", {})["flesch_reading_ease"] = result.get("flesch_reading_ease", 0)
        state.get("metadata", {})["gunning_fog_index"] = result.get("gunning_fog_index", 0)
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="readability",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("readability", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("readability")
            state["retry_counts"]["readability"] = state["retry_counts"].get("readability", 0) + 1
            
            if state["retry_counts"]["readability"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Readability validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Readability validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Readability validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state