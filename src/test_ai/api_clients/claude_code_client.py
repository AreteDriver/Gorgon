"""Claude Code API client wrapper with API and CLI modes."""

import asyncio
import json
import subprocess
from typing import Any, Dict, Optional

from test_ai.config import get_settings
from test_ai.utils.retry import with_retry, async_with_retry
from test_ai.api_clients.resilience import resilient_call, resilient_call_async

try:
    import anthropic
except ImportError:
    anthropic = None


# Default role prompts - can be overridden via config/agent_prompts.json
DEFAULT_ROLE_PROMPTS = {
    "planner": """You are a strategic planning agent. Break down the requested feature into:
1. Clear, actionable implementation steps
2. Required files and their purposes
3. Dependencies and prerequisites
4. Success criteria

Output a structured markdown plan.""",
    "builder": """You are a code implementation agent. Using the provided plan:
1. Write clean, production-ready code
2. Follow best practices and patterns
3. Include inline documentation
4. Ensure code is testable

Focus on implementation quality and maintainability.""",
    "tester": """You are a testing specialist agent. For the implemented code:
1. Write comprehensive unit tests
2. Include edge cases and error conditions
3. Ensure good test coverage
4. Write clear test descriptions

Use appropriate testing frameworks.""",
    "reviewer": """You are a code review agent. Analyze the implementation for:
1. Code quality and best practices
2. Potential bugs or issues
3. Performance considerations
4. Security concerns
5. Suggestions for improvement

Provide constructive, actionable feedback.""",
    "model_builder": """You are a 3D modeling and game development specialist agent. You help with:
1. Creating scripts, shaders, and materials for Unity, Blender, Unreal, Godot, and Three.js
2. Generating procedural geometry and mesh manipulation code
3. Setting up scenes, lighting, and camera configurations
4. Writing animation controllers and state machines
5. Optimizing 3D assets for performance (LOD, batching, draw call reduction)
6. Creating prefabs, blueprints, and reusable components

When generating code:
- Use platform-specific best practices (C# for Unity, Python for Blender, C++/Blueprints for Unreal)
- Include comments explaining 3D-specific concepts
- Consider performance implications (polygon count, texture memory, shader complexity)
- Provide step-by-step instructions for tasks requiring manual work in 3D tools

For non-code tasks, provide detailed instructions that can be followed in the target 3D application.""",
}


class ClaudeCodeClient:
    """Wrapper for Claude Code with both API and CLI modes."""

    def __init__(self):
        settings = get_settings()
        self.mode = settings.claude_mode
        self.api_key = settings.anthropic_api_key
        self.cli_path = settings.claude_cli_path
        self.client = None
        self.role_prompts = self._load_role_prompts(settings)

        if self.mode == "api" and self.api_key and anthropic:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        else:
            self.async_client = None

    def _load_role_prompts(self, settings) -> Dict[str, str]:
        """Load role prompts from config file or use defaults."""
        prompts_file = settings.base_dir / "config" / "agent_prompts.json"
        if prompts_file.exists():
            try:
                with open(prompts_file) as f:
                    data = json.load(f)
                return {
                    role: info.get("system_prompt", DEFAULT_ROLE_PROMPTS.get(role, ""))
                    for role, info in data.items()
                }
            except Exception:
                pass
        return DEFAULT_ROLE_PROMPTS.copy()

    def is_configured(self) -> bool:
        """Check if Claude Code client is configured."""
        if self.mode == "api":
            return self.client is not None
        else:
            # CLI mode - check if claude command exists
            try:
                result = subprocess.run(
                    [self.cli_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.returncode == 0
            except Exception:
                return False

    def execute_agent(
        self,
        role: str,
        task: str,
        context: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Execute a specialized agent with role-specific prompt.

        Args:
            role: Agent role (planner, builder, tester, reviewer)
            task: The task description
            context: Optional context from previous steps
            model: Claude model to use
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'success', 'output', and optionally 'error'
        """
        if not self.is_configured():
            return {"success": False, "error": "Claude Code client not configured"}

        system_prompt = self.role_prompts.get(role, "")
        if not system_prompt:
            return {"success": False, "error": f"Unknown role: {role}"}

        user_prompt = f"Task: {task}"
        if context:
            user_prompt += f"\n\nContext:\n{context}"

        try:
            if self.mode == "api":
                output = self._execute_via_api(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    max_tokens=max_tokens,
                )
            else:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                output = self._execute_via_cli(prompt=full_prompt)

            return {"success": True, "output": output, "role": role}
        except Exception as e:
            return {"success": False, "error": str(e), "role": role}

    def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Generate a completion without role-specific prompts.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Claude model to use
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'success', 'output', and optionally 'error'
        """
        if not self.is_configured():
            return {"success": False, "error": "Claude Code client not configured"}

        try:
            if self.mode == "api":
                output = self._execute_via_api(
                    system_prompt=system_prompt or "You are a helpful assistant.",
                    user_prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                )
            else:
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                output = self._execute_via_cli(prompt=full_prompt)

            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_cli_command(
        self,
        prompt: str,
        working_dir: Optional[str] = None,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Execute Claude CLI with a custom prompt.

        Args:
            prompt: The prompt to send to Claude CLI
            working_dir: Optional working directory for the CLI
            timeout: Command timeout in seconds

        Returns:
            Dict with 'success', 'output', and optionally 'error'
        """
        try:
            output = self._execute_via_cli(
                prompt=prompt,
                working_dir=working_dir,
                timeout=timeout,
            )
            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_via_api(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> str:
        """Execute via Anthropic API."""
        if not self.client:
            raise RuntimeError("Anthropic client not initialized")

        return self._call_anthropic_api(system_prompt, user_prompt, model, max_tokens)

    @resilient_call("anthropic")
    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _call_anthropic_api(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
    ) -> str:
        """Make the actual Anthropic API call with retry logic."""
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    def _execute_via_cli(
        self,
        prompt: str,
        working_dir: Optional[str] = None,
        timeout: int = 300,
    ) -> str:
        """Execute via Claude CLI subprocess."""
        cmd = [self.cli_path, "-p", prompt, "--no-input"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI error: {result.stderr}")

        return result.stdout

    async def execute_agent_async(
        self,
        role: str,
        task: str,
        context: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Async version of execute_agent().

        Execute a specialized agent with role-specific prompt asynchronously.

        Args:
            role: Agent role (planner, builder, tester, reviewer)
            task: The task description
            context: Optional context from previous steps
            model: Claude model to use
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'success', 'output', and optionally 'error'
        """
        if not self.is_configured():
            return {"success": False, "error": "Claude Code client not configured"}

        system_prompt = self.role_prompts.get(role, "")
        if not system_prompt:
            return {"success": False, "error": f"Unknown role: {role}"}

        user_prompt = f"Task: {task}"
        if context:
            user_prompt += f"\n\nContext:\n{context}"

        try:
            if self.mode == "api":
                output = await self._execute_via_api_async(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    max_tokens=max_tokens,
                )
            else:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                output = await self._execute_via_cli_async(prompt=full_prompt)

            return {"success": True, "output": output, "role": role}
        except Exception as e:
            return {"success": False, "error": str(e), "role": role}

    async def generate_completion_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Async version of generate_completion().

        Generate a completion without role-specific prompts asynchronously.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Claude model to use
            max_tokens: Maximum tokens in response

        Returns:
            Dict with 'success', 'output', and optionally 'error'
        """
        if not self.is_configured():
            return {"success": False, "error": "Claude Code client not configured"}

        try:
            if self.mode == "api":
                output = await self._execute_via_api_async(
                    system_prompt=system_prompt or "You are a helpful assistant.",
                    user_prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                )
            else:
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                output = await self._execute_via_cli_async(prompt=full_prompt)

            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_via_api_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> str:
        """Execute via Anthropic API asynchronously."""
        if not self.async_client:
            raise RuntimeError("Anthropic async client not initialized")

        return await self._call_anthropic_api_async(
            system_prompt, user_prompt, model, max_tokens
        )

    @resilient_call_async("anthropic")
    @async_with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def _call_anthropic_api_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
    ) -> str:
        """Make the actual Anthropic API call asynchronously with retry logic."""
        response = await self.async_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    async def _execute_via_cli_async(
        self,
        prompt: str,
        working_dir: Optional[str] = None,
        timeout: int = 300,
    ) -> str:
        """Execute via Claude CLI subprocess asynchronously."""
        cmd = [self.cli_path, "-p", prompt, "--no-input"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"Claude CLI timed out after {timeout} seconds")

        if process.returncode != 0:
            raise RuntimeError(f"Claude CLI error: {stderr.decode()}")

        return stdout.decode()
