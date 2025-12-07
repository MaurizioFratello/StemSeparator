# Contributing to Stem Separator

Thank you for your interest in contributing to Stem Separator! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/StemSeparator.git
   cd StemSeparator
   ```
3. **Add the upstream repository**:
   ```bash
   git remote add upstream https://github.com/MaurizioFratello/StemSeparator.git
   ```

## Development Setup

### Prerequisites

- macOS 10.15 (Catalina) or newer
- Python 3.9+ (3.11 recommended)
- Conda (recommended) or pip
- Xcode Command Line Tools (for macOS features)

### Installation

1. **Create a conda environment**:
   ```bash
   conda env create -f environment.yml
   conda activate stem-separator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

### Development Tools

We recommend using:
- **Black** for code formatting
- **Flake8** for linting
- **pytest** for testing

Install development tools:
```bash
pip install black flake8 pytest pytest-cov
```

## How to Contribute

### Types of Contributions

- **Bug fixes**: Fix existing issues
- **Features**: Add new functionality
- **Documentation**: Improve docs, add examples
- **Tests**: Increase test coverage
- **Performance**: Optimize existing code
- **UI/UX**: Improve user interface and experience

### Workflow

1. **Create a new branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

   Branch naming conventions:
   - `feature/` - New features
   - `fix/` - Bug fixes
   - `docs/` - Documentation changes
   - `refactor/` - Code refactoring
   - `test/` - Test additions/changes

2. **Make your changes**:
   - Write clean, readable code
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

   Commit message format:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `refactor:` - Code refactoring
   - `test:` - Test changes
   - `chore:` - Maintenance tasks

4. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request** on GitHub

## Coding Standards

### Python Style

- Follow **PEP 8** guidelines
- Use **type hints** where appropriate
- Write **docstrings** for all public functions/classes
- Maximum line length: **100 characters**

### Code Formatting

Format your code with Black:
```bash
black .
```

Check for style issues:
```bash
flake8 .
```

### Project Structure

```
StemSeparator/
├── core/           # Business logic
├── ui/             # GUI components
├── utils/          # Utilities
├── tests/          # Tests
├── docs/           # Documentation
└── resources/      # Resources (models, icons, translations)
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_separator.py

# Run GUI tests
pytest tests/ui/
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test names
- Mock external dependencies
- Aim for >80% code coverage

Example test:
```python
def test_separator_initialization():
    """Test that separator initializes correctly"""
    separator = Separator()
    assert separator is not None
    assert separator.device_manager is not None
```

## Pull Request Process

1. **Ensure all tests pass**:
   ```bash
   pytest
   ```

2. **Update documentation** if needed

3. **Create a Pull Request** with:
   - Clear title and description
   - Reference related issues
   - List of changes
   - Screenshots (for UI changes)

4. **Address review feedback** promptly

5. **Squash commits** if requested

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] Commit messages are clear and descriptive

## Reporting Bugs

### Before Reporting

1. **Check existing issues** to avoid duplicates
2. **Test with the latest version**
3. **Collect relevant information**:
   - OS version
   - Python version
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages/logs

### Bug Report Template

```markdown
**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., macOS 14.0]
- Python: [e.g., 3.11.5]
- Version: [e.g., 1.0.0]

**Logs**
Attach relevant logs from `logs/app.log`

**Additional context**
Any other relevant information.
```

## Feature Requests

We welcome feature suggestions! Please:

1. **Check existing issues** first
2. **Provide detailed description**:
   - Use case
   - Expected behavior
   - Why it's useful
   - Potential implementation approach

## Questions?

- Check the [documentation](docs/)
- Review [existing issues](https://github.com/MaurizioFratello/StemSeparator/issues)
- Open a new issue for questions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

---

**Thank you for contributing to Stem Separator!** 🎵
