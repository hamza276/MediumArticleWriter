import uuid
import json
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.agents.state import ArticleState
from app.agents.generator import generator
from app.agents.graph import workflow_manager
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger
from app.api.websocket import manager
from app.utils.prompts import prompt_templates

router = APIRouter()

class ChatMessage(BaseModel):
    session_id: str
    message: str

class ArticleRequest(BaseModel):
    session_id: str
    requirements: Dict[str, Any]

class TimeTravel(BaseModel):
    article_id: str
    checkpoint_id: str
    modifications: Dict[str, Any]

@router.post("/chat")
async def chat_endpoint(chat_msg: ChatMessage):
    """Handle chat messages for requirement gathering"""
    try:
        # Save user message
        db_ops.add_chat_message(
            session_id=chat_msg.session_id,
            user_message=chat_msg.message,
            message_type='chat'
        )
        
        # Get chat history
        history = db_ops.get_chat_history(chat_msg.session_id)
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": prompt_templates.CHAT_INITIAL_SYSTEM}
        ]
        
        for chat in history:
            if chat.user_message:
                messages.append({"role": "user", "content": chat.user_message})
            if chat.bot_response:
                messages.append({"role": "assistant", "content": chat.bot_response})
        
        # Get response
        response_parts = []
        async for token in generator.chat_with_user(messages):
            response_parts.append(token)
            # Send token via WebSocket if connected
            await manager.send_token(chat_msg.session_id, token, "chat")
        
        bot_response = "".join(response_parts)
        
        # Save bot response
        db_ops.add_chat_message(
            session_id=chat_msg.session_id,
            bot_response=bot_response,
            message_type='chat'
        )
        
        return {
            "success": True,
            "response": bot_response,
            "session_id": chat_msg.session_id
        }
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-article")
async def generate_article_endpoint(request: ArticleRequest):
    """Start article generation process"""
    try:
        # Check queue
        processing_count = db_ops.get_processing_count()
        
        if processing_count >= settings.MAX_CONCURRENT_ARTICLES:
            # Add to queue
            position = db_ops.add_to_queue(request.session_id)
            await manager.send_status(
                request.session_id,
                "queued",
                {"position": position, "message": f"Added to queue at position {position}"}
            )
            return {
                "success": True,
                "status": "queued",
                "position": position
            }
        
        # Mark as processing
        db_ops.update_queue_status(request.session_id, "processing")
        
        # Create article
        article_id = f"article_{uuid.uuid4().hex[:12]}"
        
        article = db_ops.create_article(
            article_id=article_id,
            session_id=request.session_id,
            title=request.requirements.get('topic', 'Untitled'),
            author=request.requirements.get('author', 'Anonymous'),
            metadata=request.requirements
        )
        
        # Initialize state
        initial_state: ArticleState = {
            "session_id": request.session_id,
            "article_id": article_id,
            "topic": request.requirements.get('topic', ''),
            "author": request.requirements.get('author', ''),
            "target_audience": request.requirements.get('target_audience', 'mixed'),
            "article_type": request.requirements.get('article_type', 'educational'),
            "tone": request.requirements.get('tone', 'conversational'),
            "requirements": request.requirements,
            "content": "",
            "title": "",
            "metadata": request.requirements,
            "scores": {},
            "overall_score": 0.0,
            "feedback": {},
            "retry_counts": {},
            "needs_regeneration": False,
            "failed_nodes": [],
            "current_node": "",
            "iteration": 0,
            "has_code": False,
            "has_math": False,
            "status": "processing",
            "error": None,
            "started_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Run workflow asynchronously
        import asyncio
        asyncio.create_task(run_workflow(initial_state))
        
        return {
            "success": True,
            "article_id": article_id,
            "status": "processing",
            "message": "Article generation started"
        }
        
    except Exception as e:
        logger.error(f"Generation start error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_workflow(state: ArticleState):
    """Run the article generation workflow"""
    try:
        await manager.send_status(state["session_id"], "started", 
                                 {"article_id": state["article_id"]})
        
        # Run workflow
        final_state = await workflow_manager.run(state)
        
        if final_state.get("status") == "completed":
            await manager.send_completion(
                state["session_id"],
                final_state.get("article_id"),
                final_state.get("overall_score")
            )
        elif final_state.get("status") == "error":
            await manager.send_error(state["session_id"], final_state.get("error"))
        
        # Mark queue as completed
        db_ops.update_queue_status(state["session_id"], "completed")
        
        # Check if next in queue
        next_session = db_ops.get_next_in_queue()
        if next_session:
            # Trigger next article generation
            pass
        return final_state
    except Exception as e:
        logger.error(f"Workflow error: {str(e)}")
        await manager.send_error(state["session_id"], str(e))
        db_ops.update_article(state["article_id"], status="failed")

@router.get("/article/{article_id}")
async def get_article(article_id: str):
    """Get article by ID"""
    try:
        article = db_ops.get_article(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return {
            "success": True,
            "article": {
                "id": article.id,
                "title": article.title,
                "content": article.content,
                "author": article.author,
                "metadata": article.article_metadata,  # CHANGED: was 'article.metadata'
                "status": article.status,
                "overall_score": article.overall_score,
                "created_at": article.created_at.isoformat(),
                "updated_at": article.updated_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get article error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/article-status/{session_id}")
async def get_article_status(session_id: str):
    """Get current status of article generation"""
    try:
        # Check queue status
        queue_item = db_ops.get_queue_position(session_id)
        
        return {
            "success": True,
            "queue_position": queue_item,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/validation-report/{article_id}")
async def get_validation_report(article_id: str):
    """Get detailed validation report"""
    try:
        logs = db_ops.get_validation_logs(article_id)
        versions = db_ops.get_versions(article_id)
        
        report = {
            "article_id": article_id,
            "validations": [],
            "versions": [],
            "summary": {}
        }
        
        # Process validation logs
        for log in logs:
            report["validations"].append({
                "node": log.node_name,
                "score": log.score,
                "feedback": log.feedback,
                "retry_count": log.retry_count,
                "status": log.status,
                "timestamp": log.timestamp.isoformat()
            })
        
        # Process versions
        for version in versions:
            report["versions"].append({
                "version": version.version_number,
                "node": version.node_name,
                "scores": version.scores,
                "timestamp": version.timestamp.isoformat()
            })
        
        # Calculate summary
        if logs:
            latest_scores = {}
            for log in reversed(logs):
                if log.node_name not in latest_scores:
                    latest_scores[log.node_name] = log.score
            
            report["summary"] = {
                "total_validations": len(logs),
                "total_versions": len(versions),
                "latest_scores": latest_scores,
                "average_score": sum(latest_scores.values()) / len(latest_scores) if latest_scores else 0
            }
        
        return {"success": True, "report": report}
        
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles")
async def get_all_articles(limit: int = 50):
    """Get all articles"""
    try:
        articles = db_ops.get_all_articles(limit)
        
        return {
            "success": True,
            "articles": [
                {
                    "id": article.id,
                    "title": article.title,
                    "author": article.author,
                    "status": article.status,
                    "overall_score": article.overall_score,
                    "created_at": article.created_at.isoformat()
                }
                for article in articles
            ]
        }
    except Exception as e:
        logger.error(f"Get articles error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/time-travel")
async def time_travel(request: TimeTravel):
    """Time travel to checkpoint and modify"""
    try:
        # Get checkpoint
        checkpoint = db_ops.get_checkpoint(request.checkpoint_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        
        # Load state
        state = checkpoint.state_data
        
        # Apply modifications
        for key, value in request.modifications.items():
            if key in state:
                state[key] = value
        
        # Create new article version
        new_article_id = f"article_{uuid.uuid4().hex[:12]}"
        state["article_id"] = new_article_id
        
        # Run workflow from checkpoint
        final_state = await workflow_manager.run(state)
        
        return {
            "success": True,
            "new_article_id": new_article_id,
            "message": "Time travel successful, new article created"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Time travel error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

