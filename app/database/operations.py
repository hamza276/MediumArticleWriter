from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Generator
from datetime import datetime
import json

from app.database.models import Base, Article, ArticleVersion, ChatHistory, ValidationLog, ArticleQueue, Checkpoint, Analytics
from app.config import settings
from app.utils.logger import logger

class DatabaseOperations:
    
    def __init__(self):
        self.engine = create_engine(
            f'sqlite:///{settings.DATABASE_PATH}',
            connect_args={"check_same_thread": False},
            echo=False
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.info(f"Database initialized at {settings.DATABASE_PATH}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            session.close()
    
    # Article Operations
    def create_article(self, article_id: str, session_id: str, title: str, 
                      author: str, metadata: Dict) -> Article:
        with self.get_session() as session:
            article = Article(
                id=article_id,
                session_id=session_id,
                title=title,
                content="",
                author=author,
                article_metadata=metadata,
                status='processing'
            )
            session.add(article)
            logger.info(f"Created article: {article_id}")
            return article
    
    def update_article(self, article_id: str, content: Optional[str] = None,
                      status: Optional[str] = None, score: Optional[float] = None):
        with self.get_session() as session:
            article = session.query(Article).filter_by(id=article_id).first()
            if article:
                if content is not None:
                    article.content = content
                if status is not None:
                    article.status = status
                if score is not None:
                    article.overall_score = score
                article.updated_at = datetime.utcnow()
                logger.info(f"Updated article: {article_id}")
    
    def get_article(self, article_id: str) -> Optional[Article]:
        with self.get_session() as session:
            return session.query(Article).filter_by(id=article_id).first()
    
    def get_all_articles(self, limit: int = 50) -> List[Article]:
        with self.get_session() as session:
            return session.query(Article).order_by(desc(Article.created_at)).limit(limit).all()
    
    # Version Operations
    def create_version(self, article_id: str, content: str, scores: Dict, 
                      node_name: str) -> ArticleVersion:
        with self.get_session() as session:
            # Get current version count
            version_count = session.query(ArticleVersion).filter_by(article_id=article_id).count()
            
            version = ArticleVersion(
                article_id=article_id,
                version_number=version_count + 1,
                content=content,
                scores=scores,
                node_name=node_name
            )
            session.add(version)
            logger.info(f"Created version {version_count + 1} for article {article_id}")
            return version
    
    def get_versions(self, article_id: str) -> List[ArticleVersion]:
        with self.get_session() as session:
            return session.query(ArticleVersion).filter_by(
                article_id=article_id
            ).order_by(ArticleVersion.version_number).all()
    
    # Chat History Operations
    def add_chat_message(self, session_id: str, user_message: Optional[str] = None,
                        bot_response: Optional[str] = None, message_type: str = 'chat'):
        with self.get_session() as session:
            chat = ChatHistory(
                session_id=session_id,
                user_message=user_message,
                bot_response=bot_response,
                message_type=message_type
            )
            session.add(chat)
    
    def get_chat_history(self, session_id: str) -> List[ChatHistory]:
        with self.get_session() as session:
            return session.query(ChatHistory).filter_by(
                session_id=session_id
            ).order_by(ChatHistory.timestamp).all()
    
    # Validation Log Operations
    def add_validation_log(self, article_id: str, node_name: str, score: float,
                          feedback: Dict, retry_count: int, status: str):
        with self.get_session() as session:
            log = ValidationLog(
                article_id=article_id,
                node_name=node_name,
                score=score,
                feedback=feedback,
                retry_count=retry_count,
                status=status
            )
            session.add(log)
            logger.log_node_execution(article_id, node_name, status, score)
    
    def get_validation_logs(self, article_id: str) -> List[ValidationLog]:
        with self.get_session() as session:
            return session.query(ValidationLog).filter_by(
                article_id=article_id
            ).order_by(ValidationLog.timestamp).all()
    
    # Queue Operations
    def add_to_queue(self, session_id: str) -> int:
        with self.get_session() as session:
            # Get current queue length
            position = session.query(ArticleQueue).filter_by(status='queued').count() + 1
            
            queue_item = ArticleQueue(
                session_id=session_id,
                position=position,
                status='queued'
            )
            session.add(queue_item)
            logger.info(f"Added session {session_id} to queue at position {position}")
            return position
    
    def update_queue_status(self, session_id: str, status: str):
        with self.get_session() as session:
            queue_item = session.query(ArticleQueue).filter_by(session_id=session_id).first()
            if queue_item:
                queue_item.status = status
                if status == 'processing':
                    queue_item.started_at = datetime.utcnow()
                elif status == 'completed':
                    queue_item.completed_at = datetime.utcnow()
    
    def get_queue_position(self, session_id: str) -> Optional[int]:
        with self.get_session() as session:
            queue_item = session.query(ArticleQueue).filter_by(session_id=session_id).first()
            return queue_item.position if queue_item else None
    
    def get_processing_count(self) -> int:
        with self.get_session() as session:
            return session.query(ArticleQueue).filter_by(status='processing').count()
    
    def get_next_in_queue(self) -> Optional[str]:
        with self.get_session() as session:
            queue_item = session.query(ArticleQueue).filter_by(
                status='queued'
            ).order_by(ArticleQueue.position).first()
            return queue_item.session_id if queue_item else None
    
    # Checkpoint Operations
    def save_checkpoint(self, checkpoint_id: str, article_id: str, 
                       node_name: str, state_data: Dict):
        with self.get_session() as session:
            checkpoint = Checkpoint(
                id=checkpoint_id,
                article_id=article_id,
                node_name=node_name,
                state_data=state_data
            )
            session.add(checkpoint)
            logger.log_checkpoint(article_id, checkpoint_id, node_name)
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        with self.get_session() as session:
            return session.query(Checkpoint).filter_by(id=checkpoint_id).first()
    
    def get_article_checkpoints(self, article_id: str) -> List[Checkpoint]:
        with self.get_session() as session:
            return session.query(Checkpoint).filter_by(
                article_id=article_id
            ).order_by(desc(Checkpoint.timestamp)).all()
    
    # Analytics Operations
    def add_analytics(self, article_id: str, metric_name: str, 
                     metric_value: float, metadata: Optional[Dict] = None):
        with self.get_session() as session:
            analytics = Analytics(
                article_id=article_id,
                metric_name=metric_name,
                metric_value=metric_value,
                meta_info=metadata or {}
            )
            session.add(analytics)
    
    def get_analytics(self, article_id: Optional[str] = None) -> List[Analytics]:
        with self.get_session() as session:
            query = session.query(Analytics)
            if article_id:
                query = query.filter_by(article_id=article_id)
            return query.order_by(desc(Analytics.timestamp)).all()

db_ops = DatabaseOperations()

