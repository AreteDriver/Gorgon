"""Gorgon CLI - Main entry point."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

__version__ = "0.3.0"

app = typer.Typer(
    name="gorgon",
    help="Your personal army of AI agents for development workflows.",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold cyan]gorgon[/bold cyan] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
):
    """Gorgon - Multi-agent AI workflow orchestration.

    Coordinate specialized AI agents (Planner, Builder, Tester, Reviewer)
    across your development workflows.

    [bold]Quick Start:[/bold]

        gorgon init         Create a new workflow template
        gorgon run WORKFLOW Execute a workflow
        gorgon plan TASK    Plan implementation steps
        gorgon build TASK   Generate code for a task
        gorgon test TASK    Generate tests for code
        gorgon review PATH  Review code for issues
        gorgon ask QUESTION Ask a question about your code

    [bold]Shell Completion:[/bold]

        # Bash
        gorgon --install-completion bash

        # Zsh
        gorgon --install-completion zsh

        # Fish
        gorgon --install-completion fish
    """
    pass


def get_workflow_engine():
    """Lazy import workflow engine to avoid startup cost."""
    try:
        from test_ai.orchestrator import WorkflowEngineAdapter

        return WorkflowEngineAdapter()
    except ImportError as e:
        console.print(f"[red]Missing dependencies:[/red] {e}")
        console.print("Run: pip install pydantic-settings")
        raise typer.Exit(1)


def get_claude_client():
    """Get Claude Code client for direct agent execution."""
    try:
        from test_ai.api_clients import ClaudeCodeClient

        client = ClaudeCodeClient()
        if not client.is_configured():
            console.print("[red]Claude not configured.[/red]")
            console.print("Set ANTHROPIC_API_KEY environment variable.")
            raise typer.Exit(1)
        return client
    except ImportError as e:
        console.print(f"[red]Missing dependencies:[/red] {e}")
        raise typer.Exit(1)


def get_workflow_executor(dry_run: bool = False):
    """Get workflow executor with checkpoint and budget managers."""
    try:
        from test_ai.workflow.executor import WorkflowExecutor
        from test_ai.state.checkpoint import CheckpointManager
        from test_ai.budget import BudgetManager

        checkpoint_mgr = CheckpointManager()
        budget_mgr = BudgetManager()

        return WorkflowExecutor(
            checkpoint_manager=checkpoint_mgr,
            budget_manager=budget_mgr,
            dry_run=dry_run,
        )
    except ImportError as e:
        console.print(f"[red]Missing dependencies:[/red] {e}")
        raise typer.Exit(1)


def _detect_python_framework(path: Path) -> str | None:
    """Detect Python framework from pyproject.toml."""
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        content = pyproject.read_text().lower()
        frameworks = [
            ("fastapi", "fastapi"),
            ("django", "django"),
            ("flask", "flask"),
            ("streamlit", "streamlit"),
        ]
        for keyword, framework in frameworks:
            if keyword in content:
                return framework
    except Exception:
        pass
    return None


def _detect_js_framework(path: Path) -> str | None:
    """Detect JavaScript/TypeScript framework from package.json."""
    try:
        pkg = json.loads((path / "package.json").read_text())
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        frameworks = [("react", "react"), ("vue", "vue"), ("next", "nextjs")]
        for keyword, framework in frameworks:
            if keyword in deps:
                return framework
    except Exception:
        pass
    return None


def _detect_language_and_framework(path: Path) -> tuple[str, str | None]:
    """Detect primary language and framework.

    Returns:
        Tuple of (language, framework)
    """
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        return "python", _detect_python_framework(path)
    if (path / "Cargo.toml").exists():
        return "rust", None
    if (path / "package.json").exists():
        return "typescript", _detect_js_framework(path)
    if (path / "go.mod").exists():
        return "go", None
    return "unknown", None


def _get_key_structure(path: Path, limit: int = 20) -> list[str]:
    """Get key directories and files in the codebase."""
    structure = []
    key_dirs = {"src", "lib", "app", "tests", "docs"}
    code_exts = {".py", ".rs", ".ts", ".js", ".go"}

    for item in path.iterdir():
        if item.name.startswith("."):
            continue
        if item.is_dir() and item.name in key_dirs:
            structure.append(f"{item.name}/")
        elif item.is_file() and item.suffix in code_exts:
            structure.append(item.name)
    return structure[:limit]


def _get_readme_content(path: Path, max_chars: int = 500) -> str | None:
    """Get README content if present."""
    readme_names = ("README.md", "README.rst", "README.txt", "README")
    for name in readme_names:
        readme_path = path / name
        if readme_path.exists():
            try:
                return readme_path.read_text()[:max_chars]
            except Exception:
                pass
    return None


def detect_codebase_context(path: Path = None) -> dict:
    """Auto-detect codebase context for better agent prompts.

    Returns context dict with:
    - language: Primary language (python, rust, typescript, etc.)
    - framework: Detected framework (fastapi, react, etc.)
    - structure: Key directories and files
    - readme: First 500 chars of README if present
    """
    path = path or Path.cwd()
    language, framework = _detect_language_and_framework(path)

    return {
        "path": str(path),
        "language": language,
        "framework": framework,
        "structure": _get_key_structure(path),
        "readme": _get_readme_content(path),
    }


def format_context_for_prompt(context: dict) -> str:
    """Format codebase context for agent prompts."""
    lines = [f"Codebase: {context['path']}"]
    lines.append(f"Language: {context['language']}")
    if context["framework"]:
        lines.append(f"Framework: {context['framework']}")
    if context["structure"]:
        lines.append(f"Structure: {', '.join(context['structure'][:10])}")
    return "\n".join(lines)


def get_tracker():
    """Lazy import execution tracker."""
    try:
        from test_ai.monitoring.tracker import get_tracker as _get_tracker

        return _get_tracker()
    except ImportError:
        return None


def _parse_cli_variables(var: list[str]) -> dict:
    """Parse CLI variables in key=value format."""
    variables = {}
    for v in var:
        if "=" in v:
            key, value = v.split("=", 1)
            variables[key] = value
        else:
            console.print(f"[red]Invalid variable format: {v}[/red]")
            console.print("Use: --var key=value")
            raise typer.Exit(1)
    return variables


def _load_workflow_from_source(workflow: str, engine) -> tuple[str, dict, Path | None]:
    """Load workflow from file or by ID.

    Returns:
        Tuple of (workflow_id, workflow_data, workflow_path_or_None)
    """
    workflow_path = Path(workflow)
    if workflow_path.exists() and workflow_path.suffix == ".json":
        try:
            with open(workflow_path) as f:
                workflow_data = json.load(f)
            workflow_id = workflow_data.get("id", workflow_path.stem)
            console.print(f"[dim]Loading workflow from:[/dim] {workflow_path}")
            return workflow_id, workflow_data, workflow_path
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON in workflow file:[/red] {e}")
            raise typer.Exit(1)

    loaded = engine.load_workflow(workflow)
    if not loaded:
        console.print(f"[red]Workflow not found:[/red] {workflow}")
        console.print("\nAvailable workflows:")
        list_workflows_table(engine)
        raise typer.Exit(1)
    return workflow, loaded.model_dump(), None


def _display_workflow_preview(
    workflow_id: str, workflow_data: dict, variables: dict
) -> None:
    """Display workflow information preview."""
    console.print(
        Panel(
            f"[bold]{workflow_data.get('name', workflow_id)}[/bold]\n"
            f"[dim]{workflow_data.get('description', 'No description')}[/dim]",
            title="Workflow",
            border_style="blue",
        )
    )

    if workflow_data.get("steps"):
        console.print(f"\n[dim]Steps:[/dim] {len(workflow_data['steps'])}")
        for step in workflow_data["steps"]:
            console.print(
                f"  • {step['id']} ({step['type']}:{step.get('action', 'N/A')})"
            )

    if variables:
        console.print("\n[dim]Variables:[/dim]")
        for k, v in variables.items():
            console.print(f"  {k} = {v}")


def _output_run_results(result, json_output: bool) -> None:
    """Output workflow execution results."""
    if json_output:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    status_color = "green" if result.status == "completed" else "red"
    console.print(f"\n[{status_color}]Status: {result.status}[/{status_color}]")

    if result.step_results:
        console.print("\n[dim]Step Results:[/dim]")
        for step_id, step_result in result.step_results.items():
            status = step_result.get("status", "unknown")
            icon = "✓" if status == "success" else "✗"
            console.print(f"  {icon} {step_id}: {status}")

    if result.error:
        console.print(f"\n[red]Error:[/red] {result.error}")


@app.command()
def run(
    workflow: str = typer.Argument(
        ...,
        help="Workflow ID or path to workflow JSON file",
    ),
    var: list[str] = typer.Option(
        [],
        "--var",
        "-v",
        help="Variables in key=value format (can be repeated)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output results as JSON",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and show workflow without executing",
    ),
):
    """Run a workflow by ID or from a JSON file."""
    engine = get_workflow_engine()
    variables = _parse_cli_variables(var)
    workflow_id, workflow_data, workflow_path = _load_workflow_from_source(
        workflow, engine
    )

    _display_workflow_preview(workflow_id, workflow_data, variables)

    if dry_run:
        console.print("\n[yellow]Dry run - workflow not executed[/yellow]")
        raise typer.Exit(0)

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Executing workflow...", total=None)

        try:
            if workflow_path is None:
                wf = engine.load_workflow(workflow_id)
                wf.variables = variables
            else:
                from test_ai.orchestrator import Workflow

                wf = Workflow(**workflow_data)
                wf.variables = variables

            result = engine.execute_workflow(wf)
            progress.update(task, description="Complete!")
        except Exception as e:
            progress.stop()
            console.print(f"\n[red]Execution failed:[/red] {e}")
            raise typer.Exit(1)

    _output_run_results(result, json_output)


@app.command("list")
def list_workflows(
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """List all available workflows."""
    engine = get_workflow_engine()
    workflows = engine.list_workflows()

    if json_output:
        print(json.dumps(workflows, indent=2))
        return

    if not workflows:
        console.print("[yellow]No workflows found[/yellow]")
        console.print(
            "\nCreate workflows in the workflows directory or use 'gorgon run <file.json>'"
        )
        return

    list_workflows_table(engine)


def list_workflows_table(engine):
    """Display workflows in a table."""
    workflows = engine.list_workflows()

    table = Table(title="Available Workflows")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Steps", justify="right")

    for wf in workflows:
        loaded = engine.load_workflow(wf["id"])
        steps = len(loaded.steps) if loaded else "?"
        table.add_row(
            wf["id"],
            wf.get("name", "-"),
            wf.get("description", "-")[:50],
            str(steps),
        )

    console.print(table)


def _validate_cli_required_fields(data: dict) -> tuple[list[str], list[str]]:
    """Validate required workflow fields for CLI."""
    errors = []
    warnings = []
    if "id" not in data:
        errors.append("Missing required field: id")
    if "steps" not in data:
        errors.append("Missing required field: steps")
    elif not isinstance(data["steps"], list):
        errors.append("'steps' must be a list")
    elif len(data["steps"]) == 0:
        warnings.append("Workflow has no steps")
    return errors, warnings


def _validate_cli_steps(steps: list) -> tuple[list[str], list[str], set[str]]:
    """Validate workflow steps for CLI."""
    errors = []
    warnings = []
    step_ids: set[str] = set()
    valid_types = {"claude_code", "openai", "transform", "condition"}

    for i, step in enumerate(steps):
        prefix = f"Step {i + 1}"

        if "id" not in step:
            errors.append(f"{prefix}: Missing 'id'")
        else:
            if step["id"] in step_ids:
                errors.append(f"{prefix}: Duplicate step ID '{step['id']}'")
            step_ids.add(step["id"])

        if "type" not in step:
            errors.append(f"{prefix}: Missing 'type'")
        elif step["type"] not in valid_types:
            warnings.append(f"{prefix}: Unknown step type '{step['type']}'")

        if "action" not in step:
            errors.append(f"{prefix}: Missing 'action'")

    return errors, warnings, step_ids


def _validate_cli_next_step_refs(steps: list, step_ids: set[str]) -> list[str]:
    """Validate next_step references in workflow."""
    errors = []
    for step in steps:
        if "next_step" in step and step["next_step"]:
            if step["next_step"] not in step_ids:
                errors.append(
                    f"Step '{step.get('id', '?')}': next_step '{step['next_step']}' not found"
                )
    return errors


def _output_validation_results(
    errors: list[str], warnings: list[str], workflow_file: Path
) -> None:
    """Output validation results to console."""
    if errors:
        console.print(
            Panel(
                "\n".join(f"[red]✗[/red] {e}" for e in errors),
                title="Errors",
                border_style="red",
            )
        )

    if warnings:
        console.print(
            Panel(
                "\n".join(f"[yellow]![/yellow] {w}" for w in warnings),
                title="Warnings",
                border_style="yellow",
            )
        )

    if not errors and not warnings:
        console.print(f"[green]✓ Workflow is valid:[/green] {workflow_file}")
    elif not errors:
        console.print("\n[green]✓ Workflow is valid with warnings[/green]")
    else:
        console.print("\n[red]✗ Validation failed[/red]")
        raise typer.Exit(1)


@app.command()
def validate(
    workflow_file: Path = typer.Argument(
        ...,
        help="Path to workflow JSON file",
        exists=True,
    ),
):
    """Validate a workflow JSON file."""
    try:
        with open(workflow_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON:[/red] {e}")
        raise typer.Exit(1)

    errors, warnings = _validate_cli_required_fields(data)

    steps = data.get("steps", [])
    if isinstance(steps, list):
        step_errors, step_warnings, step_ids = _validate_cli_steps(steps)
        errors.extend(step_errors)
        warnings.extend(step_warnings)
        errors.extend(_validate_cli_next_step_refs(steps, step_ids))

    _output_validation_results(errors, warnings, workflow_file)


@app.command()
def status(
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """Show orchestrator status and metrics."""
    try:
        tracker = get_tracker()
        data = tracker.get_dashboard_data()
    except Exception as e:
        console.print(f"[yellow]Metrics unavailable:[/yellow] {e}")
        data = {"summary": {}, "active_workflows": [], "recent_executions": []}

    if json_output:
        print(json.dumps(data, indent=2, default=str))
        return

    summary = data.get("summary", {})

    # Summary panel
    console.print(
        Panel(
            f"Active Workflows: [bold]{summary.get('active_workflows', 0)}[/bold]\n"
            f"Total Executions: [bold]{summary.get('total_executions', 0)}[/bold]\n"
            f"Success Rate: [bold]{summary.get('success_rate', 0):.1f}%[/bold]\n"
            f"Avg Duration: [bold]{summary.get('avg_duration_ms', 0):.0f}ms[/bold]",
            title="Gorgon Status",
            border_style="blue",
        )
    )

    # Active workflows
    active = data.get("active_workflows", [])
    if active:
        console.print("\n[bold]Active Workflows:[/bold]")
        for wf in active:
            progress = (
                wf["completed_steps"] / wf["total_steps"]
                if wf["total_steps"] > 0
                else 0
            )
            console.print(
                f"  • {wf['workflow_name']} ({wf['execution_id'][:12]}...) "
                f"[dim]{wf['completed_steps']}/{wf['total_steps']} steps ({progress * 100:.0f}%)[/dim]"
            )

    # Recent executions
    recent = data.get("recent_executions", [])[:5]
    if recent:
        console.print("\n[bold]Recent Executions:[/bold]")
        table = Table(show_header=True, header_style="dim")
        table.add_column("Workflow")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Steps")

        for ex in recent:
            status_style = "green" if ex["status"] == "completed" else "red"
            table.add_row(
                ex["workflow_name"][:30],
                f"[{status_style}]{ex['status']}[/{status_style}]",
                f"{ex['duration_ms']:.0f}ms",
                f"{ex['completed_steps']}/{ex['total_steps']}",
            )

        console.print(table)


@app.command()
def init(
    name: str = typer.Argument(
        ...,
        help="Name for the new workflow",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: <name>.json)",
    ),
):
    """Create a new workflow template."""
    workflow_id = name.lower().replace(" ", "_").replace("-", "_")
    output_path = output or Path(f"{workflow_id}.json")

    if output_path.exists():
        overwrite = typer.confirm(f"{output_path} already exists. Overwrite?")
        if not overwrite:
            raise typer.Abort()

    template = {
        "id": workflow_id,
        "name": name,
        "description": f"Workflow: {name}",
        "variables": {"input": "default value"},
        "steps": [
            {
                "id": "step_1",
                "type": "transform",
                "action": "format",
                "params": {"template": "Processing: {{input}}"},
                "next_step": "step_2",
            },
            {
                "id": "step_2",
                "type": "claude_code",
                "action": "execute_agent",
                "params": {
                    "role": "assistant",
                    "task": "Analyze the input and provide insights",
                },
                "next_step": None,
            },
        ],
    }

    with open(output_path, "w") as f:
        json.dump(template, f, indent=2)

    console.print(f"[green]✓ Created workflow template:[/green] {output_path}")
    console.print("\nNext steps:")
    console.print(f"  1. Edit {output_path} to customize your workflow")
    console.print(f"  2. Validate: [cyan]gorgon validate {output_path}[/cyan]")
    console.print(f"  3. Run: [cyan]gorgon run {output_path}[/cyan]")


@app.command(hidden=True)
def version():
    """Show Gorgon version (use --version instead)."""
    console.print(f"[bold cyan]gorgon[/bold cyan] version {__version__}")
    console.print("[dim]Your personal army of AI agents[/dim]")


@app.command()
def completion(
    shell: str = typer.Argument(
        None,
        help="Shell type (bash, zsh, fish). Auto-detected if not provided.",
    ),
    install: bool = typer.Option(
        False,
        "--install",
        "-i",
        help="Install completion to shell config file.",
    ),
):
    """Show or install shell completion.

    Examples:

        # Show completion script for current shell
        gorgon completion

        # Show completion script for specific shell
        gorgon completion bash

        # Install completion (adds to shell config)
        gorgon completion --install
    """
    import os

    # Auto-detect shell
    if not shell:
        shell_path = os.environ.get("SHELL", "")
        if "zsh" in shell_path:
            shell = "zsh"
        elif "fish" in shell_path:
            shell = "fish"
        else:
            shell = "bash"

    if install:
        # Use Typer's built-in completion installation
        console.print(f"[cyan]Installing completion for {shell}...[/cyan]")
        try:
            # Typer installs completion via --install-completion
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "typer",
                    "gorgon",
                    "--install-completion",
                    shell,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print(f"[green]Completion installed for {shell}![/green]")
                console.print(
                    "[dim]Restart your shell or source your config file.[/dim]"
                )
            else:
                # Fall back to manual instructions
                _show_completion_instructions(shell)
        except Exception:
            _show_completion_instructions(shell)
    else:
        _show_completion_instructions(shell)


def _show_completion_instructions(shell: str):
    """Show manual completion installation instructions."""
    instructions = {
        "bash": """
# Add to ~/.bashrc:
eval "$(_GORGON_COMPLETE=bash_source gorgon)"

# Or generate and source a file:
_GORGON_COMPLETE=bash_source gorgon > ~/.gorgon-complete.bash
echo 'source ~/.gorgon-complete.bash' >> ~/.bashrc
""",
        "zsh": """
# Add to ~/.zshrc:
eval "$(_GORGON_COMPLETE=zsh_source gorgon)"

# Or for faster startup, add to ~/.zshrc:
autoload -Uz compinit && compinit
eval "$(_GORGON_COMPLETE=zsh_source gorgon)"
""",
        "fish": """
# Add to ~/.config/fish/completions/gorgon.fish:
_GORGON_COMPLETE=fish_source gorgon > ~/.config/fish/completions/gorgon.fish
""",
    }

    console.print(
        Panel(
            f"[bold]Shell Completion Setup for {shell.upper()}[/bold]\n\n"
            f"{instructions.get(shell, instructions['bash'])}\n"
            "[dim]After adding, restart your shell or source the config file.[/dim]",
            title="Installation Instructions",
            border_style="cyan",
        )
    )


# =============================================================================
# INTERACTIVE AGENT COMMANDS - Your Personal Army
# =============================================================================


@app.command("do")
def do_task(
    task: str = typer.Argument(
        ...,
        help="Natural language description of what you want to do",
    ),
    workflow: str = typer.Option(
        "feature-build",
        "--workflow",
        "-w",
        help="Workflow to use (feature-build, bug-fix, refactor)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would happen without executing",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output results as JSON",
    ),
):
    """Execute a development task using your agent army.

    Examples:
        gorgon do "add user authentication"
        gorgon do "fix the login bug" --workflow bug-fix
        gorgon do "refactor the database module" --workflow refactor
    """
    from test_ai.workflow.loader import load_workflow

    # Detect codebase context
    context = detect_codebase_context()
    context_str = format_context_for_prompt(context)

    console.print(
        Panel(
            f"[bold]{task}[/bold]\n\n[dim]{context_str}[/dim]",
            title="🐍 Gorgon Task",
            border_style="cyan",
        )
    )

    # Load workflow
    workflows_dir = Path(__file__).parent.parent.parent.parent / "workflows"
    workflow_path = workflows_dir / f"{workflow}.yaml"

    if not workflow_path.exists():
        console.print(f"[red]Workflow not found:[/red] {workflow}")
        console.print(f"\nAvailable workflows in {workflows_dir}:")
        for wf in workflows_dir.glob("*.yaml"):
            console.print(f"  • {wf.stem}")
        raise typer.Exit(1)

    try:
        wf_config = load_workflow(workflow_path, validate_path=False)
    except Exception as e:
        console.print(f"[red]Failed to load workflow:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"\n[dim]Using workflow:[/dim] {wf_config.name}")
    console.print(f"[dim]Steps:[/dim] {len(wf_config.steps)}")

    if dry_run:
        console.print("\n[yellow]Dry run - showing plan without executing[/yellow]")
        for i, step in enumerate(wf_config.steps, 1):
            role = step.params.get("role", step.type)
            console.print(f"  {i}. [{step.type}] {step.id} ({role})")
        raise typer.Exit(0)

    # Execute workflow
    executor = get_workflow_executor(dry_run=False)

    inputs = {
        "feature_request": task,
        "codebase_path": context["path"],
        "task_description": task,
        "context": context_str,
    }

    console.print()
    with console.status("[bold cyan]Agents working...", spinner="dots"):
        result = executor.execute(wf_config, inputs=inputs)

    # Display results
    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
        return

    status_color = "green" if result.status == "success" else "red"
    console.print(f"\n[{status_color}]Status: {result.status}[/{status_color}]")

    if result.steps:
        console.print("\n[bold]Agent Activity:[/bold]")
        for step in result.steps:
            icon = (
                "✓"
                if step.status.value == "success"
                else "✗"
                if step.status.value == "failed"
                else "○"
            )
            role = (
                step.output.get("role", step.step_id) if step.output else step.step_id
            )
            tokens = step.tokens_used
            console.print(f"  {icon} {role}: {step.status.value} ({tokens:,} tokens)")

    if result.error:
        console.print(f"\n[red]Error:[/red] {result.error}")

    console.print(f"\n[dim]Total tokens: {result.total_tokens:,}[/dim]")


@app.command()
def plan(
    task: str = typer.Argument(
        ...,
        help="What do you want to plan?",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """Run the Planner agent to break down a task.

    Example:
        gorgon plan "add OAuth2 authentication to the API"
    """
    client = get_claude_client()
    context = detect_codebase_context()
    context_str = format_context_for_prompt(context)

    console.print(
        Panel(
            f"[bold]Planning:[/bold] {task}",
            title="🗺️ Planner Agent",
            border_style="blue",
        )
    )

    prompt = f"""Analyze and create a detailed implementation plan for:

{task}

{context_str}

Provide:
1. Task breakdown with clear steps
2. Files that need to be created or modified
3. Dependencies and order of operations
4. Potential risks and how to mitigate them
5. Success criteria for the implementation"""

    with console.status("[bold blue]Planner thinking...", spinner="dots"):
        result = client.execute_agent(
            role="planner",
            task=prompt,
            context=context_str,
        )

    if json_output:
        print(json.dumps(result, indent=2))
        return

    if result.get("success"):
        console.print("\n[bold]Implementation Plan:[/bold]\n")
        console.print(result.get("output", "No output"))
    else:
        console.print(f"\n[red]Error:[/red] {result.get('error', 'Unknown error')}")


@app.command()
def build(
    description: str = typer.Argument(
        ...,
        help="What to build",
    ),
    plan: Optional[str] = typer.Option(
        None,
        "--plan",
        "-p",
        help="Path to a plan file or inline plan",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """Run the Builder agent to implement code.

    Example:
        gorgon build "user authentication module"
        gorgon build "login endpoint" --plan "1. Create route 2. Add validation"
    """
    client = get_claude_client()
    context = detect_codebase_context()
    context_str = format_context_for_prompt(context)

    console.print(
        Panel(
            f"[bold]Building:[/bold] {description}",
            title="🔨 Builder Agent",
            border_style="green",
        )
    )

    # Load plan if provided as file
    plan_text = ""
    if plan:
        plan_path = Path(plan)
        if plan_path.exists():
            plan_text = plan_path.read_text()
        else:
            plan_text = plan

    prompt = f"""Implement the following:

{description}

{context_str}
"""
    if plan_text:
        prompt += f"""
Based on this plan:
{plan_text}
"""

    prompt += """
Write production-quality code with:
- Type hints (for Python)
- Error handling
- Clear documentation
- Following existing project patterns"""

    with console.status("[bold green]Builder coding...", spinner="dots"):
        result = client.execute_agent(
            role="builder",
            task=prompt,
            context=context_str,
        )

    if json_output:
        print(json.dumps(result, indent=2))
        return

    if result.get("success"):
        console.print("\n[bold]Implementation:[/bold]\n")
        console.print(result.get("output", "No output"))
    else:
        console.print(f"\n[red]Error:[/red] {result.get('error', 'Unknown error')}")


@app.command()
def test(
    target: str = typer.Argument(
        ".",
        help="File or module to test",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """Run the Tester agent to create tests.

    Example:
        gorgon test src/auth/login.py
        gorgon test "the new user registration flow"
    """
    client = get_claude_client()
    context = detect_codebase_context()
    context_str = format_context_for_prompt(context)

    # Check if target is a file
    target_path = Path(target)
    code_context = ""
    if target_path.exists() and target_path.is_file():
        try:
            code_context = (
                f"\nCode to test:\n```\n{target_path.read_text()[:5000]}\n```"
            )
        except Exception:
            pass

    console.print(
        Panel(
            f"[bold]Testing:[/bold] {target}",
            title="🧪 Tester Agent",
            border_style="yellow",
        )
    )

    prompt = f"""Create comprehensive tests for:

{target}

{context_str}
{code_context}

Write tests that include:
- Unit tests for individual functions
- Edge cases and error conditions
- Integration tests where appropriate
- Clear test names that describe behavior
- Following the project's existing test patterns (pytest for Python)"""

    with console.status("[bold yellow]Tester analyzing...", spinner="dots"):
        result = client.execute_agent(
            role="tester",
            task=prompt,
            context=context_str,
        )

    if json_output:
        print(json.dumps(result, indent=2))
        return

    if result.get("success"):
        console.print("\n[bold]Generated Tests:[/bold]\n")
        console.print(result.get("output", "No output"))
    else:
        console.print(f"\n[red]Error:[/red] {result.get('error', 'Unknown error')}")


def _get_git_diff_context(target: str, cwd: Path) -> str:
    """Get code context from git diff."""
    try:
        diff = subprocess.run(
            ["git", "diff", target],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if diff.returncode == 0:
            return f"\nGit diff:\n```diff\n{diff.stdout[:8000]}\n```"
    except Exception:
        pass
    return ""


def _get_file_context(target_path: Path) -> str:
    """Get code context from a single file."""
    try:
        return f"\nCode to review:\n```\n{target_path.read_text()[:8000]}\n```"
    except Exception:
        return ""


def _get_directory_context(target_path: Path) -> str:
    """Get code context from a directory of files."""
    files = list(target_path.rglob("*.py"))[:5]
    code_snippets = []
    for f in files:
        try:
            code_snippets.append(f"# {f}\n{f.read_text()[:2000]}")
        except Exception:
            pass
    if code_snippets:
        return f"\nFiles to review:\n```\n{'---'.join(code_snippets)}\n```"
    return ""


def _gather_review_code_context(target: str, context: dict) -> str:
    """Gather code context for review based on target type."""
    # Check if target is a git ref
    if target.startswith("HEAD") or target.startswith("origin/"):
        return _get_git_diff_context(target, context["path"])

    target_path = Path(target)
    if not target_path.exists():
        return ""

    if target_path.is_file():
        return _get_file_context(target_path)
    if target_path.is_dir():
        return _get_directory_context(target_path)

    return ""


@app.command()
def review(
    target: str = typer.Argument(
        ".",
        help="File, directory, or git diff to review",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """Run the Reviewer agent for code review.

    Example:
        gorgon review src/auth/
        gorgon review HEAD~1  # Review last commit
    """
    client = get_claude_client()
    context = detect_codebase_context()
    context_str = format_context_for_prompt(context)
    code_context = _gather_review_code_context(target, context)

    console.print(
        Panel(
            f"[bold]Reviewing:[/bold] {target}",
            title="🔍 Reviewer Agent",
            border_style="magenta",
        )
    )

    prompt = f"""Review the following code:

{target}

{context_str}
{code_context}

Evaluate:
1. Code quality and readability
2. Security concerns (OWASP top 10, input validation, etc.)
3. Performance implications
4. Error handling completeness
5. Test coverage gaps
6. Adherence to project patterns

Provide:
- Approval recommendation (approved/needs_changes/rejected)
- Score (1-10)
- Specific findings with severity (critical/warning/info)
- Actionable improvement suggestions"""

    with console.status("[bold magenta]Reviewer analyzing...", spinner="dots"):
        result = client.execute_agent(
            role="reviewer",
            task=prompt,
            context=context_str,
        )

    if json_output:
        print(json.dumps(result, indent=2))
        return

    if result.get("success"):
        console.print("\n[bold]Code Review:[/bold]\n")
        console.print(result.get("output", "No output"))
    else:
        console.print(f"\n[red]Error:[/red] {result.get('error', 'Unknown error')}")


@app.command()
def ask(
    question: str = typer.Argument(
        ...,
        help="Question about your codebase",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON",
    ),
):
    """Ask a question about your codebase.

    Example:
        gorgon ask "how does the authentication system work?"
        gorgon ask "what are the main API endpoints?"
    """
    client = get_claude_client()
    context = detect_codebase_context()
    context_str = format_context_for_prompt(context)

    console.print(
        Panel(
            f"[bold]{question}[/bold]",
            title="❓ Question",
            border_style="cyan",
        )
    )

    prompt = f"""Answer this question about the codebase:

{question}

{context_str}

Provide a clear, helpful answer based on the codebase context.
If you need to reference specific files or code, mention them explicitly."""

    with console.status("[bold cyan]Thinking...", spinner="dots"):
        result = client.generate_completion(
            prompt=prompt,
            system_prompt="You are a helpful assistant analyzing a software codebase. Be concise and specific.",
        )

    if json_output:
        print(json.dumps({"question": question, "answer": result}, indent=2))
        return

    if result:
        console.print("\n[bold]Answer:[/bold]\n")
        console.print(result)
    else:
        console.print("[red]No response received[/red]")


# Schedule commands
schedule_app = typer.Typer(help="Manage scheduled workflows")
app.add_typer(schedule_app, name="schedule")


@schedule_app.command("list")
def schedule_list(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all scheduled workflows."""
    try:
        from test_ai.workflow import WorkflowScheduler

        scheduler = WorkflowScheduler()
        schedules = scheduler.list()
    except Exception as e:
        console.print(f"[red]Error loading schedules:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps([s.__dict__ for s in schedules], indent=2, default=str))
        return

    if not schedules:
        console.print("[yellow]No scheduled workflows[/yellow]")
        return

    table = Table(title="Scheduled Workflows")
    table.add_column("ID", style="cyan")
    table.add_column("Workflow")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    for s in schedules:
        schedule_str = (
            s.cron_expression if s.cron_expression else f"every {s.interval_seconds}s"
        )
        status_color = "green" if s.status.value == "active" else "yellow"
        next_run = str(s.next_run_time)[:19] if s.next_run_time else "-"
        table.add_row(
            s.schedule_id[:12],
            s.workflow_path,
            schedule_str,
            f"[{status_color}]{s.status.value}[/{status_color}]",
            next_run,
        )

    console.print(table)


@schedule_app.command("add")
def schedule_add(
    workflow: str = typer.Argument(..., help="Workflow path or ID"),
    cron: str = typer.Option(None, "--cron", "-c", help="Cron expression"),
    interval: int = typer.Option(None, "--interval", "-i", help="Interval in seconds"),
    name: str = typer.Option(None, "--name", "-n", help="Schedule name"),
):
    """Add a new scheduled workflow."""
    if not cron and not interval:
        console.print("[red]Must specify --cron or --interval[/red]")
        raise typer.Exit(1)

    try:
        from test_ai.workflow import WorkflowScheduler, ScheduleConfig

        scheduler = WorkflowScheduler()

        config = ScheduleConfig(
            workflow_path=workflow,
            name=name or f"Schedule for {workflow}",
            cron_expression=cron,
            interval_seconds=interval,
        )
        result = scheduler.add(config)
        scheduler.start()

        console.print(f"[green]✓ Schedule created:[/green] {result.schedule_id}")
        if cron:
            console.print(f"  Cron: {cron}")
        else:
            console.print(f"  Interval: {interval}s")
    except Exception as e:
        console.print(f"[red]Error creating schedule:[/red] {e}")
        raise typer.Exit(1)


@schedule_app.command("remove")
def schedule_remove(
    schedule_id: str = typer.Argument(..., help="Schedule ID to remove"),
):
    """Remove a scheduled workflow."""
    try:
        from test_ai.workflow import WorkflowScheduler

        scheduler = WorkflowScheduler()

        if scheduler.remove(schedule_id):
            console.print(f"[green]✓ Schedule removed:[/green] {schedule_id}")
        else:
            console.print(f"[red]Schedule not found:[/red] {schedule_id}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error removing schedule:[/red] {e}")
        raise typer.Exit(1)


@schedule_app.command("pause")
def schedule_pause(
    schedule_id: str = typer.Argument(..., help="Schedule ID to pause"),
):
    """Pause a scheduled workflow."""
    try:
        from test_ai.workflow import WorkflowScheduler

        scheduler = WorkflowScheduler()

        if scheduler.pause(schedule_id):
            console.print(f"[green]✓ Schedule paused:[/green] {schedule_id}")
        else:
            console.print(f"[red]Schedule not found:[/red] {schedule_id}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error pausing schedule:[/red] {e}")
        raise typer.Exit(1)


@schedule_app.command("resume")
def schedule_resume(
    schedule_id: str = typer.Argument(..., help="Schedule ID to resume"),
):
    """Resume a paused scheduled workflow."""
    try:
        from test_ai.workflow import WorkflowScheduler

        scheduler = WorkflowScheduler()

        if scheduler.resume(schedule_id):
            console.print(f"[green]✓ Schedule resumed:[/green] {schedule_id}")
        else:
            console.print(f"[red]Schedule not found:[/red] {schedule_id}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error resuming schedule:[/red] {e}")
        raise typer.Exit(1)


# Memory commands
memory_app = typer.Typer(help="Manage agent memory")
app.add_typer(memory_app, name="memory")


@memory_app.command("list")
def memory_list(
    agent: str = typer.Option(None, "--agent", "-a", help="Filter by agent ID"),
    memory_type: str = typer.Option(None, "--type", "-t", help="Filter by type"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum entries"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List agent memories."""
    try:
        from test_ai.state import AgentMemory

        memory = AgentMemory()

        if agent:
            memories = memory.recall(agent, memory_type=memory_type, limit=limit)
        else:
            # Get all agents' memories
            memories = memory.backend.fetchall(
                "SELECT * FROM agent_memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            from test_ai.state.memory import MemoryEntry

            memories = [MemoryEntry.from_dict(m) for m in memories]
    except Exception as e:
        console.print(f"[red]Error loading memories:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps([m.to_dict() for m in memories], indent=2, default=str))
        return

    if not memories:
        console.print("[yellow]No memories found[/yellow]")
        return

    table = Table(title="Agent Memories")
    table.add_column("ID", style="dim")
    table.add_column("Agent", style="cyan")
    table.add_column("Type")
    table.add_column("Content")
    table.add_column("Importance", justify="right")

    for m in memories:
        content = m.content[:50] + "..." if len(m.content) > 50 else m.content
        table.add_row(
            str(m.id),
            m.agent_id,
            m.memory_type,
            content,
            f"{m.importance:.2f}",
        )

    console.print(table)


@memory_app.command("stats")
def memory_stats(
    agent: str = typer.Argument(..., help="Agent ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show memory statistics for an agent."""
    try:
        from test_ai.state import AgentMemory

        memory = AgentMemory()
        stats = memory.get_stats(agent)
    except Exception as e:
        console.print(f"[red]Error getting stats:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(stats, indent=2))
        return

    console.print(
        Panel(
            f"Total Memories: [bold]{stats['total_memories']}[/bold]\n"
            f"Average Importance: [bold]{stats['average_importance']:.2f}[/bold]",
            title=f"Memory Stats: {agent}",
            border_style="blue",
        )
    )

    if stats["by_type"]:
        console.print("\n[dim]By Type:[/dim]")
        for mtype, count in stats["by_type"].items():
            console.print(f"  {mtype}: {count}")


@memory_app.command("clear")
def memory_clear(
    agent: str = typer.Argument(..., help="Agent ID"),
    memory_type: str = typer.Option(None, "--type", "-t", help="Only clear this type"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Clear agent memories."""
    if not force:
        msg = f"Clear all memories for agent '{agent}'"
        if memory_type:
            msg += f" of type '{memory_type}'"
        if not typer.confirm(f"{msg}?"):
            raise typer.Abort()

    try:
        from test_ai.state import AgentMemory

        memory = AgentMemory()
        count = memory.forget(agent, memory_type=memory_type)
        console.print(f"[green]✓ Cleared {count} memories[/green]")
    except Exception as e:
        console.print(f"[red]Error clearing memories:[/red] {e}")
        raise typer.Exit(1)


# Budget commands
budget_app = typer.Typer(help="View budget and usage")
app.add_typer(budget_app, name="budget")


@budget_app.command("status")
def budget_status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show current budget status."""
    try:
        from test_ai.budget import BudgetManager

        manager = BudgetManager()
        stats = manager.get_stats()
    except Exception as e:
        console.print(f"[red]Error getting budget:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(stats, indent=2, default=str))
        return

    used_pct = (
        (stats["used"] / stats["total_budget"] * 100)
        if stats["total_budget"] > 0
        else 0
    )
    status_color = "green" if used_pct < 75 else "yellow" if used_pct < 90 else "red"

    console.print(
        Panel(
            f"Total Budget: [bold]{stats['total_budget']:,}[/bold] tokens\n"
            f"Used: [bold]{stats['used']:,}[/bold] tokens ([{status_color}]{used_pct:.1f}%[/{status_color}])\n"
            f"Remaining: [bold]{stats['remaining']:,}[/bold] tokens\n"
            f"Operations: [bold]{stats['total_operations']}[/bold]",
            title="Budget Status",
            border_style="blue",
        )
    )

    if stats.get("agents"):
        console.print("\n[dim]Usage by Agent:[/dim]")
        for agent_id, usage in stats["agents"].items():
            console.print(f"  {agent_id}: {usage:,} tokens")


@budget_app.command("history")
def budget_history(
    agent: str = typer.Option(None, "--agent", "-a", help="Filter by agent"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum entries"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show budget usage history."""
    try:
        from test_ai.budget import BudgetManager

        manager = BudgetManager()
        history = manager.get_usage_history(agent)[:limit]
    except Exception as e:
        console.print(f"[red]Error getting history:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps([h.__dict__ for h in history], indent=2, default=str))
        return

    if not history:
        console.print("[yellow]No usage history[/yellow]")
        return

    table = Table(title="Usage History")
    table.add_column("Time", style="dim")
    table.add_column("Agent", style="cyan")
    table.add_column("Tokens", justify="right")
    table.add_column("Operation")

    for record in history:
        time_str = str(record.timestamp)[:19] if record.timestamp else "-"
        table.add_row(
            time_str,
            record.agent_id,
            f"{record.tokens:,}",
            record.operation[:30] if record.operation else "-",
        )

    console.print(table)


@budget_app.command("reset")
def budget_reset(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Reset budget tracking."""
    if not force:
        if not typer.confirm("Reset all budget tracking? This cannot be undone."):
            raise typer.Abort()

    try:
        from test_ai.budget import BudgetManager

        manager = BudgetManager()
        manager.reset()
        console.print("[green]✓ Budget tracking reset[/green]")
    except Exception as e:
        console.print(f"[red]Error resetting budget:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# METRICS COMMANDS
# =============================================================================

metrics_app = typer.Typer(help="Export and view metrics")
app.add_typer(metrics_app, name="metrics")


@metrics_app.command("export")
def metrics_export(
    format: str = typer.Option(
        "prometheus",
        "--format",
        "-f",
        help="Export format (prometheus, json, text)",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file (stdout if not specified)"
    ),
):
    """Export workflow metrics."""
    try:
        from test_ai.metrics import (
            PrometheusExporter,
            JsonExporter,
            get_collector,
        )

        collector = get_collector()

        if format == "prometheus":
            exporter = PrometheusExporter()
            content = exporter.export(collector)
        elif format == "json":
            exporter = JsonExporter()
            content = exporter.export(collector)
        else:
            # Text summary
            summary = collector.get_summary()
            lines = [
                "Gorgon Metrics Summary",
                "=" * 40,
                f"Workflows Total: {summary['workflows_total']}",
                f"Workflows Active: {summary['workflows_active']}",
                f"Workflows Completed: {summary['workflows_completed']}",
                f"Workflows Failed: {summary['workflows_failed']}",
                f"Success Rate: {summary['success_rate']:.1%}",
                f"Tokens Used: {summary['tokens_used']:,}",
            ]
            if summary.get("avg_duration_ms"):
                lines.append(f"Avg Duration: {summary['avg_duration_ms']:.0f}ms")
            content = "\n".join(lines)

        if output:
            output.write_text(content)
            console.print(f"[green]✓ Metrics exported to:[/green] {output}")
        else:
            print(content)

    except Exception as e:
        console.print(f"[red]Error exporting metrics:[/red] {e}")
        raise typer.Exit(1)


@metrics_app.command("serve")
def metrics_serve(
    port: int = typer.Option(9090, "--port", "-p", help="Port to serve metrics on"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
):
    """Start Prometheus metrics HTTP server."""
    try:
        from test_ai.metrics import PrometheusMetricsServer, get_collector

        collector = get_collector()
        server = PrometheusMetricsServer(collector, host=host, port=port)

        console.print("[cyan]Starting Prometheus metrics server...[/cyan]")
        console.print(f"[bold]URL:[/bold] http://{host}:{port}/metrics")
        console.print(f"[bold]Health:[/bold] http://{host}:{port}/health")
        console.print("\n[dim]Press Ctrl+C to stop[/dim]")

        server.start()

        try:
            import time

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            server.stop()
            console.print("[green]✓ Server stopped[/green]")

    except Exception as e:
        console.print(f"[red]Error starting server:[/red] {e}")
        raise typer.Exit(1)


@metrics_app.command("push")
def metrics_push(
    gateway_url: str = typer.Argument(..., help="Push gateway URL"),
    job: str = typer.Option("gorgon", "--job", "-j", help="Job name"),
    instance: str = typer.Option(None, "--instance", "-i", help="Instance name"),
):
    """Push metrics to Prometheus Push Gateway."""
    try:
        from test_ai.metrics import PrometheusPushGateway, get_collector

        collector = get_collector()
        gateway = PrometheusPushGateway(
            url=gateway_url,
            job=job,
            instance=instance,
        )

        with console.status("[cyan]Pushing metrics...", spinner="dots"):
            success = gateway.push(collector)

        if success:
            console.print(f"[green]✓ Metrics pushed to:[/green] {gateway_url}")
        else:
            console.print("[red]Failed to push metrics[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error pushing metrics:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# CONFIG COMMANDS
# =============================================================================

config_app = typer.Typer(help="View and manage configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show current configuration."""
    try:
        from test_ai.config import get_config

        config = get_config()
        config_dict = config.model_dump()
    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        config_dict = {}

    # Mask sensitive values
    masked = {}
    for key, value in config_dict.items():
        if any(s in key.lower() for s in ["key", "secret", "password", "token"]):
            masked[key] = "****" if value else None
        else:
            masked[key] = value

    if json_output:
        print(json.dumps(masked, indent=2, default=str))
        return

    console.print(Panel("[bold]Gorgon Configuration[/bold]", border_style="blue"))

    table = Table(show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    for key, value in sorted(masked.items()):
        display_value = str(value) if value is not None else "[dim]not set[/dim]"
        if display_value == "****":
            display_value = "[green]****[/green]"
        table.add_row(key, display_value)

    console.print(table)


@config_app.command("path")
def config_path():
    """Show configuration file paths."""
    from pathlib import Path
    import os

    console.print("[bold]Configuration Sources[/bold]\n")

    # .env file
    env_path = Path(".env")
    if env_path.exists():
        console.print(f"[green]✓[/green] .env: {env_path.absolute()}")
    else:
        console.print("[yellow]○[/yellow] .env: not found")

    # Environment variables
    gorgon_vars = {k: v for k, v in os.environ.items() if k.startswith("GORGON_")}
    if gorgon_vars:
        console.print(f"\n[bold]Environment Variables ({len(gorgon_vars)}):[/bold]")
        for key in sorted(gorgon_vars.keys()):
            console.print(f"  {key}")
    else:
        console.print("\n[dim]No GORGON_* environment variables set[/dim]")

    # Config directories
    console.print("\n[bold]Search Paths:[/bold]")
    console.print("  ./config/")
    console.print("  ~/.config/gorgon/")


@config_app.command("env")
def config_env():
    """Show required environment variables."""
    env_vars = [
        ("ANTHROPIC_API_KEY", "Anthropic/Claude API key", True),
        ("OPENAI_API_KEY", "OpenAI API key", True),
        ("GITHUB_TOKEN", "GitHub personal access token", False),
        ("NOTION_TOKEN", "Notion API token", False),
        ("GORGON_LOG_LEVEL", "Log level (DEBUG, INFO, WARNING, ERROR)", False),
        ("GORGON_BUDGET_LIMIT", "Token budget limit", False),
        ("GORGON_WORKFLOWS_DIR", "Workflows directory path", False),
    ]

    import os

    console.print("[bold]Environment Variables[/bold]\n")

    table = Table()
    table.add_column("Variable", style="cyan")
    table.add_column("Description")
    table.add_column("Required")
    table.add_column("Status")

    for var, desc, required in env_vars:
        value = os.environ.get(var)
        if value:
            status = "[green]✓ set[/green]"
        elif required:
            status = "[red]✗ missing[/red]"
        else:
            status = "[dim]not set[/dim]"

        req = "[yellow]yes[/yellow]" if required else "no"
        table.add_row(var, desc, req, status)

    console.print(table)


# =============================================================================
# DASHBOARD COMMAND
# =============================================================================


@app.command()
def dashboard(
    port: int = typer.Option(8501, "--port", "-p", help="Port to run dashboard on"),
    host: str = typer.Option("localhost", "--host", "-h", help="Host to bind to"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't open browser automatically"
    ),
):
    """Launch the Gorgon web dashboard."""
    import webbrowser

    dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"

    if not dashboard_path.exists():
        console.print(f"[red]Dashboard not found at:[/red] {dashboard_path}")
        raise typer.Exit(1)

    url = f"http://{host}:{port}"
    console.print("[cyan]Starting Gorgon Dashboard...[/cyan]")
    console.print(f"[bold]URL:[/bold] {url}")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

    if not no_browser:
        webbrowser.open(url)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(dashboard_path),
                "--server.port",
                str(port),
                "--server.address",
                host,
                "--server.headless",
                "true",
            ],
        )
        if result.returncode != 0:
            raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")


# =============================================================================
# PLUGINS COMMANDS
# =============================================================================

plugins_app = typer.Typer(help="Manage plugins")
app.add_typer(plugins_app, name="plugins")


@plugins_app.command("list")
def plugins_list(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List installed plugins."""
    try:
        from test_ai.plugins import PluginManager

        manager = PluginManager()
        plugins = manager.list_plugins()
    except Exception as e:
        console.print(f"[red]Error loading plugins:[/red] {e}")
        plugins = []

    if json_output:
        print(json.dumps([p.to_dict() for p in plugins], indent=2))
        return

    if not plugins:
        console.print("[yellow]No plugins installed[/yellow]")
        console.print(
            "\n[dim]Plugins extend Gorgon with custom step types and integrations.[/dim]"
        )
        return

    table = Table(title="Installed Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Status")

    for plugin in plugins:
        status = "[green]active[/green]" if plugin.enabled else "[dim]disabled[/dim]"
        table.add_row(
            plugin.name,
            plugin.version,
            plugin.description[:40] if plugin.description else "-",
            status,
        )

    console.print(table)


@plugins_app.command("info")
def plugins_info(
    name: str = typer.Argument(..., help="Plugin name"),
):
    """Show detailed plugin information."""
    try:
        from test_ai.plugins import PluginManager

        manager = PluginManager()
        plugin = manager.get_plugin(name)

        if not plugin:
            console.print(f"[red]Plugin not found:[/red] {name}")
            raise typer.Exit(1)

        console.print(
            Panel(
                f"[bold]{plugin.name}[/bold] v{plugin.version}\n\n"
                f"{plugin.description or 'No description'}\n\n"
                f"[dim]Author:[/dim] {plugin.author or 'Unknown'}\n"
                f"[dim]Status:[/dim] {'Enabled' if plugin.enabled else 'Disabled'}",
                title="Plugin Info",
                border_style="cyan",
            )
        )

        if plugin.step_types:
            console.print("\n[bold]Step Types:[/bold]")
            for step_type in plugin.step_types:
                console.print(f"  • {step_type}")

        if plugin.hooks:
            console.print("\n[bold]Hooks:[/bold]")
            for hook in plugin.hooks:
                console.print(f"  • {hook}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# =============================================================================
# LOGS COMMAND
# =============================================================================


@app.command()
def logs(
    workflow: str = typer.Option(None, "--workflow", "-w", help="Filter by workflow"),
    execution: str = typer.Option(
        None, "--execution", "-e", help="Filter by execution ID"
    ),
    level: str = typer.Option(
        "INFO", "--level", "-l", help="Minimum log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of recent entries"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """View workflow execution logs."""
    import time

    try:
        tracker = get_tracker()
        if not tracker:
            console.print("[yellow]Tracker not available[/yellow]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error accessing logs:[/red] {e}")
        raise typer.Exit(1)

    def format_log_entry(entry: dict) -> str:
        """Format a single log entry."""
        ts = entry.get("timestamp", "")[:19]
        lvl = entry.get("level", "INFO")
        msg = entry.get("message", "")
        wf = entry.get("workflow_id", "")
        ex = entry.get("execution_id", "")[:8] if entry.get("execution_id") else ""

        level_colors = {
            "DEBUG": "dim",
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "red",
        }
        color = level_colors.get(lvl, "white")

        if wf:
            return f"[dim]{ts}[/dim] [{color}]{lvl:7}[/{color}] [{wf}:{ex}] {msg}"
        return f"[dim]{ts}[/dim] [{color}]{lvl:7}[/{color}] {msg}"

    def get_logs():
        """Fetch logs from tracker."""
        try:
            logs = tracker.get_logs(
                workflow_id=workflow,
                execution_id=execution,
                level=level,
                limit=tail,
            )
            return logs
        except AttributeError:
            # Tracker doesn't have get_logs, use dashboard data
            data = tracker.get_dashboard_data()
            return data.get("recent_logs", [])

    logs_data = get_logs()

    if json_output:
        print(json.dumps(logs_data, indent=2, default=str))
        return

    if not logs_data:
        console.print("[yellow]No logs found[/yellow]")
        if not follow:
            return

    # Display existing logs
    for entry in logs_data:
        console.print(format_log_entry(entry))

    # Follow mode
    if follow:
        console.print("\n[dim]Following logs... (Ctrl+C to stop)[/dim]\n")
        seen = set(str(e) for e in logs_data)
        try:
            while True:
                time.sleep(2)
                new_logs = get_logs()
                for entry in new_logs:
                    entry_str = str(entry)
                    if entry_str not in seen:
                        seen.add(entry_str)
                        console.print(format_log_entry(entry))
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped following logs[/dim]")


if __name__ == "__main__":
    app()
