import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.logger import logger

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: Dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {str(e)}")
    
    async def send_token(self, session_id: str, token: str, message_type: str = "content"):
        """Send individual token for streaming effect"""
        await self.send_message(session_id, {
            "type": "token",
            "message_type": message_type,
            "content": token
        })
    
    async def send_status(self, session_id: str, status: str, data: Dict = None):
        """Send status update"""
        message = {
            "type": "status",
            "status": status,
            "data": data or {}
        }
        await self.send_message(session_id, message)
    
    async def send_node_update(self, session_id: str, node_name: str, 
                               status: str, score: float = None):
        """Send validation node update"""
        message = {
            "type": "node_update",
            "node": node_name,
            "status": status,
            "score": score
        }
        await self.send_message(session_id, message)
    
    async def send_error(self, session_id: str, error: str):
        """Send error message"""
        await self.send_message(session_id, {
            "type": "error",
            "message": error
        })
    
    async def send_completion(self, session_id: str, article_id: str, 
                             overall_score: float):
        """Send completion message"""
        await self.send_message(session_id, {
            "type": "completion",
            "article_id": article_id,
            "overall_score": overall_score
        })

manager = ConnectionManager()

