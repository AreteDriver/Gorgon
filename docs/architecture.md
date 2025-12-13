# AI-Orchestra Architecture

## System Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        Dashboard[Streamlit Dashboard]
        API[FastAPI REST API]
    end
    
    subgraph "Core Engine"
        Auth[Authentication<br/>Token-based Auth]
        WE[Workflow Engine<br/>Orchestration Logic]
        PM[Prompt Manager<br/>Template System]
    end
    
    subgraph "Integration Layer"
        OAI[OpenAI Client<br/>GPT-4 & GPT-3.5]
        GH[GitHub Client<br/>Issues & Commits]
        NOT[Notion Client<br/>Pages & Databases]
        GM[Gmail Client<br/>OAuth & Messages]
    end
    
    subgraph "Data Layer"
        WF[Workflow Storage<br/>JSON Files]
        PT[Prompt Templates<br/>JSON Files]
        LOG[Execution Logs<br/>JSON Files]
    end
    
    Dashboard --> Auth
    API --> Auth
    Auth --> WE
    Auth --> PM
    WE --> OAI
    WE --> GH
    WE --> NOT
    WE --> GM
    WE --> WF
    PM --> PT
    WE --> LOG
    
    style Dashboard fill:#e1f5ff
    style API fill:#e1f5ff
    style WE fill:#fff4e1
    style Auth fill:#ffe1e1
    style OAI fill:#e8f5e9
    style GH fill:#e8f5e9
    style NOT fill:#e8f5e9
    style GM fill:#e8f5e9
```

## Workflow Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Dashboard/API
    participant Auth
    participant WorkflowEngine
    participant APIClients
    participant ExternalAPIs
    
    User->>Dashboard/API: Execute Workflow
    Dashboard/API->>Auth: Verify Token
    Auth-->>Dashboard/API: Authenticated
    Dashboard/API->>WorkflowEngine: Load Workflow Definition
    WorkflowEngine->>WorkflowEngine: Initialize Variables
    
    loop For Each Step
        WorkflowEngine->>WorkflowEngine: Interpolate Variables
        WorkflowEngine->>APIClients: Execute Step Action
        APIClients->>ExternalAPIs: API Call
        ExternalAPIs-->>APIClients: Response
        APIClients-->>WorkflowEngine: Step Result
        WorkflowEngine->>WorkflowEngine: Update Variables
        WorkflowEngine->>WorkflowEngine: Log Step Execution
    end
    
    WorkflowEngine->>WorkflowEngine: Generate Execution Log
    WorkflowEngine-->>Dashboard/API: Workflow Result
    Dashboard/API-->>User: Display Results
```

## Data Flow Architecture

```mermaid
flowchart LR
    subgraph Input
        Email[Email/Gmail]
        Manual[Manual Input]
        API_Input[API Request]
    end
    
    subgraph Processing
        WE[Workflow Engine]
        AI[AI Processing<br/>OpenAI GPT]
        Transform[Data Transformation]
    end
    
    subgraph Output
        Notion[Notion Pages]
        GitHub[GitHub Issues/Commits]
        Response[API Response]
    end
    
    Email --> WE
    Manual --> WE
    API_Input --> WE
    
    WE --> AI
    AI --> Transform
    Transform --> WE
    
    WE --> Notion
    WE --> GitHub
    WE --> Response
    
    style Email fill:#e3f2fd
    style Manual fill:#e3f2fd
    style API_Input fill:#e3f2fd
    style WE fill:#fff3e0
    style AI fill:#f3e5f5
    style Notion fill:#e8f5e9
    style GitHub fill:#e8f5e9
    style Response fill:#e8f5e9
```

## Component Interaction

```mermaid
graph TD
    subgraph "Core Components"
        A[Workflow Engine] --> B[Step Executor]
        B --> C[Variable Interpolator]
        B --> D[Error Handler]
    end
    
    subgraph "API Clients"
        E[OpenAI Client]
        F[GitHub Client]
        G[Notion Client]
        H[Gmail Client]
    end
    
    subgraph "Utilities"
        I[Config Manager]
        J[Template Manager]
        K[Logger]
    end
    
    B --> E
    B --> F
    B --> G
    B --> H
    
    A --> I
    A --> J
    A --> K
    
    E --> I
    F --> I
    G --> I
    H --> I
    
    style A fill:#ffccbc
    style B fill:#ffccbc
    style E fill:#c8e6c9
    style F fill:#c8e6c9
    style G fill:#c8e6c9
    style H fill:#c8e6c9
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant TokenAuth
    participant Workflow
    
    Client->>API: POST /auth/login<br/>{user_id, password}
    API->>TokenAuth: Verify Credentials
    TokenAuth->>TokenAuth: Generate JWT Token
    TokenAuth-->>API: Access Token
    API-->>Client: {access_token, token_type}
    
    Note over Client: Store Token
    
    Client->>API: POST /workflows/execute<br/>Authorization: Bearer {token}
    API->>TokenAuth: Verify Token
    TokenAuth->>TokenAuth: Decode & Validate JWT
    TokenAuth-->>API: User ID
    API->>Workflow: Execute Workflow
    Workflow-->>API: Result
    API-->>Client: Workflow Result
```

## Modular Architecture Benefits

### 1. **Separation of Concerns**
- Each module has a single, well-defined responsibility
- Easy to understand, test, and maintain
- Changes in one module don't affect others

### 2. **Extensibility**
- Add new API integrations by implementing client interface
- Add new workflow steps without modifying core engine
- Easy to add new authentication methods

### 3. **Testability**
- Each component can be tested independently
- Mock external dependencies easily
- Unit tests for core logic, integration tests for workflows

### 4. **Reusability**
- API clients can be used in other projects
- Workflow engine is generic and adaptable
- Template system can be applied to any use case

### 5. **Scalability**
- Async execution support ready to implement
- Can distribute workflow execution across workers
- Modular design supports microservices architecture

## Technology Stack Details

### Backend Framework
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Pydantic**: Data validation and settings management
- **Uvicorn**: ASGI server for production deployment

### Frontend
- **Streamlit**: Rapid dashboard development with Python
- Interactive UI without JavaScript complexity

### AI/ML Integration
- **OpenAI SDK**: GPT-4 and GPT-3.5-turbo for text generation
- Supports function calling and structured outputs

### API Integrations
- **PyGithub**: Complete GitHub API wrapper
- **Notion SDK**: Official Notion API client
- **Google API Client**: Gmail API integration with OAuth 2.0

### Data & Storage
- **JSON**: Lightweight workflow and template storage
- **YAML**: Human-readable configuration files
- File-based for simplicity, easily migrated to database

### Security
- **JWT Tokens**: Stateless authentication
- **OAuth 2.0**: Secure third-party authorization (Gmail)
- **Environment Variables**: Sensitive data management
