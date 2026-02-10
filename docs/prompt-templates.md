# Prompt Templates

Gorgon's prompt template system provides reusable, parameterized prompts with variable injection and security sanitization.

## Core Concepts

A `PromptTemplate` has:
- **system_prompt** - Optional instructions for the AI model
- **user_prompt** - Template with `{variable}` placeholders
- **variables** - List of expected variable names
- **model** / **temperature** - Default model settings

## Quick Start

### Python API

```python
from test_ai.prompts import PromptTemplate, PromptTemplateManager

manager = PromptTemplateManager()

# Create a template
template = PromptTemplate(
    id="code_review",
    name="Code Review",
    description="Review code for quality and security",
    system_prompt="You are an experienced software engineer.",
    user_prompt="Review this code:\n\n{code}\n\nFocus on: {focus_areas}",
    variables=["code", "focus_areas"],
    model="gpt-4o-mini",
    temperature=0.7,
)
manager.save_template(template)

# Use a template
template = manager.load_template("code_review")
formatted = template.format(code="def add(a, b): return a + b", focus_areas="correctness")
```

### Dashboard

Navigate to **Prompts** in the sidebar to create, view, and manage templates through the UI.

## API Reference

### PromptTemplateManager

| Method | Returns | Description |
|--------|---------|-------------|
| `save_template(template)` | `bool` | Save template to JSON |
| `load_template(template_id)` | `Optional[PromptTemplate]` | Load by ID |
| `list_templates()` | `List[Dict]` | List all available templates |
| `delete_template(template_id)` | `bool` | Delete a template |
| `create_default_templates()` | `None` | Initialize built-in templates |

### Built-in Templates

| ID | Purpose | Variables |
|----|---------|-----------|
| `email_summary` | Summarize email content | `email_content` |
| `sop_generator` | Generate SOPs | `task_description` |
| `meeting_notes` | Generate meeting notes | `transcript` |
| `code_review` | Code review comments | `code` |

## Security

- Template IDs are validated to prevent path traversal
- Variable values are sanitized — curly braces in user input are escaped to prevent format string injection
- Templates are stored as JSON files in the configured `prompts_dir`

## Configuration

Templates are stored in the directory specified by `settings.prompts_dir`. Override via environment:

```bash
PROMPTS_DIR=/path/to/templates
```
