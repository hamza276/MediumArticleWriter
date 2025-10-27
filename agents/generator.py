import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from app.config import settings
from app.utils.prompts import prompt_templates
from app.utils.logger import logger

class ArticleGenerator:
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.generator_model = settings.GENERATOR_MODEL
        self.validator_model = settings.VALIDATOR_MODEL
    
    async def chat_with_user(self, messages: list) -> AsyncGenerator[str, None]:
        """
        Chat with user to gather requirements
        Streams responses token by token
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.generator_model,
                messages=messages,
                temperature=settings.GENERATOR_TEMPERATURE,
                stream=True
            )
            
            full_response = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield token
            
            logger.log_api_call(self.generator_model, "chat", len(full_response.split()))
            
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            raise
    
    async def generate_article(self, requirements: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Generate article based on gathered requirements
        Streams content token by token
        """
        try:
            prompt = f"""
Generate a Medium article with the following requirements:

Topic: {requirements.get('topic')}
Target Audience: {requirements.get('target_audience')}
Article Type: {requirements.get('article_type')}
Tone: {requirements.get('tone')}
Author: {requirements.get('author')}

Additional Requirements:
{json.dumps(requirements.get('additional_requirements', {}), indent=2)}

Write a comprehensive, engaging Medium article following all best practices.
"""
            
            messages = [
                {"role": "system", "content": prompt_templates.ARTICLE_GENERATOR_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            
            stream = await self.client.chat.completions.create(
                model=self.generator_model,
                messages=messages,
                temperature=settings.GENERATOR_TEMPERATURE,
                max_tokens=4000,
                stream=True
            )
            
            full_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_content += token
                    yield token
            
            logger.log_api_call(self.generator_model, "generation", len(full_content.split()))
            logger.info(f"Generated article with {len(full_content.split())} words")
            
        except Exception as e:
            logger.error(f"Generation error: {str(e)}")
            raise
    
    async def regenerate_content(self, node_name: str, feedback: str, 
                                 current_content: str) -> AsyncGenerator[str, None]:
        """
        Regenerate content based on validator feedback
        """
        try:
            prompt = prompt_templates.get_regeneration_prompt(node_name, feedback, current_content)
            
            messages = [
                {"role": "system", "content": prompt_templates.ARTICLE_GENERATOR_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            
            stream = await self.client.chat.completions.create(
                model=self.generator_model,
                messages=messages,
                temperature=settings.GENERATOR_TEMPERATURE,
                max_tokens=4000,
                stream=True
            )
            
            full_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_content += token
                    yield token
            
            logger.log_api_call(self.generator_model, f"regeneration_{node_name}", len(full_content.split()))
            
        except Exception as e:
            logger.error(f"Regeneration error: {str(e)}")
            raise
    
    async def validate_content(self, validator_type: str, content: str, 
                              metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate content using specified validator
        Returns validation results as JSON
        """
        try:
            system_prompt, user_prompt = prompt_templates.get_validator_prompt(
                validator_type, content, metadata
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.validator_model,
                messages=messages,
                temperature=settings.VALIDATOR_TEMPERATURE,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.log_api_call(self.validator_model, f"validation_{validator_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"Validation error for {validator_type}: {str(e)}")
            raise

generator = ArticleGenerator()

