# AI-Orchestra 🎼

**A Unified Workflow Orchestration Platform for AI-Powered Automation**

AI-Orchestra is a powerful, extensible workflow orchestration system that connects AI services (OpenAI, etc.) with productivity tools (GitHub, Notion, Gmail) through a unified automation layer. Build complex, multi-step workflows with minimal code using our intuitive dashboard or programmatic API.

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## ✨ Features

### 🔄 Workflow Orchestration
- **Multi-Step Workflows**: Chain multiple API calls and operations seamlessly
- **Variable Interpolation**: Pass data between workflow steps dynamically
- **Error Handling**: Robust error tracking and recovery mechanisms
- **Execution Logging**: Complete audit trail of all workflow executions

### 🤖 AI Integration
- **OpenAI Integration**: Text generation, summarization, and content creation
- **Prompt Templates**: Reusable, parameterized prompt library
- **AI-Powered Automation**: Leverage GPT models for intelligent workflows

### 🔗 Third-Party Integrations
- **GitHub**: Create issues, commit files, manage repositories
- **Notion**: Create pages, append content, search databases
- **Gmail**: Read emails, extract content (OAuth 2.0 support)
- **Extensible Architecture**: Easy to add new integrations

### 🎨 User Interfaces
- **Streamlit Dashboard**: Interactive web UI for workflow management
- **REST API**: Full-featured FastAPI backend with auto-generated docs
- **CLI Ready**: Scriptable for automation and CI/CD pipelines

### 🔐 Enterprise-Ready
- **Token-Based Authentication**: Secure API access control
- **Environment Configuration**: Flexible settings management
- **Structured Logging**: JSON-formatted execution logs
- **Type Safety**: Pydantic models for data validation

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** installed on your system
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
- **Poetry** (recommended) or pip for dependency management

### Installation

```bash
# Clone the repository
git clone https://github.com/AreteDriver/AI-Orchestra.git
cd AI-Orchestra

# Install dependencies
pip install -r requirements.txt

# Or using Poetry (recommended)
poetry install

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Initialize default templates
./init.sh
```

### Running the Application

#### Option 1: Streamlit Dashboard (Recommended)

```bash
./run_dashboard.sh
```

Access the dashboard at **http://localhost:8501**

#### Option 2: FastAPI Server

```bash
./run_api.sh
```

API available at **http://localhost:8000**  
Documentation at **http://localhost:8000/docs**

---

## 📖 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Detailed installation and first steps
- **[Implementation Details](IMPLEMENTATION.md)** - Architecture and technical overview
- **[API Documentation](http://localhost:8000/docs)** - Interactive API reference (when running)

---

## 🎯 Example Workflows

### 1. Simple AI Completion
Generate text using OpenAI's GPT models.

```json
{
  "workflow_id": "simple_ai_completion",
  "variables": {
    "prompt": "Write a haiku about automation"
  }
}
```

### 2. Email to Notion Summary
Extract emails from Gmail, summarize with AI, and save to Notion.

```json
{
  "workflow_id": "email_to_notion",
  "variables": {
    "email_query": "is:unread from:important@example.com",
    "notion_page_id": "your-notion-page-id"
  }
}
```

### 3. Generate SOP to GitHub
Create Standard Operating Procedures with AI and commit to GitHub.

```json
{
  "workflow_id": "generate_sop_to_github",
  "variables": {
    "topic": "Deployment Process",
    "repo_name": "your-repo",
    "file_path": "docs/deployment-sop.md"
  }
}
```

---

## 🏗️ Architecture

```
AI-Orchestra/
├── src/test_ai/           # Main application package
│   ├── api.py             # FastAPI REST API
│   ├── api_clients/       # Third-party API integrations
│   │   ├── openai_client.py
│   │   ├── github_client.py
│   │   ├── notion_client.py
│   │   └── gmail_client.py
│   ├── orchestrator/      # Workflow execution engine
│   ├── prompts/           # Template management
│   ├── dashboard/         # Streamlit UI
│   ├── auth/              # Authentication layer
│   └── config/            # Configuration management
├── config/                # Configuration files
├── workflows/             # Workflow definitions (JSON)
└── docs/                  # Additional documentation
```

**Technology Stack:**
- **Backend**: FastAPI, Uvicorn
- **Frontend**: Streamlit
- **AI/ML**: OpenAI SDK
- **Integrations**: PyGithub, Notion SDK, Google API Client
- **Data Validation**: Pydantic
- **Environment**: python-dotenv, pydantic-settings

---

## 🔧 Configuration

### Required Environment Variables

```bash
# .env file
OPENAI_API_KEY=sk-...              # Required for AI features
```

### Optional Environment Variables

```bash
GITHUB_TOKEN=ghp_...                # For GitHub integration
NOTION_TOKEN=secret_...             # For Notion integration
GMAIL_CREDENTIALS_PATH=credentials.json  # For Gmail integration
```

See **[.env.example](.env.example)** for complete configuration options.

---

## 🧪 Testing

```bash
# Run basic tests
python test_basic.py

# Test specific modules
pytest tests/  # (when test suite is added)
```

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

Please ensure your code:
- Follows existing code style
- Includes appropriate tests
- Updates documentation as needed

---

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🔒 Security

### Important Security Notes

- **Never commit** `.env`, `credentials.json`, or `token.json` files
- **Rotate API keys** regularly
- **Use environment variables** for sensitive data
- **Review permissions** for third-party integrations

To report security vulnerabilities, please email: aretedriver@gmail.com

---

## 🗺️ Roadmap

### Upcoming Features
- [ ] Scheduled workflow execution (cron-like)
- [ ] Webhook support for event-driven workflows
- [ ] Visual workflow builder
- [ ] Workflow templates marketplace
- [ ] Additional AI providers (Anthropic, Cohere)
- [ ] Database persistence (PostgreSQL)
- [ ] User management and permissions
- [ ] Monitoring dashboard with metrics

---

## 📞 Support

- **Documentation**: [Quick Start Guide](QUICKSTART.md)
- **Issues**: [GitHub Issues](https://github.com/AreteDriver/AI-Orchestra/issues)
- **Email**: aretedriver@gmail.com

---

## 🙏 Acknowledgments

Built with:
- [OpenAI](https://openai.com) - AI capabilities
- [FastAPI](https://fastapi.tiangolo.com) - Web framework
- [Streamlit](https://streamlit.io) - Dashboard UI
- [Pydantic](https://pydantic.dev) - Data validation

---

**Made with ❤️ by the AI-Orchestra Team**