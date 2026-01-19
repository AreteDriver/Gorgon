"""OpenAI API client wrapper."""

from typing import Optional, List, Dict
from openai import OpenAI

from test_ai.config import get_settings
from test_ai.utils.retry import with_retry


class OpenAIClient:
    """Wrapper for OpenAI API."""

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate_completion(
        self,
        prompt: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a completion from a prompt."""
        messages: List[Dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return self._call_api(model, messages, temperature, max_tokens)

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    def _call_api(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """Make the actual API call with retry logic."""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def summarize_text(self, text: str, max_length: int = 500) -> str:
        """Summarize text using GPT."""
        prompt = f"Please provide a concise summary (max {max_length} words) of the following text:\n\n{text}"
        return self.generate_completion(
            prompt=prompt,
            system_prompt="You are a helpful assistant that creates clear, concise summaries.",
        )

    def generate_sop(self, task_description: str) -> str:
        """Generate a Standard Operating Procedure."""
        prompt = f"Create a detailed Standard Operating Procedure (SOP) for: {task_description}"
        return self.generate_completion(
            prompt=prompt,
            system_prompt="You are an expert at creating clear, detailed Standard Operating Procedures.",
        )
