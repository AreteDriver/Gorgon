# Example Workflows

This directory contains example workflow definitions that demonstrate various features and integrations of AI-Orchestra.

## 📁 Available Examples

### Basic Examples

1. **[simple_ai_completion.json](simple_ai_completion.json)**
   - Basic AI text generation
   - Single-step workflow
   - Good for beginners

### Integration Examples

2. **[email_to_notion.json](email_to_notion.json)**
   - Gmail → AI Summary → Notion
   - Multi-service integration
   - OAuth authentication example

3. **[generate_sop_to_github.json](generate_sop_to_github.json)**
   - AI content generation → GitHub
   - Repository management
   - Standard Operating Procedure creation

### Future Examples (Coming Soon)

- **multi-step-ai.json** - Multiple AI operations in sequence
- **notion-to-github.json** - Notion → AI processing → GitHub
- **content-pipeline.json** - Complex multi-step pipeline
- **automated-reporting.json** - Data collection and summarization

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
cp examples/simple_ai_completion.json src/test_ai/workflows/

# Execute via API
curl -X POST http://localhost:8000/workflows/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "simple_ai_completion",
    "variables": {"prompt": "Hello, AI!"}
  }'
```

### Method 3: Programmatically

```python
from test_ai import WorkflowEngine

engine = WorkflowEngine()
workflow = engine.load_workflow("simple_ai_completion")
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

1. Copy the example: `cp examples/simple_ai_completion.json my-workflow.json`
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

See [.env.example](../.env.example) for complete configuration options.

## 💡 Learning Path

**Beginner:**
1. Start with `simple_ai_completion.json`
2. Experiment with different prompts and variables
3. Try modifying the workflow parameters

**Intermediate:**
4. Set up GitHub or Notion integration
5. Try `email_to_notion.json` or `generate_sop_to_github.json`
6. Create custom workflows by combining steps

**Advanced:**
7. Combine multiple services in one workflow
8. Build complex automations with conditional logic
9. Share your workflows with the community

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

- [Quick Start Guide](../QUICKSTART.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Architecture Overview](../ARCHITECTURE.md)

---

**Happy Workflow Building! 🎼**
