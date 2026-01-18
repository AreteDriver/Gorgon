# Gorgon Code Examples

This document provides detailed code examples and usage patterns for Gorgon.

## Table of Contents
- [Basic Usage](#basic-usage)
- [Workflow Creation](#workflow-creation)
- [API Integration](#api-integration)
- [Custom Workflows](#custom-workflows)
- [Advanced Patterns](#advanced-patterns)
- [Error Handling](#error-handling)

---

## Basic Usage

### Example 1: Simple Text Generation

```python
from test_ai import WorkflowEngine, Workflow, WorkflowStep, StepType

# Initialize the workflow engine
engine = WorkflowEngine()

# Create a simple workflow
workflow = Workflow(
    id="simple_generation",
    name="Simple Text Generation",
    description="Generate creative text with AI",
    steps=[
        WorkflowStep(
            id="generate_text",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": "{{user_prompt}}",
                "model": "gpt-4o-mini",
                "max_tokens": 500
            }
        )
    ],
    variables={
        "user_prompt": "Write a short story about a robot learning to paint"
    }
)

# Execute the workflow
result = engine.execute_workflow(workflow)

# Access the output
print(f"Status: {result.status}")
print(f"Output: {result.outputs['generate_text']['response']}")
```

### Example 2: Using Prompt Templates

```python
from test_ai import PromptTemplateManager, PromptTemplate

# Initialize the prompt manager
manager = PromptTemplateManager()

# Create a reusable template
template = PromptTemplate(
    id="blog_post_generator",
    name="Blog Post Generator",
    description="Generate blog posts from topics",
    system_prompt="You are an expert content writer who creates engaging blog posts.",
    user_prompt="Write a 500-word blog post about: {topic}\n\nInclude:\n- Introduction\n- 3 main points\n- Conclusion",
    variables=["topic"]
)

# Save the template
manager.save_template(template)

# Use the template
loaded_template = manager.load_template("blog_post_generator")
formatted_prompt = loaded_template.format(topic="AI in Healthcare")

print(formatted_prompt)
```

---

## Workflow Creation

### Example 3: Multi-Step Workflow

```python
from test_ai import WorkflowEngine, Workflow, WorkflowStep, StepType

# Create a workflow with multiple steps
workflow = Workflow(
    id="multi_step_content",
    name="Multi-Step Content Creation",
    description="Generate outline, then full content",
    steps=[
        # Step 1: Generate outline
        WorkflowStep(
            id="create_outline",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": "Create a detailed outline for an article about: {{topic}}",
                "model": "gpt-4o-mini"
            },
            next_step="write_content"
        ),
        # Step 2: Write full content based on outline
        WorkflowStep(
            id="write_content",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": "Write a full article based on this outline:\n\n{{create_outline.response}}",
                "model": "gpt-4o-mini",
                "max_tokens": 2000
            },
            next_step="save_to_file"
        ),
        # Step 3: Save to GitHub
        WorkflowStep(
            id="save_to_file",
            type=StepType.GITHUB,
            action="commit_file",
            params={
                "repo": "{{github_repo}}",
                "path": "articles/{{filename}}.md",
                "content": "{{write_content.response}}",
                "message": "Add article: {{topic}}"
            }
        )
    ],
    variables={
        "topic": "The Future of AI",
        "github_repo": "username/blog",
        "filename": "future-of-ai"
    }
)

# Execute
engine = WorkflowEngine()
result = engine.execute_workflow(workflow)
```

### Example 4: Conditional Logic (Pseudo-code)

```python
# Note: This is a conceptual example showing how you might extend the system

workflow = Workflow(
    id="conditional_workflow",
    name="Workflow with Conditions",
    steps=[
        WorkflowStep(
            id="analyze_sentiment",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": "Analyze sentiment (positive/negative): {{text}}"
            },
            next_step="check_sentiment"
        ),
        WorkflowStep(
            id="check_sentiment",
            type=StepType.CONDITION,
            condition="{{analyze_sentiment.sentiment}} == 'positive'",
            true_step="send_thank_you",
            false_step="escalate_issue"
        ),
        WorkflowStep(
            id="send_thank_you",
            type=StepType.GMAIL,
            action="send_email",
            params={
                "to": "{{customer_email}}",
                "subject": "Thank you!",
                "body": "We appreciate your positive feedback!"
            }
        ),
        WorkflowStep(
            id="escalate_issue",
            type=StepType.GITHUB,
            action="create_issue",
            params={
                "title": "Customer Issue: {{analyze_sentiment.summary}}",
                "body": "{{text}}"
            }
        )
    ]
)
```

---

## API Integration

### Example 5: Using the REST API

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# 1. Authenticate
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"user_id": "demo", "password": "demo"}
)
token = login_response.json()["access_token"]

# Headers for authenticated requests
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. List available workflows
workflows_response = requests.get(
    f"{BASE_URL}/workflows",
    headers=headers
)
workflows = workflows_response.json()
print(f"Available workflows: {len(workflows)}")

# 3. Execute a workflow
execute_response = requests.post(
    f"{BASE_URL}/workflows/execute",
    headers=headers,
    json={
        "workflow_id": "simple_ai_completion",
        "variables": {
            "prompt": "Explain machine learning in simple terms"
        }
    }
)
result = execute_response.json()
print(f"Result: {result}")

# 4. Create a new prompt template
template_response = requests.post(
    f"{BASE_URL}/prompts",
    headers=headers,
    json={
        "id": "code_reviewer",
        "name": "Code Reviewer",
        "description": "Review code for best practices",
        "user_prompt": "Review this code:\n\n{code}\n\nProvide feedback on:\n- Code quality\n- Best practices\n- Potential bugs",
        "variables": ["code"]
    }
)
```

### Example 6: Async API Usage

```python
import httpx
import asyncio

async def execute_workflow_async():
    async with httpx.AsyncClient() as client:
        # Login
        login_resp = await client.post(
            "http://localhost:8000/auth/login",
            json={"user_id": "demo", "password": "demo"}
        )
        token = login_resp.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Execute workflow
        result = await client.post(
            "http://localhost:8000/workflows/execute",
            headers=headers,
            json={
                "workflow_id": "simple_ai_completion",
                "variables": {"prompt": "Hello AI!"}
            }
        )
        
        return result.json()

# Run async
result = asyncio.run(execute_workflow_async())
print(result)
```

---

## Custom Workflows

### Example 7: Email Processing Pipeline

```json
{
  "id": "email_processing",
  "name": "Email Processing Pipeline",
  "description": "Fetch, summarize, and organize emails",
  "steps": [
    {
      "id": "fetch_emails",
      "type": "gmail",
      "action": "get_messages",
      "params": {
        "max_results": 10,
        "query": "is:unread"
      },
      "next_step": "summarize_each"
    },
    {
      "id": "summarize_each",
      "type": "openai",
      "action": "generate_completion",
      "params": {
        "prompt": "Summarize this email in 2-3 sentences:\n\nSubject: {{fetch_emails.subject}}\n\nBody: {{fetch_emails.body}}",
        "model": "gpt-4o-mini"
      },
      "next_step": "save_summary"
    },
    {
      "id": "save_summary",
      "type": "notion",
      "action": "create_page",
      "params": {
        "parent_id": "{{notion_inbox_id}}",
        "title": "Email: {{fetch_emails.subject}}",
        "content": "**From:** {{fetch_emails.from}}\n**Date:** {{fetch_emails.date}}\n**Summary:** {{summarize_each.response}}"
      }
    }
  ],
  "variables": {
    "notion_inbox_id": "your-notion-page-id"
  }
}
```

### Example 8: Documentation Generator

```python
from test_ai import WorkflowEngine, Workflow, WorkflowStep, StepType

# Workflow that generates documentation from code
doc_workflow = Workflow(
    id="doc_generator",
    name="Documentation Generator",
    description="Generate docs from source code",
    steps=[
        WorkflowStep(
            id="read_code",
            type=StepType.TRANSFORM,
            action="read_file",
            params={"path": "{{source_file}}"}
        ),
        WorkflowStep(
            id="generate_docs",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": """Generate comprehensive documentation for this code:

```python
{{read_code.content}}
```

Include:
- Overview
- Function descriptions
- Parameter explanations
- Usage examples
- Return values""",
                "model": "gpt-4o-mini"
            }
        ),
        WorkflowStep(
            id="save_docs",
            type=StepType.GITHUB,
            action="commit_file",
            params={
                "repo": "{{repo}}",
                "path": "docs/{{doc_filename}}.md",
                "content": "{{generate_docs.response}}",
                "message": "Add documentation for {{source_file}}"
            }
        )
    ],
    variables={
        "source_file": "src/utils.py",
        "repo": "username/project",
        "doc_filename": "utils_api"
    }
)
```

---

## Advanced Patterns

### Example 9: Batch Processing

```python
from test_ai import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.load_workflow("email_processing")

# Process multiple items
items = [
    {"email_id": "123", "subject": "Important Update"},
    {"email_id": "124", "subject": "Meeting Request"},
    {"email_id": "125", "subject": "Project Status"}
]

results = []
for item in items:
    workflow.variables.update(item)
    result = engine.execute_workflow(workflow)
    results.append({
        "email_id": item["email_id"],
        "status": result.status,
        "summary": result.outputs.get("summarize_each", {}).get("response")
    })

# Process results
successful = [r for r in results if r["status"] == "completed"]
print(f"Processed {len(successful)}/{len(items)} emails successfully")
```

### Example 10: Error Handling and Retry

```python
from test_ai import WorkflowEngine
import time

def execute_with_retry(workflow, max_retries=3):
    """Execute workflow with retry logic."""
    engine = WorkflowEngine()
    
    for attempt in range(max_retries):
        try:
            result = engine.execute_workflow(workflow)
            
            if result.status == "completed":
                return result
            elif result.status == "failed":
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"Failed after {max_retries} attempts")
                    return result
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Error: {e}, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise
    
    return None

# Usage
result = execute_with_retry(my_workflow)
```

### Example 11: Workflow Chaining

```python
from test_ai import WorkflowEngine

engine = WorkflowEngine()

# Execute workflows in sequence, passing data between them
workflow1 = engine.load_workflow("fetch_data")
result1 = engine.execute_workflow(workflow1)

# Use result from workflow1 in workflow2
workflow2 = engine.load_workflow("process_data")
workflow2.variables["input_data"] = result1.outputs["fetch"]["data"]
result2 = engine.execute_workflow(workflow2)

# Chain to workflow3
workflow3 = engine.load_workflow("save_results")
workflow3.variables["processed_data"] = result2.outputs["process"]["result"]
result3 = engine.execute_workflow(workflow3)

print(f"Pipeline complete: {result3.status}")
```

---

## Error Handling

### Example 12: Graceful Error Handling

```python
from test_ai import WorkflowEngine
from test_ai.orchestrator import WorkflowResult

def safe_execute(workflow_id: str, variables: dict = None):
    """Execute workflow with comprehensive error handling."""
    try:
        engine = WorkflowEngine()
        workflow = engine.load_workflow(workflow_id)
        
        if variables:
            workflow.variables.update(variables)
        
        result = engine.execute_workflow(workflow)
        
        if result.status == "completed":
            return {
                "success": True,
                "outputs": result.outputs,
                "message": "Workflow completed successfully"
            }
        else:
            return {
                "success": False,
                "error": result.error,
                "message": "Workflow failed"
            }
            
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"Workflow '{workflow_id}' not found",
            "message": "Check workflow ID and try again"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Unexpected error occurred"
        }

# Usage
result = safe_execute("my_workflow", {"param": "value"})
if result["success"]:
    print(f"Success: {result['outputs']}")
else:
    print(f"Error: {result['error']}")
```

---

## Real-World Examples

### Example 13: Meeting Notes to Action Items

```python
from test_ai import WorkflowEngine, Workflow, WorkflowStep, StepType

meeting_notes_workflow = Workflow(
    id="meeting_notes_processor",
    name="Meeting Notes to Action Items",
    description="Extract action items from meeting notes and create GitHub issues",
    steps=[
        WorkflowStep(
            id="extract_actions",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": """Extract action items from these meeting notes:

{{notes}}

Format each action item as:
- [ ] Action item description
- Assignee: Name
- Due date: YYYY-MM-DD

Return only the action items list.""",
                "model": "gpt-4o-mini"
            }
        ),
        WorkflowStep(
            id="create_issues",
            type=StepType.GITHUB,
            action="create_issue",
            params={
                "repo": "{{repo}}",
                "title": "Action Item: {{extract_actions.item_title}}",
                "body": "{{extract_actions.item_description}}\n\nAssignee: {{extract_actions.assignee}}\nDue: {{extract_actions.due_date}}",
                "labels": ["meeting-action-item", "{{priority}}"]
            }
        ),
        WorkflowStep(
            id="save_to_notion",
            type=StepType.NOTION,
            action="create_page",
            params={
                "parent_id": "{{notion_meetings_db}}",
                "title": "Meeting: {{meeting_date}}",
                "content": "{{notes}}\n\n## Action Items\n{{extract_actions.response}}"
            }
        )
    ],
    variables={
        "notes": "",
        "meeting_date": "2025-01-15",
        "repo": "company/projects",
        "notion_meetings_db": "meeting-db-id",
        "priority": "normal"
    }
)
```

### Example 14: Customer Support Automation

```python
support_workflow = Workflow(
    id="support_automation",
    name="Customer Support Automation",
    description="Process support emails and route appropriately",
    steps=[
        WorkflowStep(
            id="fetch_support_email",
            type=StepType.GMAIL,
            action="get_messages",
            params={
                "query": "to:support@company.com is:unread",
                "max_results": 1
            }
        ),
        WorkflowStep(
            id="categorize",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": """Categorize this support email:

Subject: {{fetch_support_email.subject}}
Body: {{fetch_support_email.body}}

Return ONLY one of: bug, feature_request, question, complaint""",
                "model": "gpt-4o-mini"
            }
        ),
        WorkflowStep(
            id="generate_response",
            type=StepType.OPENAI,
            action="generate_completion",
            params={
                "prompt": """Generate a helpful response to this support email:

Category: {{categorize.response}}
Subject: {{fetch_support_email.subject}}
Body: {{fetch_support_email.body}}

Be professional, empathetic, and provide actionable next steps.""",
                "model": "gpt-4o-mini"
            }
        ),
        WorkflowStep(
            id="create_tracking_issue",
            type=StepType.GITHUB,
            action="create_issue",
            params={
                "repo": "company/support-tracker",
                "title": "[{{categorize.response}}] {{fetch_support_email.subject}}",
                "body": "**From:** {{fetch_support_email.from}}\n**Category:** {{categorize.response}}\n\n**Original Message:**\n{{fetch_support_email.body}}\n\n**Suggested Response:**\n{{generate_response.response}}",
                "labels": ["support", "{{categorize.response}}"]
            }
        )
    ]
)
```

---

## Best Practices

### 1. Workflow Organization
- Keep workflows focused on a single purpose
- Use descriptive IDs and names
- Document expected variables and outputs
- Version control your workflow definitions

### 2. Error Handling
- Always handle potential API failures
- Implement retry logic for critical operations
- Log errors for debugging
- Provide fallback behaviors

### 3. Security
- Never hardcode API keys in workflows
- Use environment variables for sensitive data
- Validate all user inputs
- Implement proper authentication

### 4. Performance
- Batch operations when possible
- Use appropriate AI models (gpt-4o-mini for simple tasks)
- Cache results when appropriate
- Monitor API usage and costs

### 5. Testing
- Test workflows with sample data first
- Validate outputs before production use
- Monitor execution logs
- Set up alerts for failures

---

For more examples, see the [workflows directory](../src/test_ai/workflows/) in the repository.
