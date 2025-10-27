from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(String, primary_key=True)
    session_id = Column(String, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String, nullable=False)
    article_metadata = Column(JSON)  # Changed from 'metadata' to 'article_metadata'
    status = Column(String, default='draft')  # draft, processing, completed, failed
    overall_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    versions = relationship("ArticleVersion", back_populates="article", cascade="all, delete-orphan")
    validations = relationship("ValidationLog", back_populates="article", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="article", cascade="all, delete-orphan")

class ArticleVersion(Base):
    __tablename__ = 'article_versions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String, ForeignKey('articles.id'))
    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    scores = Column(JSON)
    node_name = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    article = relationship("Article", back_populates="versions")

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    user_message = Column(Text)
    bot_response = Column(Text)
    message_type = Column(String, default='chat')  # chat, system, error
    timestamp = Column(DateTime, default=datetime.utcnow)

class ValidationLog(Base):
    __tablename__ = 'validation_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String, ForeignKey('articles.id'))
    node_name = Column(String, nullable=False)
    score = Column(Float)
    feedback = Column(JSON)
    retry_count = Column(Integer, default=0)
    status = Column(String)  # passed, failed, retrying
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    article = relationship("Article", back_populates="validations")

class ArticleQueue(Base):
    __tablename__ = 'article_queue'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, index=True)
    position = Column(Integer)
    status = Column(String, default='queued')  # queued, processing, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class Checkpoint(Base):
    __tablename__ = 'checkpoints'
    
    id = Column(String, primary_key=True)
    article_id = Column(String, ForeignKey('articles.id'))
    node_name = Column(String, nullable=False)
    state_data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    article = relationship("Article", back_populates="checkpoints")

class Analytics(Base):
    __tablename__ = 'analytics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String)
    metric_name = Column(String)  # generation_time, token_usage, cost, etc.
    metric_value = Column(Float)
    meta_info = Column(JSON)  # Changed from 'metadata' to 'meta_info'
    timestamp = Column(DateTime, default=datetime.utcnow)

