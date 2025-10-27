# Medium Article Generator

This project is an AI-powered article generation and validation system that creates high-quality, engaging Medium articles. It uses a multi-agent system to generate, validate, and regenerate content until it meets a set of quality standards.

## Project Overview

The Medium Article Generator is a FastAPI application that provides an API for generating Medium articles. The application uses a sophisticated AI workflow to generate articles, validate them against a set of criteria, and regenerate them if they don't meet the quality standards. The validation process includes checks for structure, language, grammar, length, mathematical equations, depth, readability, and code.

The application is built with the following technologies:

- **FastAPI:** A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.
- **SQLAlchemy:** The Python SQL toolkit and Object Relational Mapper that gives application developers the full power and flexibility of SQL.
- **LangGraph:** A library for building stateful, multi-agent applications with LLMs.
- **OpenAI:** The AI platform that provides the language models used for generation and validation.

## Architecture

The application is divided into the following components:

- **`main.py`:** The entry point of the application. It initializes the FastAPI application and includes the API routes.
- **`app/`:** The main application directory.
  - **`api/`:** Contains the API routes and WebSocket implementation.
  - **`database/`:** Contains the database models and operations.
  - **`utils/`:** Contains utility functions and helper modules.
  - **`validators/`:** Contains the validation logic for the different aspects of the article.
  - **`agents/`:** Contains the AI agents and the LangGraph workflow.
  - **`config.py`:** Contains the application settings.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/medium-article-generator.git
    cd medium-article-generator
    ```
2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```
3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create a `.env` file:**
    ```
    OPENAI_API_KEY="your-openai-api-key"
    SECRET_KEY="your-secret-key"
    ```
5.  **Run the application:**
    ```bash
    uvicorn main:app --reload
    ```

## API Endpoints

- **`POST /api/chat`:** Handles chat messages for requirement gathering.
- **`POST /api/generate-article`:** Starts the article generation process.
- **`GET /api/article/{article_id}`:** Gets an article by its ID.
- **`GET /api/article-status/{session_id}`:** Gets the current status of article generation.
- **`GET /api/validation-report/{article_id}`:** Gets a detailed validation report for an article.
- **`GET /api/articles`:** Gets all articles.
- **`POST /api/time-travel`:** Time travels to a checkpoint and modifies the article.

## Validation and Regeneration

The application uses a multi-step validation process to ensure the quality of the generated articles. The validation process includes the following checks:

- **Structure:** Validates the structure and organization of the article.
- **Language:** Validates the language quality and tone consistency.
- **Grammar:** Validates the grammatical correctness of the article.
- **Length:** Validates the length and pacing of the article.
- **Math:** Validates the mathematical equations and formulas in the article.
- **Depth:** Validates how thoroughly the article covers the topic.
- **Readability:** Validates whether the article is understandable to both beginners and advanced readers.
- **Code:** Validates the code examples in the article.

If an article fails any of these validation checks, it is sent back to the regeneration node, where the AI model improves the article based on the feedback from the validators. This process is repeated until the article meets all the quality standards.
