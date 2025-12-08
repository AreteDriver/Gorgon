# Example Workflows

This directory contains example workflow definitions that demonstrate various features and integrations of AI-Orchestra.

## 📁 Available Examples

### Basic Examples

1. **[simple-completion.json](simple-completion.json)**
   - Basic AI text generation
   - Single-step workflow
   - Good for beginners

2. **[multi-step-ai.json](multi-step-ai.json)**
   - Multiple AI operations in sequence
   - Variable passing between steps
   - Demonstrates workflow chaining

### Integration Examples

3. **[email-to-notion.json](email-to-notion.json)**
   - Gmail → AI Summary → Notion
   - Multi-service integration
   - OAuth authentication example

4. **[github-automation.json](github-automation.json)**
   - AI content generation → GitHub
   - Repository management
   - File creation and commits

5. **[notion-to-github.json](notion-to-github.json)**
   - Notion → AI processing → GitHub
   - Cross-platform workflow
   - Database to repository sync

### Advanced Examples

6. **[content-pipeline.json](content-pipeline.json)**
   - Complex multi-step pipeline
   - Multiple AI processing stages
   - Advanced variable interpolation

7. **[automated-reporting.json](automated-reporting.json)**
   - Data collection and summarization
   - Scheduled execution ready
   - Multiple output destinations

## 🚀 How to Use Examples

### Method 1: Via Dashboard

1. Start the dashboard: `./run_dashboard.sh`
2. Navigate to "Workflows" page
3. Click "Import Workflow"
4. Select an example JSON file
5. Click "Execute" to run

### Method 2: Via API

```bash
# Copy example to workflows directory
cp examples/simple-completion.json src/test_ai/workflows/

# Execute via API
curl -X POST http://localhost:8000/workflows/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "simple_completion",
    "variables": {"prompt": "Hello, AI!"}
  }'
```

### Method 3: Programmatically

```python
from test_ai import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.load_workflow("simple_completion")
workflow.variables["prompt"] = "Hello, AI!"
result = engine.execute_workflow(workflow)
print(result.outputs)
```

## 📝 Example Workflow Structure

All examples follow this structure:

```json
{
  "workflow_id": "unique_id",
  "name": "Human Readable Name",
  "description": "What this workflow does",
  "steps": [
    {
      "step_id": "step1",
      "step_type": "openai",
      "action": "generate_completion",
      "parameters": {
        "prompt": "{{input_variable}}",
        "model": "gpt-4"
      }
    }
  ],
  "variables": {
    "input_variable": "default value"
  }
}
```

## 🎯 Customization Guide

### Modify an Example

1. Copy the example: `cp examples/simple-completion.json my-workflow.json`
2. Edit the file:
   - Change `workflow_id` to unique name
   - Update `name` and `description`
   - Modify `steps` as needed
   - Set default `variables`
3. Save to `src/test_ai/workflows/`
4. Run your custom workflow

### Common Modifications

**Change AI Model:**
```json
"parameters": {
  "model": "gpt-4o-mini"  // or "gpt-4", "gpt-3.5-turbo"
}
```

**Add More Steps:**
```json
"steps": [
  {
    "step_id": "step1",
    // ... first step
  },
  {
    "step_id": "step2",
    // ... second step using {{step1_output}}
  }
]
```

**Use Previous Output:**
```json
"parameters": {
  "content": "{{previous_step_id_output}}"
}
```

## 🔧 Required Configuration

Some examples require API credentials:

### OpenAI Examples
```bash
# .env
OPENAI_API_KEY=sk-...
```

### GitHub Examples
```bash
# .env
GITHUB_TOKEN=ghp_...
```

### Notion Examples
```bash
# .env
NOTION_TOKEN=secret_...
```

### Gmail Examples
```bash
# .env
GMAIL_CREDENTIALS_PATH=credentials.json
```

See [Configuration Guide](../docs/configuration.md) for details.

## 💡 Learning Path

**Beginner:**
1. Start with `simple-completion.json`
2. Try `multi-step-ai.json`
3. Experiment with variables

**Intermediate:**
4. Set up GitHub integration
5. Try `github-automation.json`
6. Create custom workflows

**Advanced:**
7. Combine multiple services
8. Use `content-pipeline.json`
9. Build complex automations

## 🐛 Troubleshooting

### Workflow Won't Execute

- Check API credentials in `.env`
- Verify workflow JSON syntax
- Review logs in `src/test_ai/logs/`

### Variables Not Working

- Use double curly braces: `{{variable}}`
- Check variable names match exactly
- Ensure variables are defined in workflow

### API Errors

- Verify API keys are valid
- Check internet connection
- Review API rate limits

## 🤝 Contributing Examples

Have a great workflow to share?

1. Create your workflow JSON
2. Test it thoroughly
3. Add comments and documentation
4. Submit a pull request to `examples/`

See [Contributing Guide](../CONTRIBUTING.md) for details.

## 📚 Additional Resources

- [Workflow Creation Guide](../docs/creating-workflows.md)
- [API Integration Guides](../docs/integrations/)
- [API Reference](../docs/api-reference.md)

---

**Happy Workflow Building! 🎼**
