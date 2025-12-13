# 🎼 AI-Orchestra

> **Enterprise-grade AI workflow orchestration platform** - Unify ChatGPT, Notion, Gmail, and GitHub through intelligent automation pipelines.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Usage Examples](#-usage-examples)
- [API Reference](#-api-reference)
- [Workflow Examples](#-workflow-examples)
- [Configuration](#-configuration)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**AI-Orchestra** is a powerful Python-based workflow orchestration platform that enables you to create, manage, and execute complex AI-powered automation workflows. It provides a unified interface for integrating multiple AI services and productivity tools, making it ideal for:

- **AI-Powered Automation**: Leverage GPT-4 for intelligent content processing
- **Multi-Service Integration**: Connect OpenAI, GitHub, Notion, and Gmail seamlessly
- **Workflow Orchestration**: Chain multiple operations into reusable, configurable pipelines
- **Enterprise Solutions**: Build production-ready automation for business processes

### 🎯 Purpose

AI-Orchestra bridges the gap between AI capabilities and practical business automation by providing:

1. **Unified API Layer**: Single interface for multiple AI and productivity services
2. **Declarative Workflows**: Define complex automations in simple JSON configurations
3. **Template System**: Reusable prompt templates for consistent AI interactions
4. **Dual Interface**: Both REST API and interactive dashboard for flexibility

### 🛠️ Technologies

- **Backend**: Python 3.12+, FastAPI, Pydantic
- **Frontend**: Streamlit dashboard
- **AI/ML**: OpenAI GPT-4 & GPT-3.5-turbo
- **Integrations**: GitHub API, Notion API, Gmail API
- **Auth**: JWT tokens, OAuth 2.0
- **Storage**: JSON/YAML-based configuration

### 💼 Use Cases

- **Email Processing**: Automatically summarize and organize emails into Notion
- **Documentation Generation**: Create SOPs and technical docs with AI assistance
- **Code Management**: Generate commit messages, create issues, automate PRs
- **Content Pipelines**: Build multi-step content processing workflows
- **Report Automation**: Generate and distribute reports across platforms
- **Task Automation**: Intelligent task routing and execution

---

## ✨ Features

### 🔧 Core Capabilities

#### **Modular Architecture**
- **Pluggable Components**: Each integration is an independent module
- **Separation of Concerns**: Clean boundaries between workflow, auth, and API layers
- **Easy Extension**: Add new services without modifying core engine
- **Type-Safe**: Full Pydantic validation for all data models

#### **Flexible Workflow System**
- **Multi-Step Pipelines**: Chain unlimited operations in sequence
- **Variable Interpolation**: Pass data between workflow steps dynamically
- **Error Handling**: Robust error tracking and recovery mechanisms
- **Execution Logging**: Complete audit trail for all workflow runs
- **Workflow Persistence**: Save and reuse workflow definitions

#### **Intelligent Prompt Management**
- **Template Library**: Reusable prompt templates with variable substitution
- **CRUD Operations**: Create, read, update, delete templates via API
- **Default Templates**: Pre-built templates for common tasks
- **Format Validation**: Ensure prompts are properly structured

#### **Enterprise-Ready Features**
- **Authentication**: Token-based auth with JWT
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Health Checks**: Monitor system status
- **Logging**: Comprehensive execution and error logs
- **Configuration Management**: Environment-based settings

### 🎨 User Interfaces

#### **Streamlit Dashboard**
- Interactive workflow creation and execution
- Real-time execution monitoring
- Template management UI
- Execution log viewer
- Multi-page navigation

#### **REST API**
- 15+ endpoints for programmatic access
- Authentication middleware
- JSON request/response
- Rate limiting ready
- Fully documented

### 🔌 Integrations

#### **OpenAI**
- Text generation and completion
- Content summarization
- SOP generation
- Multiple model support (GPT-4, GPT-3.5)

#### **GitHub**
- Issue creation
- File commits
- Repository management
- Organization listing

#### **Notion**
- Page creation
- Content appending
- Database queries
- Search functionality

#### **Gmail**
- Message listing
- Content extraction
- OAuth 2.0 authentication
- Label management

---

## 🏗️ Architecture

AI-Orchestra follows a modular, layered architecture designed for scalability and maintainability:

```
┌─────────────────────────────────────────────────────────┐
│           User Interface Layer                          │
│  ┌──────────────────┐      ┌──────────────────┐        │
│  │ Streamlit        │      │ FastAPI          │        │
│  │ Dashboard        │      │ REST API         │        │
│  └──────────────────┘      └──────────────────┘        │
└─────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Core Engine Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Workflow │  │  Prompt  │  │   Auth   │             │
│  │  Engine  │  │ Manager  │  │  Layer   │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│           Integration Layer                             │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐       │
│  │ OpenAI │  │ GitHub │  │ Notion │  │ Gmail  │       │
│  │ Client │  │ Client │  │ Client │  │ Client │       │
│  └────────┘  └────────┘  └────────┘  └────────┘       │
└─────────────────────────────────────────────────────────┘
```

For detailed architecture diagrams and component interactions, see [docs/architecture.md](docs/architecture.md).

### 📂 Project Structure

> **Note**: The Python package is named `test_ai` internally. This is the import name used in code examples throughout the documentation.

```
AI-Orchestra/
├── src/test_ai/              # Main application package (Python import name)
│   ├── api.py                # FastAPI backend
│   ├── main.py               # Original demo script
│   ├── auth/                 # Authentication module
│   ├── api_clients/          # External API integrations
│   │   ├── openai_client.py
│   │   ├── github_client.py
│   │   ├── notion_client.py
│   │   └── gmail_client.py
│   ├── orchestrator/         # Workflow engine
│   ├── prompts/              # Template management
│   ├── dashboard/            # Streamlit UI
│   ├── config/               # Configuration management
│   └── workflows/            # Example workflow definitions
├── docs/                     # Documentation
│   └── architecture.md       # Architecture diagrams
├── config/                   # Configuration files
│   ├── settings.example.yaml
│   └── prompts.example.json
├── .env.example              # Environment template
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Poetry configuration
├── README.md                 # This file
├── QUICKSTART.md             # Getting started guide
└── IMPLEMENTATION.md         # Implementation details
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Optional: GitHub, Notion, Gmail credentials for full functionality

### Installation

```bash
# Clone the repository
git clone https://github.com/AreteDriver/AI-Orchestra.git
cd AI-Orchestra

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Initialize system
./init.sh
```

### Running the Application

#### Option 1: Dashboard (Recommended)

```bash
./run_dashboard.sh
```
Open http://localhost:8501 in your browser.

#### Option 2: API Server

```bash
./run_api.sh
```
API available at http://localhost:8000  
Documentation at http://localhost:8000/docs

### First Workflow

Try the simple AI completion workflow:

```bash
# Via API
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "password": "demo"}'

# Use the token to execute a workflow
curl -X POST http://localhost:8000/workflows/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "simple_ai_completion",
    "variables": {"prompt": "Write a haiku about AI"}
  }'
```

Or use the dashboard: Navigate to **Execute** → Select **simple_ai_completion** → Run!

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md).

---

## 💡 Usage Examples

### Example 1: Simple AI Text Generation

```python
from test_ai import WorkflowEngine, Workflow, WorkflowStep, StepType

# Create workflow
engine = WorkflowEngine()
workflow = Workflow(
    id="my_workflow",
    name="Simple Text Generation",
    description="Generate text with AI",
    steps=[
        WorkflowStep(
            id="generate",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": "{{user_prompt}}",
                "model": "gpt-4o-mini"
            }
        )
    ],
    variables={"user_prompt": "Explain quantum computing"}
)

# Execute
result = engine.execute_workflow(workflow)
print(result.outputs)
```

### Example 2: Email to Notion Pipeline

This workflow fetches emails, summarizes them with AI, and saves to Notion:

```json
{
  "id": "email_to_notion",
  "name": "Email Summary to Notion",
  "steps": [
    {
      "id": "fetch_email",
      "type": "gmail",
      "action": "get_messages",
      "params": {"max_results": 1}
    },
    {
      "id": "summarize",
      "type": "openai",
      "action": "generate_completion",
      "params": {
        "prompt": "Summarize this email: {{fetch_email.body}}"
      }
    },
    {
      "id": "save_to_notion",
      "type": "notion",
      "action": "create_page",
      "params": {
        "title": "Email Summary",
        "content": "{{summarize.response}}"
      }
    }
  ]
}
```

### Example 3: SOP Generation to GitHub

Generate standard operating procedures and commit them to GitHub:

```python
from test_ai import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.load_workflow("generate_sop_to_github")

# Customize variables
workflow.variables["sop_topic"] = "Customer Onboarding Process"
workflow.variables["repo"] = "my-company/docs"

# Execute
result = engine.execute_workflow(workflow)
print(f"SOP committed to: {result.outputs['github_url']}")
```

### Example 4: Batch Processing

Process multiple items in a workflow:

```python
emails = ["email1@example.com", "email2@example.com"]
results = []

for email in emails:
    workflow.variables["email_address"] = email
    result = engine.execute_workflow(workflow)
    results.append(result)

# Process results
for i, result in enumerate(results):
    print(f"Email {i+1}: {result.status}")
```

---

## 🔌 API Reference

### Authentication

```bash
POST /auth/login
Content-Type: application/json

{
  "user_id": "demo",
  "password": "demo"
}

Response: {
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### Workflow Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/workflows` | GET | List all workflows |
| `/workflows/{id}` | GET | Get workflow details |
| `/workflows` | POST | Create new workflow |
| `/workflows/{id}` | PUT | Update workflow |
| `/workflows/{id}` | DELETE | Delete workflow |
| `/workflows/execute` | POST | Execute workflow |

### Prompt Template Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/prompts` | GET | List all templates |
| `/prompts/{id}` | GET | Get template details |
| `/prompts` | POST | Create new template |
| `/prompts/{id}` | PUT | Update template |
| `/prompts/{id}` | DELETE | Delete template |

### Example API Calls

```bash
# List workflows
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/workflows

# Get workflow
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/workflows/simple_ai_completion

# Execute workflow
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "my_workflow", "variables": {"key": "value"}}' \
  http://localhost:8000/workflows/execute
```

Full API documentation available at: http://localhost:8000/docs

---

## 📝 Workflow Examples

### Pre-built Workflows

AI-Orchestra includes several example workflows in `src/test_ai/workflows/`:

#### 1. Simple AI Completion
**Purpose**: Basic text generation with OpenAI  
**Use Case**: Quick AI responses, brainstorming, content generation

```json
{
  "id": "simple_ai_completion",
  "name": "Simple AI Completion",
  "description": "Generate text using OpenAI",
  "steps": [
    {
      "id": "generate",
      "type": "openai",
      "action": "generate_completion",
      "params": {
        "prompt": "{{prompt}}",
        "model": "gpt-4o-mini"
      }
    }
  ],
  "variables": {
    "prompt": "Write a creative story"
  }
}
```

#### 2. Email to Notion Summary
**Purpose**: Process emails and save summaries to Notion  
**Use Case**: Email organization, meeting notes, inbox management

**Required**: Gmail OAuth, Notion token

#### 3. Generate SOP to GitHub
**Purpose**: Create standard operating procedures and commit to repository  
**Use Case**: Documentation automation, process standardization

**Required**: GitHub token

### Creating Custom Workflows

Workflows are defined in JSON with the following structure:

```json
{
  "id": "unique_workflow_id",
  "name": "Human-Readable Name",
  "description": "What this workflow does",
  "steps": [
    {
      "id": "step_1",
      "type": "openai|github|notion|gmail|transform",
      "action": "action_name",
      "params": {
        "param1": "{{variable}}",
        "param2": "static_value"
      },
      "next_step": "step_2"
    }
  ],
  "variables": {
    "variable": "default_value"
  }
}
```

**Step Types:**
- `openai`: AI text generation
- `github`: Repository operations
- `notion`: Page and database operations
- `gmail`: Email operations
- `transform`: Data transformation

**Variable Interpolation:**
- Use `{{variable_name}}` to reference workflow variables
- Use `{{step_id.output_key}}` to reference previous step outputs

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your API credentials:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional integrations
GITHUB_TOKEN=ghp_...
NOTION_TOKEN=secret_...
GMAIL_CREDENTIALS_PATH=./credentials.json

# Application settings (optional)
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

### Configuration Files

**settings.yaml**: Application configuration
```yaml
app:
  name: AI Workflow Orchestrator
  host: 127.0.0.1
  port: 8000

integrations:
  openai:
    model: "gpt-4o-mini"
  github:
    repo: "owner/repo"
```

**prompts.json**: Prompt templates
```json
{
  "template_id": {
    "system": "System prompt",
    "user_template": "User prompt with {variables}"
  }
}
```

### Getting API Credentials

- **OpenAI**: https://platform.openai.com/api-keys
- **GitHub**: https://github.com/settings/tokens (scopes: `repo`)
- **Notion**: https://www.notion.so/my-integrations
- **Gmail**: https://console.cloud.google.com/ (enable Gmail API, create OAuth credentials)

---

## 🧪 Development

### Running Tests

```bash
# Basic tests
PYTHONPATH=src python test_basic.py

# With pytest (when available)
pytest tests/
```

### Code Style

This project follows Python best practices:
- Type hints for all functions
- Pydantic models for data validation
- Modular architecture with clear separation of concerns
- Comprehensive docstrings

### Adding New Integrations

1. Create a new client in `src/test_ai/api_clients/`
2. Implement the required methods
3. Register the client in the workflow engine
4. Add configuration to `settings.yaml`

Example:

```python
# src/test_ai/api_clients/my_service_client.py
from test_ai.config import get_settings

class MyServiceClient:
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.my_service_api_key
    
    def perform_action(self, param: str) -> dict:
        # Implementation
        return {"result": "success"}
```

### Project Setup for Development

```bash
# Using Poetry (recommended)
poetry install
poetry shell

# Using pip
pip install -r requirements.txt
```

2. Create a `.env` file with these variables:

```
AI_API_KEY=your_ai_api_key
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASS=supersecret
IMAP_HOST=imap.example.com
IMAP_USER=you@example.com
IMAP_PASS=supersecret
API_KEY=some-internal-api-key
```

3. Run the app:

```bash
uvicorn app.main:app --reload
```

Endpoints
- GET /health
  - Returns: {"status": "ok"}

- POST /generate
  - Body: { "prompt": "Write a short follow-up email about X" }
  - Returns: { "text": "..." }
  - Uses: Calls an AI provider endpoint (replace the placeholder URL in code with your provider).

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
```

---

## 🤝 Contributing

Contributions are welcome! This project demonstrates advanced Python and workflow management capabilities.

### Areas for Enhancement

- Additional API integrations (Slack, Discord, Jira, etc.)
- Workflow versioning and rollback
- Visual workflow builder
- Scheduled workflow execution
- Webhook triggers
- Advanced error handling and retry logic
- Database backend (PostgreSQL)
- Async workflow execution
- Workflow marketplace

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 AreteDriver

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 📞 Support & Contact

- **Issues**: [GitHub Issues](https://github.com/AreteDriver/AI-Orchestra/issues)
- **Documentation**: See [QUICKSTART.md](QUICKSTART.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md)
- **API Docs**: http://localhost:8000/docs (when running)

---

## 🌟 Showcase

**AI-Orchestra** demonstrates:
- ✅ Advanced Python development with modern frameworks
- ✅ API integration and orchestration expertise
- ✅ AI/ML implementation and prompt engineering
- ✅ Full-stack development (Backend + Frontend)
- ✅ Clean architecture and design patterns
- ✅ Production-ready code with proper auth, logging, and error handling
- ✅ Comprehensive documentation

Perfect for portfolios, consulting projects, or as a foundation for enterprise AI automation.

---

**Built with ❤️ using Python, FastAPI, and OpenAI**
