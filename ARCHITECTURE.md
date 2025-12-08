# AI-Orchestra Architecture

## Overview

AI-Orchestra is built as a modular, extensible workflow orchestration platform. This document provides a detailed technical overview of the system architecture, design decisions, and implementation patterns.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                            │
│  ┌──────────────────┐         ┌──────────────────────┐     │
│  │  Streamlit UI    │         │   REST API Clients   │     │
│  │  (Dashboard)     │         │   (curl, SDK, etc)   │     │
│  └──────────────────┘         └──────────────────────┘     │
└────────────┬──────────────────────────┬───────────────────┘
             │                          │
             v                          v
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              FastAPI REST API                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │   │
│  │  │  Auth    │ │ Workflow │ │    Prompts       │    │   │
│  │  │ Routes   │ │  Routes  │ │    Routes        │    │   │
│  │  └──────────┘ └──────────┘ └──────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────────────┘
             │
             v
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                      │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │ Workflow     │  │   Prompt      │  │     Auth      │   │
│  │   Engine     │  │  Template     │  │    Manager    │   │
│  │              │  │   Manager     │  │               │   │
│  └──────────────┘  └───────────────┘  └───────────────┘   │
└────────────┬────────────────────────────────────────────────┘
             │
             v
┌─────────────────────────────────────────────────────────────┐
│                   Integration Layer                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ OpenAI  │  │ GitHub  │  │ Notion  │  │  Gmail  │       │
│  │ Client  │  │ Client  │  │ Client  │  │ Client  │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└────────────┬────────────────────────────────────────────────┘
             │
             v
┌─────────────────────────────────────────────────────────────┐
│                   External Services                         │
│     OpenAI API  │  GitHub API  │  Notion API  │  Gmail      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Workflow Engine (`src/test_ai/orchestrator/`)

The heart of the system, responsible for executing multi-step workflows.

#### Key Responsibilities
- Parse workflow definitions (JSON)
- Execute steps sequentially
- Handle variable interpolation
- Manage error handling and recovery
- Log execution results

#### Workflow Model

```python
class WorkflowStep:
    step_id: str           # Unique identifier
    step_type: str         # API client type (openai, github, etc.)
    action: str            # Action to perform
    parameters: dict       # Action parameters (supports {{var}} interpolation)

class Workflow:
    workflow_id: str       # Unique workflow identifier
    name: str              # Human-readable name
    description: str       # Workflow description
    steps: List[WorkflowStep]
    variables: dict        # Runtime variables

class WorkflowResult:
    success: bool          # Execution status
    outputs: dict          # Step outputs
    errors: List[str]      # Error messages
```

#### Execution Flow

1. **Load Workflow**: Read JSON definition from disk
2. **Validate**: Check workflow structure and required fields
3. **Initialize**: Set up variables and context
4. **Execute Steps**: For each step:
   - Interpolate variables in parameters
   - Call appropriate API client
   - Store results in outputs
   - Handle errors gracefully
5. **Log Results**: Write execution log to disk
6. **Return Results**: Provide success status and outputs

#### Variable Interpolation

Supports template syntax: `{{variable_name}}`

```python
# Example: Reference previous step output
{
  "step_id": "step2",
  "parameters": {
    "content": "{{step1_output}}"
  }
}
```

### 2. API Clients (`src/test_ai/api_clients/`)

Abstraction layer for third-party integrations.

#### Design Pattern

Each client follows a consistent interface:

```python
class BaseAPIClient:
    def __init__(self, config: dict):
        """Initialize with configuration."""
        
    def execute_action(self, action: str, params: dict) -> dict:
        """Execute an action and return results."""
```

#### OpenAI Client

**Capabilities:**
- Text generation (GPT-4, GPT-3.5)
- Chat completions
- Streaming support
- Model configuration

**Actions:**
- `generate_completion`: Generate text from prompt
- `chat_completion`: Chat-based interaction

#### GitHub Client

**Capabilities:**
- Repository management
- Issue creation/update
- File operations
- Branch management

**Actions:**
- `create_issue`: Create GitHub issue
- `create_file`: Commit file to repository
- `list_repos`: List user repositories

#### Notion Client

**Capabilities:**
- Page creation
- Block management
- Database queries
- Search

**Actions:**
- `create_page`: Create new Notion page
- `append_content`: Add content to page
- `search`: Search Notion workspace

#### Gmail Client

**Capabilities:**
- Email reading
- OAuth 2.0 authentication
- Query-based filtering
- Message parsing

**Actions:**
- `list_messages`: Get emails by query
- `get_message`: Fetch email content
- `search`: Search emails

### 3. Prompt Template Manager (`src/test_ai/prompts/`)

Manages reusable prompt templates.

#### Template Model

```python
class PromptTemplate:
    template_id: str       # Unique identifier
    name: str              # Human-readable name
    description: str       # Template description
    template: str          # Prompt text with {{variables}}
    variables: List[str]   # Required variables
```

#### Features

- **CRUD Operations**: Create, read, update, delete templates
- **Variable Validation**: Ensure all required variables provided
- **Template Rendering**: Substitute variables with values
- **Persistence**: JSON-based storage

#### Usage Pattern

```python
manager = PromptTemplateManager()

# Create template
template = PromptTemplate(
    template_id="email_summary",
    name="Email Summary",
    template="Summarize this email: {{email_content}}"
)
manager.save_template(template)

# Render with variables
rendered = manager.render_template(
    "email_summary",
    {"email_content": "..."}
)
```

### 4. Authentication System (`src/test_ai/auth/`)

Token-based authentication for API access.

#### Components

- **Token Generation**: Create JWT tokens
- **Token Validation**: Verify token authenticity
- **Expiration Management**: Handle token lifecycle
- **User Sessions**: Track authenticated users

#### Security Features

- **Secret Key**: Configurable secret for token signing
- **Expiration**: Tokens expire after configurable duration
- **Stateless**: No server-side session storage
- **Bearer Token**: Standard HTTP authorization header

### 5. Configuration Management (`src/test_ai/config/`)

Centralized configuration using Pydantic Settings.

#### Configuration Sources

1. **Environment Variables** (highest priority)
2. **.env file**
3. **Default values** (lowest priority)

#### Settings Model

```python
class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    github_token: Optional[str]
    notion_token: Optional[str]
    
    # Paths
    workflows_dir: Path
    prompts_dir: Path
    logs_dir: Path
    
    # Auth
    secret_key: str
    access_token_expire_minutes: int
```

### 6. REST API (`src/test_ai/api.py`)

FastAPI-based REST API for programmatic access.

#### Endpoint Groups

**Authentication**
- `POST /auth/login` - Get access token
- `POST /auth/verify` - Verify token

**Workflows**
- `GET /workflows` - List all workflows
- `GET /workflows/{id}` - Get specific workflow
- `POST /workflows` - Create workflow
- `POST /workflows/execute` - Execute workflow
- `DELETE /workflows/{id}` - Delete workflow

**Prompts**
- `GET /prompts` - List all prompts
- `GET /prompts/{id}` - Get specific prompt
- `POST /prompts` - Create prompt
- `PUT /prompts/{id}` - Update prompt
- `DELETE /prompts/{id}` - Delete prompt

**System**
- `GET /health` - Health check
- `GET /docs` - OpenAPI documentation

#### Middleware

- **CORS**: Cross-origin resource sharing
- **Authentication**: Token verification
- **Error Handling**: Consistent error responses
- **Logging**: Request/response logging

### 7. Dashboard (`src/test_ai/dashboard/`)

Streamlit-based web interface.

#### Pages

1. **Home**: Overview and status
2. **Workflows**: Browse and manage workflows
3. **Execute**: Run workflows with custom parameters
4. **Prompts**: Manage prompt templates
5. **Logs**: View execution history
6. **Settings**: Configure system

#### Features

- **Interactive Forms**: Create/edit workflows
- **Real-time Execution**: Run workflows from UI
- **Log Viewer**: Browse execution logs
- **Template Editor**: Manage prompts

## Data Flow

### Workflow Execution Flow

```
User Request
    ↓
API/Dashboard
    ↓
Workflow Engine (validate workflow)
    ↓
For each step:
    ↓
Variable Interpolation
    ↓
API Client Router (select client)
    ↓
Execute Action (external API call)
    ↓
Store Result
    ↓
Next Step (use previous outputs)
    ↓
Log Results
    ↓
Return to User
```

### Example: Email to Notion Workflow

```
1. Gmail Client
   ↓ fetch emails matching query
   emails_data
   
2. OpenAI Client
   ↓ summarize email content
   summary_text
   
3. Notion Client
   ↓ create page with summary
   notion_page_id
   
4. Return Results
```

## Design Patterns

### 1. Factory Pattern

API clients use factory pattern for dynamic instantiation:

```python
def get_api_client(client_type: str) -> BaseAPIClient:
    clients = {
        "openai": OpenAIClient,
        "github": GitHubClient,
        "notion": NotionClient,
        "gmail": GmailClient
    }
    return clients[client_type]()
```

### 2. Strategy Pattern

Different execution strategies for different step types:

```python
class WorkflowEngine:
    def execute_step(self, step: WorkflowStep):
        client = get_api_client(step.step_type)
        return client.execute_action(step.action, step.parameters)
```

### 3. Template Method Pattern

Common workflow execution flow with customizable steps:

```python
def execute_workflow(workflow: Workflow):
    validate()      # Common
    setup()         # Common
    execute_steps() # Variable
    cleanup()       # Common
    log_results()   # Common
```

### 4. Dependency Injection

Configuration and dependencies injected via Pydantic:

```python
settings = get_settings()  # Singleton
client = OpenAIClient(settings.openai_api_key)
```

## Error Handling

### Error Hierarchy

```
WorkflowError (base)
├── ValidationError (invalid workflow)
├── ExecutionError (step execution failed)
├── ConfigurationError (missing config)
└── AuthenticationError (invalid credentials)
```

### Error Handling Strategy

1. **Validation Errors**: Fail fast before execution
2. **Execution Errors**: Log error, continue or abort
3. **API Errors**: Retry with exponential backoff
4. **User Errors**: Return clear error messages

## Logging

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical failures

### Log Structure

```json
{
  "timestamp": "2024-12-08T20:00:00Z",
  "workflow_id": "simple_ai_completion",
  "execution_id": "uuid",
  "status": "success",
  "steps": [
    {
      "step_id": "generate",
      "status": "success",
      "output": "...",
      "duration_ms": 1234
    }
  ]
}
```

## Security Considerations

### Authentication
- Token-based authentication required for API
- Secure token generation using secrets
- Token expiration enforced

### API Keys
- Stored in environment variables
- Never logged or exposed in responses
- Validated on startup

### Data Handling
- No sensitive data in logs
- OAuth tokens stored securely
- HTTPS recommended for production

## Performance

### Optimization Strategies

1. **Async Operations**: FastAPI async endpoints
2. **Connection Pooling**: Reuse HTTP connections
3. **Caching**: Cache frequent API responses
4. **Lazy Loading**: Load workflows on demand

### Scalability

- **Horizontal**: Run multiple API instances
- **Vertical**: Increase resources per instance
- **Queue**: Add task queue for async execution

## Testing Strategy

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- High coverage target (>80%)

### Integration Tests
- Test component interactions
- Use test API credentials
- Verify end-to-end flows

### End-to-End Tests
- Test complete user workflows
- Validate UI functionality
- Check API contracts

## Deployment

### Development
```bash
./run_api.sh      # API on localhost:8000
./run_dashboard.sh # Dashboard on localhost:8501
```

### Production Considerations

1. **Environment Variables**: Use production secrets
2. **HTTPS**: Enable SSL/TLS
3. **Database**: Add persistent storage
4. **Monitoring**: Add APM and logging
5. **Scaling**: Use load balancer
6. **Backup**: Regular workflow/config backups

## Future Enhancements

### Planned Features

1. **Database Integration**: PostgreSQL for persistence
2. **Async Execution**: Background job processing
3. **Webhooks**: Event-driven workflows
4. **Monitoring**: Metrics and alerts
5. **Multi-tenancy**: User isolation
6. **Workflow Versioning**: Version control for workflows
7. **Visual Editor**: Drag-and-drop workflow builder
8. **Plugin System**: Custom integrations

### Technical Debt

- Add comprehensive test suite
- Implement connection pooling
- Add request rate limiting
- Improve error recovery
- Add workflow retry logic

## Conclusion

AI-Orchestra is designed with modularity, extensibility, and maintainability in mind. The architecture supports easy addition of new integrations, workflow types, and features while maintaining a clean separation of concerns.
