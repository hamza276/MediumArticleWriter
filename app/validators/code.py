import re
from typing import Dict, Any
from app.agents.state import ArticleState
from app.agents.generator import generator
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger

def check_has_code(content: str) -> bool:
    """Check if content has code blocks"""
    return bool(re.search(r'```[\s\S]*?```', content))

async def validate_code(state: ArticleState) -> ArticleState:
    """Validate code examples (conditional)"""
    
    # Check if article has code content
    has_code = check_has_code(state["content"])
    state["has_code"] = has_code
    
    if not has_code:
        logger.info(f"No code content found in article {state['article_id']}, skipping code validation")
        state.get("scores", {})["code"] = 10.0  # Perfect score if not applicable
        state.get("feedback", {})["code"] = {"score": 10.0, "feedback": "No code blocks to validate"}
        return state
    
    logger.info(f"Validating code for article {state['article_id']}")
    
    try:
        result = await generator.validate_content(
            "code",
            state["content"],
            state["metadata"]
        )
        
        score = result.get("score", 0.0)
        state.get("scores", {})["code"] = score
        state.get("feedback", {})["code"] = result
        
        # Log validation
        db_ops.add_validation_log(
            article_id=state["article_id"],
            node_name="code",
            score=score,
            feedback=result,
            retry_count=state["retry_counts"].get("code", 0),
            status="passed" if score >= settings.MIN_SCORE_THRESHOLD else "failed"
        )
        
        # Check if retry needed
        if score < settings.MIN_SCORE_THRESHOLD:
            state["failed_nodes"].append("code")
            state["retry_counts"]["code"] = state["retry_counts"].get("code", 0) + 1
            
            if state["retry_counts"]["code"] >= settings.MAX_RETRIES:
                state["status"] = "failed"
                state["error"] = f"Code validation failed after {settings.MAX_RETRIES} retries"
                logger.error(state["error"])
        
        logger.info(f"Code validation score: {score:.2f}")
        return state
        
    except Exception as e:
        logger.error(f"Code validation error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        return state