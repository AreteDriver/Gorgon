# Contributing to Gorgon

Thank you for your interest in contributing to Gorgon! This document provides guidelines and instructions for contributing to the project.

## 🌟 Ways to Contribute

- **Report Bugs**: Submit detailed bug reports via GitHub Issues
- **Suggest Features**: Propose new features or improvements
- **Submit Code**: Fix bugs, add features, or improve documentation
- **Improve Documentation**: Help make our docs clearer and more comprehensive
- **Share Workflows**: Contribute example workflows for the community

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/Gorgon.git
cd Gorgon

# Add upstream remote
git remote add upstream https://github.com/AreteDriver/Gorgon.git
```

### 2. Set Up Development Environment

```bash
# Install dependencies with Poetry (recommended)
poetry install

# Or with pip
pip install -r requirements.txt

# Install development dependencies
pip install pytest black ruff mypy

# Set up pre-commit hooks (optional)
pre-commit install
```

### 3. Create a Branch

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
```

## 📝 Development Guidelines

### Code Style

We follow Python best practices and PEP 8 guidelines:

- **Formatter**: Black (line length: 88)
- **Linter**: Ruff
- **Type Hints**: Use type hints for all functions
- **Docstrings**: Google-style docstrings for all public APIs

```bash
# Format code
black .

# Lint code
ruff check .

# Type check
mypy src/
```

### Code Structure

- **Modular Design**: Keep modules focused and independent
- **Type Safety**: Use Pydantic models for data validation
- **Error Handling**: Use specific exceptions with clear messages
- **Logging**: Use the built-in logging system
- **Documentation**: Update docstrings and README as needed

### Example Code Pattern

```python
"""Module docstring explaining purpose."""

from typing import Optional
from pydantic import BaseModel


class MyModel(BaseModel):
    """Model docstring."""
    
    field: str
    optional_field: Optional[int] = None


def my_function(param: str) -> MyModel:
    """
    Function docstring explaining what it does.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When parameter is invalid
    """
    if not param:
        raise ValueError("Parameter cannot be empty")
    
    return MyModel(field=param)
```

## 🧪 Testing

### Writing Tests

- **Location**: Place tests in `tests/` directory
- **Naming**: Test files should match `test_*.py` pattern
- **Coverage**: Aim for >80% code coverage
- **Fixtures**: Use pytest fixtures for common setup

```python
# tests/test_my_feature.py
import pytest
from test_ai.my_module import my_function


def test_my_function_success():
    """Test successful execution."""
    result = my_function("test")
    assert result.field == "test"


def test_my_function_validation():
    """Test validation error."""
    with pytest.raises(ValueError):
        my_function("")
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/test_ai --cov-report=html

# Run specific test file
pytest tests/test_my_feature.py

# Run with verbose output
pytest -v
```

## 📚 Documentation

### Updating Documentation

When adding features or making changes:

1. **Update docstrings** in the code
2. **Update README.md** if adding user-facing features
3. **Update QUICKSTART.md** for getting started changes
4. **Update IMPLEMENTATION.md** for architectural changes
5. **Add examples** in `examples/` directory

### Documentation Style

- **Clear and Concise**: Use simple language
- **Code Examples**: Include working examples
- **Screenshots**: Add screenshots for UI changes
- **Links**: Link to related documentation

## 🔄 Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commits are clear and descriptive
- [ ] Branch is up to date with main

### Submitting PR

1. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Go to GitHub and create a PR from your fork
   - Use a clear, descriptive title
   - Fill out the PR template completely
   - Link related issues

3. **PR Title Format**
   - `feat: Add new feature`
   - `fix: Fix bug in component`
   - `docs: Update documentation`
   - `refactor: Improve code structure`
   - `test: Add tests for feature`

4. **PR Description Should Include**
   - What changes were made
   - Why the changes were necessary
   - How to test the changes
   - Screenshots (for UI changes)
   - Breaking changes (if any)

### Review Process

- Maintainers will review your PR
- Address feedback in new commits
- Once approved, maintainers will merge
- Delete your branch after merge

## 🐛 Bug Reports

### Before Reporting

- Search existing issues to avoid duplicates
- Test on the latest version
- Gather relevant information

### Bug Report Template

```markdown
## Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Expected vs actual behavior

## Environment
- OS: [e.g., macOS 14.0]
- Python Version: [e.g., 3.12]
- Gorgon Version: [e.g., 0.1.0]

## Additional Context
- Error messages
- Logs
- Screenshots
```

## 💡 Feature Requests

### Feature Request Template

```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed?

## Proposed Solution
How should this feature work?

## Alternatives Considered
Other approaches you've considered

## Additional Context
Examples, mockups, references
```

## 🔐 Security Issues

**Do not report security vulnerabilities in public issues.**

Email security concerns to: aretedriver@gmail.com

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## 📋 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors.

### Our Standards

- **Be Respectful**: Treat everyone with respect
- **Be Collaborative**: Work together constructively
- **Be Patient**: Help newcomers learn
- **Be Professional**: Focus on what's best for the project
- **Be Open**: Welcome diverse perspectives

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal attacks
- Publishing private information
- Unprofessional conduct

### Enforcement

Violations may result in temporary or permanent ban from the project.

## 📞 Getting Help

- **Documentation**: Check README.md and QUICKSTART.md
- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Search existing issues
- **Email**: aretedriver@gmail.com

## 🎯 Development Workflow

### Typical Development Flow

1. **Pick an Issue**: Choose from open issues or create one
2. **Discuss**: Comment on the issue with your approach
3. **Develop**: Write code following guidelines
4. **Test**: Ensure all tests pass
5. **Document**: Update relevant documentation
6. **Submit**: Create a pull request
7. **Review**: Address feedback
8. **Merge**: Maintainers merge approved PRs

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code improvements
- `test/description` - Test additions

## 🏅 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Credited in release notes
- Thanked in the community

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to Gorgon! 🎼**
