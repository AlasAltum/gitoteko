# Contributing to Gitoteko

Thank you for your interest in contributing!

## Development Setup

1. **Clone and Setup**
   ```bash
   git clone https://github.com/AlasAltum/gitoteko.git
   cd gitoteko
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Install Dev Dependencies**
   We use `ruff` for linting and formatting, and `mypy` for static analysis.
   ```bash
   pip install ruff mypy
   ```

## Workflow

1. **Create a Branch**: `git checkout -b feature/my-cool-feature`
2. **Implement Changes**: Follow the project's hexagonal architecture.
   - Core logic in `src/git_workspace_tool/application`
   - External adapters in `src/git_workspace_tool/adapters`
   - New rules in `src/git_workspace_tool/rules` (See [Adding New Rules](docs/adding_new_rules.md))
3. **Lint & Type Check**:
   ```bash
   ruff check src/
   mypy src/
   ```
4. **Submit PR**: Push your branch and open a Pull Request.

## Coding Standards

- **Hexagonal Architecture**: Keep the core domain pure. Access external systems (Git, Filesystem, Sonar) only via Ports/Adapters.
- **Type Hints**: All code must be fully type-hinted.
- **No External Runtime Deps**: The core tool should remain dependency-free (standard library only) to make it easy to run anywhere.
