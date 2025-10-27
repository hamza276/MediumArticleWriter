from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

async def validate_grammar(state: ArticleState) -> ArticleState:
    """Validate grammar and syntax"""
    logger.info(f"Validating grammar for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "grammar",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state["scores"]["grammar"] = score
        state["feedback"]["grammar"] = result
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="grammar",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("grammar", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("grammar")
            state["retry_counts"]["grammar"] = state["retry_counts"].get("grammar", 0) + 1
            
            if state["retry_counts"]["grammar"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Grammar validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Grammar validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Grammar validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state