from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

async def validate_depth(state: ArticleState) -> ArticleState:
    """Validate content depth and comprehensiveness"""
    logger.info(f"Validating depth for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "depth",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state.get("scores", {})["depth"] = score
        state.get("feedback", {})["depth"] = result
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="depth",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("depth", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("depth")
            state["retry_counts"]["depth"] = state["retry_counts"].get("depth", 0) + 1
            
            if state["retry_counts"]["depth"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Depth validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Depth validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Depth validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state