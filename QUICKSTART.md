# Quick Start Guide

## Prerequisites

- Python 3.12 or higher
- Poetry (for dependency management)
- OpenAI API key

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/AreteDriver/test-ai.git
   cd test-ai
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```
   
   Or with pip:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

4. **Initialize the system**
   ```bash
   ./init.sh
   ```

## Running the Application

### Option 1: Streamlit Dashboard (Recommended for beginners)

```bash
./run_dashboard.sh
```

The dashboard will open at http://localhost:8501

### Option 2: FastAPI Server (For API access)

```bash
./run_api.sh
```

The API will be available at http://localhost:8000
API Documentation: http://localhost:8000/docs

## First Steps

### Using the Dashboard

1. **Navigate to Prompts** - View the default prompt templates or create your own
2. **Navigate to Workflows** - Explore example workflows:
   - Simple AI Completion (works without additional API keys)
   - Email to Notion (requires Gmail & Notion credentials)
   - Generate SOP to GitHub (requires GitHub token)
3. **Navigate to Execute** - Run a workflow with custom parameters
4. **Navigate to Logs** - View execution results

### Using the API

1. **Login to get a token:**
   ```bash
   curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"user_id": "demo", "password": "demo"}'
   ```

2. **List available workflows:**
   ```bash
   TOKEN="your-token-here"
   curl http://localhost:8000/workflows \
     -H "Authorization: Bearer $TOKEN"
   ```

3. **Execute a simple workflow:**
   ```bash
   curl -X POST http://localhost:8000/workflows/execute \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "workflow_id": "simple_ai_completion",
       "variables": {"prompt": "Write a haiku about AI"}
     }'
   ```

## Example: Create Your First Workflow

1. Open the dashboard
2. Go to Workflows → Create Workflow
3. Fill in:
   - **Workflow ID**: `my_first_workflow`
   - **Name**: `My First Workflow`
   - **Description**: `A simple workflow to test AI`
   - **Number of Steps**: 1
   - **Step 1**:
     - Step ID: `generate`
     - Type: `openai`
     - Action: `generate_completion`
     - Parameters: `{"prompt": "{{prompt}}", "model": "gpt-4o-mini"}`
4. Save the workflow
5. Go to Execute → Select your workflow → Run it

## Configuration

### Required Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required for OpenAI workflows)
- `ANTHROPIC_API_KEY` - Your Anthropic API key (required for Claude workflows)

### Optional Environment Variables

- `GITHUB_TOKEN` - GitHub personal access token (for GitHub integration)
- `NOTION_TOKEN` - Notion integration token (for Notion integration)
- `GMAIL_CREDENTIALS_PATH` - Path to Gmail OAuth credentials (for Gmail integration)
- `CLAUDE_MODE` - Set to `api` (default) or `cli` for Claude integration mode

### Getting API Credentials

#### OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Add it to `.env` as `OPENAI_API_KEY`

#### Anthropic API Key (for Claude)
1. Go to https://console.anthropic.com/settings/keys
2. Create a new API key
3. Add it to `.env` as `ANTHROPIC_API_KEY`

#### GitHub Token
1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `write:discussion`
4. Add it to `.env` as `GITHUB_TOKEN`

#### Notion Token
1. Go to https://www.notion.so/my-integrations
2. Create new integration
3. Copy the Internal Integration Token
4. Add it to `.env` as `NOTION_TOKEN`

#### Gmail OAuth
1. Go to https://console.cloud.google.com/
2. Create a project and enable Gmail API
3. Create OAuth 2.0 credentials
4. Download credentials.json
5. Add path to `.env` as `GMAIL_CREDENTIALS_PATH`

## Troubleshooting

### "Module not found" errors
- Ensure you're using Poetry: `poetry run python ...`
- Or set PYTHONPATH: `PYTHONPATH=src python ...`

### API connection errors
- Check that `.env` has valid API keys
- Verify internet connection
- Check API quotas/limits

### Port already in use
- API: Change port in `run_api.sh` (default: 8000)
- Dashboard: Change port with `--server.port` flag (default: 8501)

## Next Steps

- Read the full README.md for detailed documentation
- Explore the example workflows in `src/test_ai/workflows/`
- Create custom prompt templates
- Build multi-step workflows
- Integrate with your own APIs

## Support

For issues or questions:
- Open an issue on GitHub
- Check the API documentation at http://localhost:8000/docs
- Review example workflows in the repository
