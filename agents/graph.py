import uuid
from datetime import datetime
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import ArticleState
from app.agents.generator import generator
from app.validators import (
    validate_structure, validate_language, validate_grammar,
    validate_length, validate_math, validate_depth,
    validate_readability, validate_code
)
from app.database.operations import db_ops
from app.config import settings
from app.utils.logger import logger
from app.utils.latex_handler import latex_handler

class ArticleWorkflow:
    
    def __init__(self):
        self.checkpointer = MemorySaver()  # CHANGED: Using MemorySaver instead of SqliteSaver
        self.workflow = self._build_workflow()
    
    async def generate_node(self, state: ArticleState) -> ArticleState:
        """Generate initial article content"""
        logger.info(f"Generating article for {state['article_id']}")
        state["current_node"] = "generate"
        
        try:
            # Generate content
            content_parts = []
            async for token in generator.generate_article(state["requirements"]):
                content_parts.append(token)
            
            state["content"] = "".join(content_parts)
            
            # Extract title from content (first # heading)
            import re
            title_match = re.search(r'^#\s+(.+)$', state["content"], re.MULTILINE)
            if title_match:
                state["title"] = title_match.group(1)
            
            # Save version
            db_ops.create_version(
                article_id=state["article_id"],
                content=state["content"],
                scores={},
                node_name="generate"
            )
            
            # Save checkpoint
            checkpoint_id = f"{state['article_id']}_generate_{uuid.uuid4().hex[:8]}"
            db_ops.save_checkpoint(
                checkpoint_id=checkpoint_id,
                article_id=state["article_id"],
                node_name="generate",
                state_data=dict(state)
            )
            
            logger.info(f"Article generated successfully: {len(state['content'])} characters")
            return state
            
        except Exception as e:
            logger.error(f"Generation error: {str(e)}")
            state["status"] = "error"
            state["error"] = str(e)
            return state
    
    async def regenerate_node(self, state: ArticleState) -> ArticleState:
        """Regenerate content based on failed validations"""
        logger.info(f"Regenerating article for {state['article_id']}")
        state["current_node"] = "regenerate"
        state["iteration"] += 1
        
        try:
            # Get feedback from failed nodes
            failed_feedback = {
                node: state["feedback"].get(node, {})
                for node in state["failed_nodes"]
            }
            
            feedback_text = "\n".join([
                f"{node}: {fb.get('feedback', 'No feedback')}"
                for node, fb in failed_feedback.items()
            ])
            
            # Regenerate content
            content_parts = []
            async for token in generator.regenerate_content(
                ", ".join(state["failed_nodes"]),
                feedback_text,
                state["content"]
            ):
                content_parts.append(token)
            
            state["content"] = "".join(content_parts)
            
            # Clear failed nodes for retry
            state["failed_nodes"] = []
            
            # Save version
            db_ops.create_version(
                article_id=state["article_id"],
                content=state["content"],
                scores=state["scores"],
                node_name="regenerate"
            )
            
            # Save checkpoint
            checkpoint_id = f"{state['article_id']}_regenerate_{uuid.uuid4().hex[:8]}"
            db_ops.save_checkpoint(
                checkpoint_id=checkpoint_id,
                article_id=state["article_id"],
                node_name="regenerate",
                state_data=dict(state)
            )
            
            logger.info(f"Article regenerated, iteration {state['iteration']}")
            return state
            
        except Exception as e:
            logger.error(f"Regeneration error: {str(e)}")
            state["status"] = "error"
            state["error"] = str(e)
            return state
    
    async def finalize_node(self, state: ArticleState) -> ArticleState:
        """Finalize article with equation processing and final save"""
        logger.info(f"Finalizing article {state['article_id']}")
        state["current_node"] = "finalize"
        
        try:
            # Process LaTeX equations if present
            if state.get("has_math", False):
                state["content"], eq_count = latex_handler.process_article_equations(
                    state["content"],
                    state["article_id"]
                )
                logger.info(f"Processed {eq_count} equations")
            
            # Calculate overall score
            scores = state["scores"]
            overall_score = sum(scores.values()) / len(scores) if scores else 0.0
            state["overall_score"] = overall_score
            
            # Update article in database
            db_ops.update_article(
                article_id=state["article_id"],
                content=state["content"],
                status="completed",
                score=overall_score
            )
            
            state["status"] = "completed"
            logger.info(f"Article finalized with overall score: {overall_score:.2f}")
            
            return state
            
        except Exception as e:
            logger.error(f"Finalization error: {str(e)}")
            state["status"] = "error"
            state["error"] = str(e)
            return state
    
    def should_regenerate(self, state: ArticleState) -> Literal["regenerate", "finalize"]:
        """Determine if regeneration is needed"""
        
        # Check if any validation failed
        if state["failed_nodes"]:
            # Check retry limits
            max_retries_reached = any(
                state["retry_counts"].get(node, 0) >= settings.MAX_RETRIES
                for node in state["failed_nodes"]
            )
            
            if max_retries_reached:
                logger.warning("Max retries reached, proceeding to finalize")
                return "finalize"
            
            return "regenerate"
        
        # Check overall score
        overall_score = sum(state["scores"].values()) / len(state["scores"]) if state["scores"] else 0.0
        
        if overall_score < settings.PUBLISH_THRESHOLD:
            logger.info(f"Overall score {overall_score:.2f} below threshold, regenerating")
            # Mark lowest scoring node as failed
            if state["scores"]:
                lowest_node = min(state["scores"], key=state["scores"].get)
                if state["scores"][lowest_node] < settings.MIN_SCORE_THRESHOLD:
                    state["failed_nodes"].append(lowest_node)
                    return "regenerate"
        
        return "finalize"
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(ArticleState)
        
        # Add nodes
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("validate_structure", validate_structure)
        workflow.add_node("validate_language", validate_language)
        workflow.add_node("validate_grammar", validate_grammar)
        workflow.add_node("validate_length", validate_length)
        workflow.add_node("validate_math", validate_math)
        workflow.add_node("validate_depth", validate_depth)
        workflow.add_node("validate_readability", validate_readability)
        workflow.add_node("validate_code", validate_code)
        workflow.add_node("regenerate", self.regenerate_node)
        workflow.add_node("finalize", self.finalize_node)
        
        # Set entry point
        workflow.set_entry_point("generate")
        
        # Sequential validation flow
        workflow.add_edge("generate", "validate_structure")
        workflow.add_edge("validate_structure", "validate_language")
        workflow.add_edge("validate_language", "validate_grammar")
        workflow.add_edge("validate_grammar", "validate_length")
        workflow.add_edge("validate_length", "validate_math")
        workflow.add_edge("validate_math", "validate_depth")
        workflow.add_edge("validate_depth", "validate_readability")
        workflow.add_edge("validate_readability", "validate_code")
        
        # Conditional edge after validation
        workflow.add_conditional_edges(
            "validate_code",
            self.should_regenerate,
            {
                "regenerate": "regenerate",
                "finalize": "finalize"
            }
        )
        
        # Loop back from regenerate to validation
        workflow.add_edge("regenerate", "validate_structure")
        
        # End workflow
        workflow.add_edge("finalize", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def run(self, initial_state: ArticleState) -> ArticleState:
        """Run the workflow"""
        config = {
            "configurable": {
                "thread_id": initial_state["session_id"]
            }
        }
        
        result = await self.workflow.ainvoke(initial_state, config)
        return result
    
    async def get_state(self, session_id: str) -> Dict[str, Any]:
        """Get current state from checkpoint"""
        config = {"configurable": {"thread_id": session_id}}
        state = await self.workflow.aget_state(config)
        return state

workflow_manager = ArticleWorkflow()

