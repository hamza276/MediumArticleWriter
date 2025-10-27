import re
from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger
from app.utils.latex_handler import latex_handler

def check_has_math(content: str) -> bool:
    """Check if content has mathematical equations"""
    return bool(re.search(r'\$.*?\$', content))

async def validate_math(state: ArticleState) -> ArticleState:
    """Validate mathematical equations (conditional)"""
    
    # Check if article has math content
    has_math = check_has_math(state["content"])
    state["has_math"] = has_math
    
    if not has_math:
        logger.info(f"No math content found in article {state['article_id']}, skipping math validation")
        state.get("scores", {})["math"] = 10.0  # Perfect score if not applicable
        state.get("feedback", {})["math"] = {"score": 10.0, "feedback": "No mathematical content to validate"}
        return state
    
    logger.info(f"Validating math for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "math",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state.get("scores", {})["math"] = score
        state.get("feedback", {})["math"] = result
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="math",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("math", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("math")
            state["retry_counts"]["math"] = state["retry_counts"].get("math", 0) + 1
            
            if state["retry_counts"]["math"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Math validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Math validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Math validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state