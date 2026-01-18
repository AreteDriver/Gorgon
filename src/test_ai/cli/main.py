"""Gorgon CLI - Main entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(
    name="gorgon",
    help="Multi-agent orchestration framework for production AI workflows",
    add_completion=False,
)
console = Console()


def get_workflow_engine():
    """Lazy import workflow engine to avoid startup cost."""
    try:
        from test_ai.orchestrator import WorkflowEngine

        return WorkflowEngine()
    except ImportError as e:
        console.print(f"[red]Missing dependencies:[/red] {e}")
        console.print("Run: pip install pydantic-settings")
        raise typer.Exit(1)


def get_tracker():
    """Lazy import execution tracker."""
    try:
        from test_ai.monitoring.tracker import get_tracker as _get_tracker

        return _get_tracker()
    except ImportError:
        return None


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

    # Parse variables
    variables = {}
    for v in var:
        if "=" in v:
            key, value = v.split("=", 1)
            variables[key] = value
        else:
            console.print(f"[red]Invalid variable format: {v}[/red]")
            console.print("Use: --var key=value")
            raise typer.Exit(1)

    # Load workflow
    workflow_path = Path(workflow)
    if workflow_path.exists() and workflow_path.suffix == ".json":
        # Load from file
        try:
            with open(workflow_path) as f:
                workflow_data = json.load(f)
            workflow_id = workflow_data.get("id", workflow_path.stem)
            console.print(f"[dim]Loading workflow from:[/dim] {workflow_path}")
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON in workflow file:[/red] {e}")
            raise typer.Exit(1)
    else:
        # Load by ID from engine
        workflow_id = workflow
        loaded = engine.load_workflow(workflow_id)
        if not loaded:
            console.print(f"[red]Workflow not found:[/red] {workflow_id}")
            console.print("\nAvailable workflows:")
            list_workflows_table(engine)
            raise typer.Exit(1)
        workflow_data = loaded.model_dump()

    # Show workflow info
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

    if dry_run:
        console.print("\n[yellow]Dry run - workflow not executed[/yellow]")
        raise typer.Exit(0)

    # Execute workflow
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Executing workflow...", total=None)

        try:
            # Load and execute
            wf = (
                engine.load_workflow(workflow_id)
                if not workflow_path.exists()
                else None
            )
            if wf:
                wf.variables = variables
                result = engine.execute_workflow(wf)
            else:
                # Execute from file
                from test_ai.orchestrator import Workflow

                wf = Workflow(**workflow_data)
                wf.variables = variables
                result = engine.execute_workflow(wf)

            progress.update(task, description="Complete!")
        except Exception as e:
            progress.stop()
            console.print(f"\n[red]Execution failed:[/red] {e}")
            raise typer.Exit(1)

    # Output results
    if json_output:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    else:
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

    errors = []
    warnings = []

    # Required fields
    if "id" not in data:
        errors.append("Missing required field: id")
    if "steps" not in data:
        errors.append("Missing required field: steps")
    elif not isinstance(data["steps"], list):
        errors.append("'steps' must be a list")
    elif len(data["steps"]) == 0:
        warnings.append("Workflow has no steps")

    # Validate steps
    step_ids = set()
    for i, step in enumerate(data.get("steps", [])):
        step_prefix = f"Step {i + 1}"

        if "id" not in step:
            errors.append(f"{step_prefix}: Missing 'id'")
        else:
            if step["id"] in step_ids:
                errors.append(f"{step_prefix}: Duplicate step ID '{step['id']}'")
            step_ids.add(step["id"])

        if "type" not in step:
            errors.append(f"{step_prefix}: Missing 'type'")
        elif step["type"] not in ["claude_code", "openai", "transform", "condition"]:
            warnings.append(f"{step_prefix}: Unknown step type '{step['type']}'")

        if "action" not in step:
            errors.append(f"{step_prefix}: Missing 'action'")

        # next_step references are validated in the loop below

    # Validate next_step references
    for step in data.get("steps", []):
        if "next_step" in step and step["next_step"]:
            if step["next_step"] not in step_ids:
                errors.append(
                    f"Step '{step.get('id', '?')}': next_step '{step['next_step']}' not found"
                )

    # Output results
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


@app.command()
def version():
    """Show Gorgon version."""
    console.print("[bold]Gorgon[/bold] v0.3.0")
    console.print("[dim]Multi-agent orchestration framework[/dim]")


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
        schedule_str = s.cron_expression if s.cron_expression else f"every {s.interval_seconds}s"
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

    console.print(Panel(
        f"Total Memories: [bold]{stats['total_memories']}[/bold]\n"
        f"Average Importance: [bold]{stats['average_importance']:.2f}[/bold]",
        title=f"Memory Stats: {agent}",
        border_style="blue",
    ))

    if stats['by_type']:
        console.print("\n[dim]By Type:[/dim]")
        for mtype, count in stats['by_type'].items():
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

    used_pct = (stats['used'] / stats['total_budget'] * 100) if stats['total_budget'] > 0 else 0
    status_color = "green" if used_pct < 75 else "yellow" if used_pct < 90 else "red"

    console.print(Panel(
        f"Total Budget: [bold]{stats['total_budget']:,}[/bold] tokens\n"
        f"Used: [bold]{stats['used']:,}[/bold] tokens ([{status_color}]{used_pct:.1f}%[/{status_color}])\n"
        f"Remaining: [bold]{stats['remaining']:,}[/bold] tokens\n"
        f"Operations: [bold]{stats['total_operations']}[/bold]",
        title="Budget Status",
        border_style="blue",
    ))

    if stats.get('agents'):
        console.print("\n[dim]Usage by Agent:[/dim]")
        for agent_id, usage in stats['agents'].items():
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


@app.callback()
def main():
    """
    Gorgon - Multi-agent orchestration framework for production AI workflows.

    Run 'gorgon --help' for available commands.
    """
    pass


if __name__ == "__main__":
    app()
