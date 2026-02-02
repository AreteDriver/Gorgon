"""Supervisor agent for autonomous multi-agent orchestration.

The Supervisor analyzes user requests and autonomously delegates
to specialized agents: Planner, Builder, Tester, Reviewer, Architect,
and Documenter.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncGenerator

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from test_ai.providers.base import BaseProvider
    from test_ai.chat.models import ChatMessage, ChatMode

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


class SupervisorAgent:
    """Orchestrates multi-agent workflows through intelligent delegation."""

    def __init__(
        self,
        provider: "BaseProvider",
        mode: "ChatMode | None" = None,
    ):
        """Initialize the Supervisor agent.

        Args:
            provider: LLM provider for generating responses.
            mode: Operating mode (assistant or self_improve).
        """
        self.provider = provider
        self.mode = mode
        self._active_delegations: list[AgentDelegation] = []

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on mode."""
        prompt = SUPERVISOR_SYSTEM_PROMPT
        if self.mode and self.mode.value == "self_improve":
            prompt += SELF_IMPROVE_PROMPT_ADDITION
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

        # Get initial response from LLM
        full_response = ""
        async for chunk in self._stream_response(context):
            full_response += chunk
            yield {"type": "text", "content": chunk, "agent": "supervisor"}

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
            import re

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

        return results

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
        return prompts.get(agent, f"You are a helpful {agent} agent.")

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
