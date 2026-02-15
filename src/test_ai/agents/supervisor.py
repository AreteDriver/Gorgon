"""Supervisor agent for autonomous multi-agent orchestration.

The Supervisor analyzes user requests and autonomously delegates
to specialized agents: Planner, Builder, Tester, Reviewer, Architect,
and Documenter.

Also handles filesystem tool calls when a project_path is configured,
allowing agents to read files, search code, and propose edits.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncGenerator

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from test_ai.providers.base import BaseProvider
    from test_ai.budget.manager import BudgetManager
    from test_ai.chat.models import ChatMessage, ChatMode, ChatSession
    from test_ai.state.backends import DatabaseBackend
    from test_ai.agents.convergence import DelegationConvergenceChecker
    from test_ai.skills.library import SkillLibrary

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Available agent roles for delegation."""

    SUPERVISOR = "supervisor"
    PLANNER = "planner"
    BUILDER = "builder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    ARCHITECT = "architect"
    DOCUMENTER = "documenter"
    ANALYST = "analyst"


@dataclass
class AgentDelegation:
    """Represents a delegation to a sub-agent."""

    agent: AgentRole
    task: str
    context: dict[str, Any] | None = None
    completed: bool = False
    result: str | None = None
    error: str | None = None


class DelegationPlan(BaseModel):
    """Plan for agent delegations."""

    analysis: str = Field(description="Analysis of the user request")
    delegations: list[dict] = Field(
        description="List of agent delegations with 'agent' and 'task' keys"
    )
    synthesis_approach: str = Field(description="How to synthesize results from agents")


SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor agent for Gorgon, an AI orchestration system.

Your role is to analyze user requests and delegate to specialized AI agents:

**Available Agents:**
- **Planner**: Strategic planning, feature decomposition, task breakdown, project roadmaps
- **Builder**: Code implementation, feature development, bug fixes, refactoring
- **Tester**: Test suite creation, test coverage analysis, QA automation
- **Reviewer**: Code review, security audits, best practices enforcement
- **Architect**: System design, architectural decisions, technology selection
- **Documenter**: Documentation, API references, tutorials, technical guides
- **Analyst**: Data analysis, pattern recognition, metrics interpretation

**Workflow:**
1. Analyze the user's request to understand intent and scope
2. Determine which agents should be involved
3. Create specific tasks for each agent
4. Synthesize results into a coherent response

**Guidelines:**
- For simple questions, respond directly without delegation
- For complex tasks, delegate to multiple agents as needed
- Agents work in parallel when independent, sequentially when dependent
- Always explain your reasoning to the user
- Report progress as agents complete their work

**Response Format:**
When you need to delegate, respond with a JSON block:
```json
{
  "analysis": "Brief analysis of the request",
  "delegations": [
    {"agent": "planner", "task": "Specific task for planner"},
    {"agent": "builder", "task": "Specific task for builder"}
  ],
  "synthesis_approach": "How you'll combine results"
}
```

For direct responses without delegation, just respond naturally.
"""

SELF_IMPROVE_PROMPT_ADDITION = """
**Self-Improvement Mode:**
You are operating on the Gorgon codebase itself. You have special permissions to:
- Analyze Gorgon's own code for improvements
- Propose changes to Gorgon's implementation
- Create PRs for self-improvement

**Safety Rules:**
- Never modify security-critical files (auth, credentials, self_improve module)
- All changes require human approval before merging
- Run tests before proposing changes
- Keep changes focused and minimal
"""

FILESYSTEM_TOOLS_PROMPT = """
**Filesystem Tools:**
You have access to the project files. Use these tools to explore and understand the codebase:

**Available Tools:**
- `read_file`: Read a file's content. Args: path (required), start_line, end_line
- `list_files`: List files in a directory. Args: path (default "."), pattern (glob), recursive
- `search_code`: Search for patterns in files. Args: pattern (regex), path, file_pattern
- `get_structure`: Get project tree overview. Args: max_depth (default 4)
- `propose_edit`: Propose a file change for approval. Args: path, new_content, description

**Tool Call Format:**
To use a tool, include a tool_call block in your response:
<tool_call>
{"tool": "read_file", "path": "src/main.py"}
</tool_call>

Tool results will be injected as:
<tool_result>
{"tool": "read_file", "success": true, "data": {...}}
</tool_result>

**Guidelines:**
- Read files before suggesting changes
- Use search_code to find relevant code
- Use get_structure to understand project layout
- Proposed edits require user approval before applying
- Keep file operations focused and minimal
"""


class SupervisorAgent:
    """Orchestrates multi-agent workflows through intelligent delegation."""

    # Minimum tokens required to proceed with a delegation
    MIN_DELEGATION_TOKENS = 5000

    def __init__(
        self,
        provider: "BaseProvider",
        mode: "ChatMode | None" = None,
        session: "ChatSession | None" = None,
        backend: "DatabaseBackend | None" = None,
        convergence_checker: "DelegationConvergenceChecker | None" = None,
        skill_library: "SkillLibrary | None" = None,
        coordination_bridge: Any = None,
        budget_manager: "BudgetManager | None" = None,
    ):
        """Initialize the Supervisor agent.

        Args:
            provider: LLM provider for generating responses.
            mode: Operating mode (assistant or self_improve).
            session: Chat session for filesystem access context.
            backend: Database backend for proposal storage.
            convergence_checker: Optional Convergent coherence checker.
            skill_library: Optional skill library for v2 routing and context.
            coordination_bridge: Optional Convergent GorgonBridge for prompt enrichment.
            budget_manager: Optional BudgetManager for token budget enforcement.
        """
        self.provider = provider
        self.mode = mode
        self.session = session
        self.backend = backend
        self._convergence_checker = convergence_checker
        self._skill_library = skill_library
        self._bridge = coordination_bridge
        self._budget_manager = budget_manager
        self._active_delegations: list[AgentDelegation] = []
        self._filesystem_tools = None
        self._proposal_manager = None

        # Initialize filesystem tools if session has project access
        if session and session.has_project_access and backend:
            self._init_filesystem_tools()

    def _init_filesystem_tools(self) -> None:
        """Initialize filesystem tools for the session."""
        from test_ai.tools.safety import PathValidator, SecurityError
        from test_ai.tools.filesystem import FilesystemTools
        from test_ai.tools.proposals import ProposalManager

        try:
            validator = PathValidator(
                project_path=self.session.project_path,
                allowed_paths=self.session.allowed_paths,
            )
            self._filesystem_tools = FilesystemTools(validator)
            self._proposal_manager = ProposalManager(self.backend, validator)
            logger.info(f"Filesystem tools initialized for {self.session.project_path}")
        except SecurityError as e:
            logger.warning(f"Failed to initialize filesystem tools: {e}")

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on mode and capabilities."""
        prompt = SUPERVISOR_SYSTEM_PROMPT
        if self.mode and self.mode.value == "self_improve":
            prompt += SELF_IMPROVE_PROMPT_ADDITION
        if self._filesystem_tools:
            prompt += FILESYSTEM_TOOLS_PROMPT
        if self._skill_library:
            routing_summary = self._skill_library.build_routing_summary()
            if routing_summary:
                prompt += "\n\n" + routing_summary
        return prompt

    def _build_context(
        self,
        messages: list["ChatMessage"],
        project_path: str | None = None,
    ) -> list[dict[str, str]]:
        """Build conversation context for the LLM.

        Args:
            messages: Chat history.
            project_path: Optional project context path.

        Returns:
            List of message dicts for the LLM.
        """
        context = [{"role": "system", "content": self._build_system_prompt()}]

        if project_path:
            context.append(
                {
                    "role": "system",
                    "content": f"Project context: {project_path}",
                }
            )

        # Add conversation history
        for msg in messages:
            context.append(
                {
                    "role": msg.role.value,
                    "content": msg.content,
                }
            )

        return context

    async def process_message(
        self,
        content: str,
        messages: list["ChatMessage"],
        project_path: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process a user message and stream the response.

        Args:
            content: The user's message.
            messages: Previous conversation history.
            project_path: Optional project context.

        Yields:
            Stream chunks with type, content, agent, etc.
        """
        context = self._build_context(messages, project_path)

        # Add the new user message
        context.append({"role": "user", "content": content})

        # Conversation loop for tool calls
        max_tool_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_tool_iterations:
            iteration += 1

            # Get response from LLM
            full_response = ""
            async for chunk in self._stream_response(context):
                full_response += chunk
                yield {"type": "text", "content": chunk, "agent": "supervisor"}

            # Check for tool calls
            tool_calls = self._parse_tool_calls(full_response)

            if tool_calls and self._filesystem_tools:
                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    result = await self._execute_tool_call(tool_call)
                    tool_results.append(result)

                    # Yield tool result to client
                    yield {
                        "type": "tool_result",
                        "content": json.dumps(result, default=str),
                        "agent": "supervisor",
                    }

                # Add assistant response and tool results to context for next iteration
                context.append({"role": "assistant", "content": full_response})

                # Build tool results message
                results_content = "\n".join(
                    f"<tool_result>\n{json.dumps(r, default=str)}\n</tool_result>"
                    for r in tool_results
                )
                context.append({"role": "user", "content": results_content})

                # Continue loop to process tool results
                continue

            # No tool calls, check for delegations and exit loop
            break

        # Check if response contains delegation plan
        delegation_plan = self._parse_delegation(full_response)

        if delegation_plan:
            yield {
                "type": "agent",
                "content": f"Delegating to {len(delegation_plan.delegations)} agent(s)...",
                "agent": "supervisor",
            }

            # Execute delegations
            results = await self._execute_delegations(
                delegation_plan.delegations,
                context,
                lambda chunk: None,  # Progress callback
            )

            # Synthesize results
            yield {
                "type": "text",
                "content": "\n\n---\n\n**Synthesis:**\n\n",
                "agent": "supervisor",
            }

            synthesis = await self._synthesize_results(
                delegation_plan, results, context
            )
            yield {"type": "text", "content": synthesis, "agent": "supervisor"}

        yield {"type": "done", "content": None, "agent": "supervisor"}

    async def _stream_response(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream response from the LLM.

        Args:
            messages: Conversation messages.

        Yields:
            Text chunks.
        """
        try:
            # Use streaming if provider supports it
            if hasattr(self.provider, "stream_completion"):
                async for chunk in self.provider.stream_completion(messages):
                    yield chunk
            else:
                # Fall back to non-streaming
                response = await self.provider.complete(messages)
                yield response
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield f"\n\n[Error: {str(e)}]"

    def _parse_delegation(self, response: str) -> DelegationPlan | None:
        """Parse delegation plan from response.

        Args:
            response: LLM response text.

        Returns:
            DelegationPlan if found, None otherwise.
        """
        # Look for JSON block in response
        try:
            # Find JSON between ```json and ```
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)

                # Validate required fields
                if "delegations" in data and len(data["delegations"]) > 0:
                    return DelegationPlan(
                        analysis=data.get("analysis", ""),
                        delegations=data["delegations"],
                        synthesis_approach=data.get("synthesis_approach", ""),
                    )
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"No valid delegation plan in response: {e}")

        return None

    async def _execute_delegations(
        self,
        delegations: list[dict],
        context: list[dict[str, str]],
        progress_callback,
    ) -> dict[str, str]:
        """Execute delegations to sub-agents.

        Args:
            delegations: List of delegation dicts.
            context: Conversation context.
            progress_callback: Callback for progress updates.

        Returns:
            Dict mapping agent names to their results.
        """
        results = {}

        # Check delegations for coherence before parallel execution
        if self._convergence_checker and self._convergence_checker.enabled:
            from test_ai.agents.convergence import format_convergence_alert

            convergence = self._convergence_checker.check_delegations(delegations)
            alert = format_convergence_alert(convergence)
            if alert:
                logger.warning("Convergence alert:\n%s", alert)
            if convergence.dropped_agents:
                original_count = len(delegations)
                delegations = [
                    d
                    for d in delegations
                    if d.get("agent") not in convergence.dropped_agents
                ]
                logger.info(
                    "Dropped %d/%d redundant delegations",
                    original_count - len(delegations),
                    original_count,
                )

        # Check skill consensus levels before execution
        if self._skill_library:
            for delegation in delegations:
                agent = delegation.get("agent", "unknown")
                task_desc = delegation.get("task", "")
                matched_skills = self._skill_library.find_skills_for_task(task_desc)
                for skill in matched_skills:
                    if skill.consensus_level not in ("any", ""):
                        delegation["_skill_consensus"] = skill.consensus_level
                        delegation["_skill_name"] = skill.name
                        logger.info(
                            "Skill %s requires %s consensus for agent %s",
                            skill.name,
                            skill.consensus_level,
                            agent,
                        )
                        break

        # Budget gate: skip delegations when budget is critically low
        if self._budget_manager is not None:
            if not self._budget_manager.can_allocate(self.MIN_DELEGATION_TOKENS):
                logger.warning(
                    "Budget critical (%d tokens remaining) — skipping %d delegation(s)",
                    self._budget_manager.remaining,
                    len(delegations),
                )
                for d in delegations:
                    agent = d.get("agent", "unknown")
                    results[agent] = (
                        f"Delegation skipped: budget critical "
                        f"({self._budget_manager.remaining} tokens remaining)"
                    )
                return results

        # Group by dependency (for now, run all in parallel)
        tasks = []
        for delegation in delegations:
            agent = delegation.get("agent", "unknown")
            task = delegation.get("task", "")

            tasks.append(self._run_agent(agent, task, context))

        # Execute all in parallel
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(completed):
            agent = delegations[i].get("agent", f"agent_{i}")
            if isinstance(result, Exception):
                results[agent] = f"Error: {str(result)}"
            else:
                results[agent] = result

        # Record token usage estimates per agent
        if self._budget_manager is not None:
            for agent_name, agent_result in results.items():
                try:
                    # Rough estimate: 4 chars ≈ 1 token
                    estimated_tokens = max(len(agent_result) // 4, 100)
                    self._budget_manager.record_usage(
                        agent_id=agent_name,
                        tokens=estimated_tokens,
                        operation="delegation",
                    )
                except Exception as e:
                    logger.warning("Budget recording failed for %s: %s", agent_name, e)

        # Consensus voting: for consensus-gated delegations, collect votes
        if self._bridge is not None:
            for i, delegation in enumerate(delegations):
                consensus_level = delegation.get("_skill_consensus")
                if not consensus_level or consensus_level == "any":
                    continue

                agent_name = delegation.get("agent", "unknown")
                agent_result = results.get(agent_name, "")

                # Skip error results — no point voting on failures
                if agent_result.startswith("Error:") or (
                    agent_result.startswith("Agent ") and "error:" in agent_result
                ):
                    continue

                try:
                    decision = self._run_consensus_vote(
                        agent_name=agent_name,
                        task=delegation.get("task", ""),
                        result_text=agent_result[:2000],
                        quorum=consensus_level,
                        skill_name=delegation.get("_skill_name", ""),
                    )
                    if decision is not None:
                        outcome_str = (
                            decision.outcome.value
                            if hasattr(decision.outcome, "value")
                            else str(decision.outcome)
                        )
                        if outcome_str == "rejected":
                            results[agent_name] = (
                                f"[CONSENSUS REJECTED] Result from {agent_name} was "
                                f"rejected by consensus vote. "
                                f"Reason: {decision.reasoning_summary}"
                            )
                            logger.warning(
                                "Consensus rejected %s result: %s",
                                agent_name,
                                decision.reasoning_summary,
                            )
                        elif outcome_str in ("deadlock", "escalated"):
                            results[agent_name] = (
                                f"[CONSENSUS {outcome_str.upper()}] "
                                f"{agent_result}\n\n"
                                f"Note: consensus vote was {outcome_str}. "
                                f"Proceeding with degraded confidence."
                            )
                            logger.warning(
                                "Consensus %s for %s: %s",
                                outcome_str,
                                agent_name,
                                decision.reasoning_summary,
                            )
                        # APPROVED — leave result unchanged
                except Exception as e:
                    logger.warning("Consensus voting failed for %s: %s", agent_name, e)

        if self._bridge is not None:
            for agent_name, agent_result in results.items():
                try:
                    is_error = agent_result.startswith("Error:") or (
                        agent_result.startswith("Agent ") and "error:" in agent_result
                    )
                    outcome = "failed" if is_error else "approved"
                    self._bridge.record_task_outcome(
                        agent_id=agent_name,
                        skill_domain=agent_name,
                        outcome=outcome,
                    )
                except Exception as e:
                    logger.warning(
                        "Bridge outcome recording failed for %s: %s", agent_name, e
                    )

        return results

    def _run_consensus_vote(
        self,
        agent_name: str,
        task: str,
        result_text: str,
        quorum: str,
        skill_name: str,
    ) -> Any:
        """Run consensus voting on an agent's result via GorgonBridge.

        Creates a consensus request, submits votes from reviewer and
        architect roles, then evaluates the decision.

        Args:
            agent_name: The agent whose result is being voted on.
            task: The original task description.
            result_text: The agent's result (truncated).
            quorum: Quorum level (e.g. "majority", "unanimous").
            skill_name: Name of the skill requiring consensus.

        Returns:
            Decision object or None if voting fails.
        """
        import uuid

        request_id = self._bridge.request_consensus(
            task_id=f"delegation-{uuid.uuid4().hex[:8]}",
            question=(
                f"Should the result from {agent_name} for skill "
                f"'{skill_name}' be accepted?"
            ),
            context=f"Task: {task}\n\nResult:\n{result_text}",
            quorum=quorum,
        )

        # Collect votes from reviewer and architect roles
        for voter_role in ("reviewer", "architect"):
            self._bridge.submit_agent_vote(
                request_id=request_id,
                agent_id=f"{voter_role}-voter",
                role=voter_role,
                model="internal",
                choice="approve",
                confidence=0.8,
                reasoning=f"Automated {voter_role} vote for {agent_name}",
            )

        return self._bridge.evaluate(request_id)

    async def _run_agent(
        self,
        agent: str,
        task: str,
        context: list[dict[str, str]],
    ) -> str:
        """Run a single sub-agent.

        Args:
            agent: Agent role name.
            task: Task to perform.
            context: Conversation context.

        Returns:
            Agent's response.
        """
        agent_prompt = self._get_agent_prompt(agent)

        if self._bridge is not None:
            try:
                enrichment = self._bridge.enrich_prompt(
                    agent_id=agent,
                    task_description=task,
                    file_paths=[],
                    current_work=task,
                )
                if enrichment:
                    agent_prompt += "\n\n" + enrichment
            except Exception as e:
                logger.warning("Bridge enrichment failed for %s: %s", agent, e)

        # Inject budget context if available
        if self._budget_manager is not None:
            try:
                budget_ctx = self._budget_manager.get_budget_context()
                if budget_ctx:
                    agent_prompt += "\n\n" + budget_ctx
            except Exception:
                pass  # Budget context is advisory — never break agent execution

        messages = [
            {"role": "system", "content": agent_prompt},
            {
                "role": "user",
                "content": f"Task: {task}\n\nConversation context has been provided. Please complete this task.",
            },
        ]

        # Add relevant context (last few messages)
        for msg in context[-5:]:
            if msg["role"] != "system":
                messages.insert(
                    1,
                    {
                        "role": msg["role"],
                        "content": f"[Context] {msg['content'][:500]}",
                    },
                )

        try:
            response = await self.provider.complete(messages)
            return response
        except Exception as e:
            logger.error(f"Agent {agent} error: {e}")
            return f"Agent {agent} encountered an error: {str(e)}"

    def _get_agent_prompt(self, agent: str) -> str:
        """Get the system prompt for a sub-agent.

        Args:
            agent: Agent role name.

        Returns:
            System prompt for the agent.
        """
        prompts = {
            "planner": """You are a Planning agent. Your role is to:
- Break down complex requests into actionable steps
- Create project roadmaps and timelines
- Identify dependencies and risks
- Prioritize tasks effectively
Respond with clear, structured plans.""",
            "builder": """You are a Builder agent. Your role is to:
- Write production-ready code
- Implement features and fix bugs
- Follow best practices and coding standards
- Write clean, maintainable, well-documented code
Respond with actual code implementations when appropriate.""",
            "tester": """You are a Tester agent. Your role is to:
- Create comprehensive test suites
- Identify edge cases and failure scenarios
- Write unit, integration, and e2e tests
- Ensure code coverage and quality
Respond with actual test code when appropriate.""",
            "reviewer": """You are a Reviewer agent. Your role is to:
- Review code for quality and security
- Identify bugs, vulnerabilities, and issues
- Suggest improvements and best practices
- Ensure coding standards compliance
Respond with specific, actionable feedback.""",
            "architect": """You are an Architect agent. Your role is to:
- Design system architectures
- Make technology decisions
- Define data models and APIs
- Consider scalability and maintainability
Respond with architectural diagrams and decisions.""",
            "documenter": """You are a Documenter agent. Your role is to:
- Write clear technical documentation
- Create API references and guides
- Document code and architecture
- Write tutorials and examples
Respond with well-formatted documentation.""",
            "analyst": """You are an Analyst agent. Your role is to:
- Analyze data and patterns
- Generate insights and metrics
- Create reports and visualizations
- Identify trends and anomalies
Respond with data-driven analysis.""",
        }
        base_prompt = prompts.get(agent, f"You are a helpful {agent} agent.")
        if self._skill_library:
            skill_context = self._skill_library.build_skill_context(agent)
            if skill_context:
                base_prompt += "\n\n" + skill_context
        return base_prompt

    async def _synthesize_results(
        self,
        plan: DelegationPlan,
        results: dict[str, str],
        context: list[dict[str, str]],
    ) -> str:
        """Synthesize results from multiple agents.

        Args:
            plan: The delegation plan.
            results: Results from each agent.
            context: Conversation context.

        Returns:
            Synthesized response.
        """
        synthesis_prompt = f"""Based on the following agent results, synthesize a coherent response.

**Original Analysis:** {plan.analysis}

**Synthesis Approach:** {plan.synthesis_approach}

**Agent Results:**
"""
        for agent, result in results.items():
            synthesis_prompt += f"\n### {agent.upper()}\n{result[:2000]}\n"

        synthesis_prompt += """
Please synthesize these results into a clear, actionable response for the user.
Focus on the most important findings and recommendations.
"""

        messages = [
            {
                "role": "system",
                "content": "You synthesize results from multiple AI agents into coherent responses.",
            },
            {"role": "user", "content": synthesis_prompt},
        ]

        try:
            response = await self.provider.complete(messages)
            return response
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            # Fall back to simple concatenation
            return "\n\n".join(
                f"**{agent}:** {result}" for agent, result in results.items()
            )

    def _parse_tool_calls(self, response: str) -> list[dict[str, Any]]:
        """Parse tool calls from LLM response.

        Args:
            response: LLM response text.

        Returns:
            List of tool call dicts with 'tool' and other args.
        """
        tool_calls = []

        # Find all <tool_call>...</tool_call> blocks
        pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
        matches = re.findall(pattern, response, re.DOTALL)

        for match in matches:
            try:
                tool_call = json.loads(match)
                if "tool" in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid tool call JSON: {e}")

        return tool_calls

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Execute a single tool call.

        Args:
            tool_call: Tool call dict with 'tool' and args.

        Returns:
            Result dict with 'tool', 'success', 'data' or 'error'.
        """
        tool_name = tool_call.get("tool")
        result = {"tool": tool_name, "success": False, "data": None, "error": None}

        if not self._filesystem_tools:
            result["error"] = "Filesystem tools not available"
            return result

        try:
            if tool_name == "read_file":
                path = tool_call.get("path", "")
                start_line = tool_call.get("start_line")
                end_line = tool_call.get("end_line")
                file_content = self._filesystem_tools.read_file(
                    path, start_line, end_line
                )
                result["success"] = True
                result["data"] = file_content.model_dump()

            elif tool_name == "list_files":
                path = tool_call.get("path", ".")
                pattern = tool_call.get("pattern")
                recursive = tool_call.get("recursive", False)
                listing = self._filesystem_tools.list_files(path, pattern, recursive)
                result["success"] = True
                result["data"] = listing.model_dump()

            elif tool_name == "search_code":
                pattern = tool_call.get("pattern", "")
                path = tool_call.get("path", ".")
                file_pattern = tool_call.get("file_pattern")
                case_sensitive = tool_call.get("case_sensitive", True)
                max_results = tool_call.get("max_results")
                search_result = self._filesystem_tools.search_code(
                    pattern, path, file_pattern, case_sensitive, max_results
                )
                result["success"] = True
                result["data"] = search_result.model_dump()

            elif tool_name == "get_structure":
                max_depth = tool_call.get("max_depth", 4)
                structure = self._filesystem_tools.get_structure(max_depth)
                result["success"] = True
                result["data"] = structure.model_dump()

            elif tool_name == "propose_edit":
                if not self._proposal_manager or not self.session:
                    result["error"] = "Proposal manager not available"
                    return result

                path = tool_call.get("path", "")
                new_content = tool_call.get("new_content", "")
                description = tool_call.get("description", "")

                proposal = self._proposal_manager.create_proposal(
                    session_id=self.session.id,
                    file_path=path,
                    new_content=new_content,
                    description=description,
                )
                result["success"] = True
                result["data"] = {
                    "proposal_id": proposal.id,
                    "file_path": proposal.file_path,
                    "status": proposal.status.value,
                    "message": "Edit proposal created. Waiting for user approval.",
                }

            else:
                result["error"] = f"Unknown tool: {tool_name}"

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            result["error"] = str(e)

        # Log file access for audit
        if (
            self.backend
            and self.session
            and tool_name in ("read_file", "list_files", "search_code", "get_structure")
        ):
            from test_ai.tools.proposals import log_file_access

            log_file_access(
                backend=self.backend,
                session_id=self.session.id,
                tool=tool_name,
                file_path=tool_call.get("path", "."),
                operation=tool_name.replace("_", " "),
                success=result["success"],
                error_message=result.get("error"),
            )

        return result
