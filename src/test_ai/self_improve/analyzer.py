"""Codebase analyzer for identifying improvement opportunities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from test_ai.agents.provider_wrapper import AgentProvider

logger = logging.getLogger(__name__)


class ImprovementCategory(str, Enum):
    """Categories of code improvements."""

    REFACTORING = "refactoring"
    BUG_FIXES = "bug_fixes"
    DOCUMENTATION = "documentation"
    TEST_COVERAGE = "test_coverage"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"


@dataclass
class ImprovementSuggestion:
    """A suggested improvement to the codebase."""

    id: str
    category: ImprovementCategory
    title: str
    description: str
    affected_files: list[str]
    priority: int = 3  # 1 (highest) to 5 (lowest)
    estimated_lines: int = 0
    reasoning: str = ""
    implementation_hints: str = ""


@dataclass
class AnalysisResult:
    """Result of codebase analysis."""

    suggestions: list[ImprovementSuggestion] = field(default_factory=list)
    files_analyzed: int = 0
    issues_found: int = 0
    analysis_summary: str = ""


class CodebaseAnalyzer:
    """Analyzes the Gorgon codebase for improvement opportunities."""

    def __init__(
        self,
        provider: "AgentProvider | None" = None,
        codebase_path: str | Path = ".",
    ):
        """Initialize the analyzer.

        Args:
            provider: Optional AI provider for intelligent analysis.
            codebase_path: Path to codebase root.
        """
        self.provider = provider
        self.codebase_path = Path(codebase_path)

    def analyze(
        self,
        categories: list[ImprovementCategory] | None = None,
        focus_paths: list[str] | None = None,
    ) -> AnalysisResult:
        """Analyze the codebase for improvements.

        Args:
            categories: Categories to focus on. None = all.
            focus_paths: Specific paths to analyze. None = all.

        Returns:
            Analysis result with suggestions.
        """
        suggestions = []
        files_analyzed = 0
        issues_found = 0

        # Get Python files to analyze
        if focus_paths:
            files = []
            for pattern in focus_paths:
                files.extend(self.codebase_path.glob(pattern))
        else:
            files = list(self.codebase_path.glob("src/**/*.py"))

        for file_path in files:
            if self._should_skip_file(file_path):
                continue

            files_analyzed += 1
            file_suggestions = self._analyze_file(file_path, categories)
            suggestions.extend(file_suggestions)
            issues_found += len(file_suggestions)

        # Prioritize suggestions
        suggestions.sort(key=lambda s: (s.priority, -s.estimated_lines))

        return AnalysisResult(
            suggestions=suggestions,
            files_analyzed=files_analyzed,
            issues_found=issues_found,
            analysis_summary=f"Analyzed {files_analyzed} files, found {issues_found} improvement opportunities.",
        )

    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped.

        Args:
            file_path: Path to check.

        Returns:
            True if should skip.
        """
        skip_patterns = [
            "__pycache__",
            ".git",
            ".venv",
            "node_modules",
            "self_improve",  # Don't analyze the self-improve module
        ]
        return any(pattern in str(file_path) for pattern in skip_patterns)

    def _analyze_file(
        self,
        file_path: Path,
        categories: list[ImprovementCategory] | None,
    ) -> list[ImprovementSuggestion]:
        """Analyze a single file.

        Args:
            file_path: Path to file.
            categories: Categories to check.

        Returns:
            List of suggestions for this file.
        """
        suggestions = []
        relative_path = str(file_path.relative_to(self.codebase_path))

        try:
            content = file_path.read_text()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return suggestions

        # Run static checks
        if not categories or ImprovementCategory.CODE_QUALITY in categories:
            suggestions.extend(self._check_code_quality(relative_path, content))

        if not categories or ImprovementCategory.DOCUMENTATION in categories:
            suggestions.extend(self._check_documentation(relative_path, content))

        if not categories or ImprovementCategory.TEST_COVERAGE in categories:
            suggestions.extend(self._check_test_coverage(relative_path, content))

        return suggestions

    def _check_code_quality(
        self,
        file_path: str,
        content: str,
    ) -> list[ImprovementSuggestion]:
        """Check for code quality issues.

        Args:
            file_path: Relative file path.
            content: File content.

        Returns:
            List of suggestions.
        """
        suggestions = []
        lines = content.split("\n")

        # Check for long functions
        function_pattern = re.compile(r"^(\s*)def\s+(\w+)\s*\(")
        current_function = None
        function_start = 0

        for i, line in enumerate(lines):
            match = function_pattern.match(line)
            if match:
                # Check previous function length
                if current_function and i - function_start > 50:
                    suggestions.append(
                        ImprovementSuggestion(
                            id=f"long_function_{file_path}_{current_function}",
                            category=ImprovementCategory.REFACTORING,
                            title=f"Long function: {current_function}",
                            description=f"Function `{current_function}` has {i - function_start} lines. Consider breaking it into smaller functions.",
                            affected_files=[file_path],
                            priority=3,
                            estimated_lines=i - function_start,
                        )
                    )

                current_function = match.group(2)
                function_start = i
                _ = len(match.group(1))  # Reserved for future indentation tracking

        # Check for TODO comments
        todo_pattern = re.compile(r"#\s*TODO[:\s](.+)", re.IGNORECASE)
        for i, line in enumerate(lines):
            match = todo_pattern.search(line)
            if match:
                suggestions.append(
                    ImprovementSuggestion(
                        id=f"todo_{file_path}_{i}",
                        category=ImprovementCategory.BUG_FIXES,
                        title=f"TODO in {file_path}:{i + 1}",
                        description=f"Unresolved TODO: {match.group(1).strip()}",
                        affected_files=[file_path],
                        priority=4,
                        estimated_lines=5,
                    )
                )

        # Check for bare except
        if "except:" in content and "except Exception" not in content:
            suggestions.append(
                ImprovementSuggestion(
                    id=f"bare_except_{file_path}",
                    category=ImprovementCategory.CODE_QUALITY,
                    title=f"Bare except in {file_path}",
                    description="Found bare `except:` clause. Consider catching specific exceptions.",
                    affected_files=[file_path],
                    priority=2,
                    estimated_lines=3,
                )
            )

        return suggestions

    def _check_documentation(
        self,
        file_path: str,
        content: str,
    ) -> list[ImprovementSuggestion]:
        """Check for documentation issues.

        Args:
            file_path: Relative file path.
            content: File content.

        Returns:
            List of suggestions.
        """
        suggestions = []

        # Check for missing module docstring
        if not content.strip().startswith('"""') and not content.strip().startswith(
            "'''"
        ):
            suggestions.append(
                ImprovementSuggestion(
                    id=f"missing_module_docstring_{file_path}",
                    category=ImprovementCategory.DOCUMENTATION,
                    title=f"Missing module docstring: {file_path}",
                    description="Module is missing a docstring. Add a description of the module's purpose.",
                    affected_files=[file_path],
                    priority=4,
                    estimated_lines=5,
                )
            )

        # Check for public functions without docstrings
        function_pattern = re.compile(
            r"^def\s+(\w+)\s*\([^)]*\)\s*(?:->.*)?:", re.MULTILINE
        )
        for match in function_pattern.finditer(content):
            func_name = match.group(1)
            if func_name.startswith("_"):
                continue  # Skip private functions

            # Check if next non-empty line is a docstring
            start_pos = match.end()
            remaining = content[start_pos : start_pos + 200]
            if not (
                remaining.strip().startswith('"""')
                or remaining.strip().startswith("'''")
            ):
                suggestions.append(
                    ImprovementSuggestion(
                        id=f"missing_docstring_{file_path}_{func_name}",
                        category=ImprovementCategory.DOCUMENTATION,
                        title=f"Missing docstring: {func_name}",
                        description=f"Public function `{func_name}` is missing a docstring.",
                        affected_files=[file_path],
                        priority=4,
                        estimated_lines=5,
                    )
                )

        return suggestions

    def _check_test_coverage(
        self,
        file_path: str,
        content: str,
    ) -> list[ImprovementSuggestion]:
        """Check for test coverage issues.

        Args:
            file_path: Relative file path.
            content: File content.

        Returns:
            List of suggestions.
        """
        suggestions = []

        # Skip test files themselves
        if "test_" in file_path or "_test.py" in file_path:
            return suggestions

        # Check if corresponding test file exists
        if file_path.startswith("src/"):
            # Convert src/test_ai/foo.py to tests/test_foo.py
            module_name = Path(file_path).stem
            potential_test = f"tests/test_{module_name}.py"
            test_path = self.codebase_path / potential_test

            if not test_path.exists():
                # Count public functions that need tests
                function_pattern = re.compile(r"^def\s+([a-z]\w*)\s*\(", re.MULTILINE)
                public_functions = [
                    m.group(1)
                    for m in function_pattern.finditer(content)
                    if not m.group(1).startswith("_")
                ]

                if public_functions:
                    suggestions.append(
                        ImprovementSuggestion(
                            id=f"missing_tests_{file_path}",
                            category=ImprovementCategory.TEST_COVERAGE,
                            title=f"Missing tests for {file_path}",
                            description=f"No test file found for {file_path}. {len(public_functions)} public functions need tests.",
                            affected_files=[file_path, potential_test],
                            priority=3,
                            estimated_lines=len(public_functions) * 20,
                            implementation_hints=f"Create {potential_test} with tests for: {', '.join(public_functions[:5])}",
                        )
                    )

        return suggestions

    async def analyze_with_ai(
        self,
        focus_file: str | None = None,
    ) -> AnalysisResult:
        """Use AI to analyze the codebase for improvements.

        Args:
            focus_file: Optional specific file to analyze.

        Returns:
            Analysis result with AI-generated suggestions.
        """
        if not self.provider:
            logger.warning("No AI provider available, using static analysis only")
            return self.analyze()

        # First do static analysis
        static_result = self.analyze()

        # TODO: Enhance with AI analysis
        # This would send code to the AI for deeper analysis
        # For now, just return static analysis

        return static_result
