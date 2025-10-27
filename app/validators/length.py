from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

async def validate_length(state: ArticleState) -> ArticleState:
    """Validate article length and pacing"""
    logger.info(f"Validating length for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "length",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state.get("scores", {})["length"] = score
        state.get("feedback", {})["length"] = result
        
        # Store word count in metadata
        state["metadata"]["word_count"] = result.get("word_count", 0)
        state["metadata"]["read_time"] = result.get("estimated_read_time", "N/A")
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="length",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("length", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("length")
            state["retry_counts"]["length"] = state["retry_counts"].get("length", 0) + 1
            
            if state["retry_counts"]["length"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Length validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Length validation score: {score:.2f}, Word count: {result.get('word_count', 0)}")
        return state
        
    except Exception as e:
        logger.error(f"Length validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state