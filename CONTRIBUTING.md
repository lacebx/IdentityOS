# Contributing to IdentityOS

Thank you for your interest in contributing to IdentityOS — the Open Identity Specification for AI. This project is an open standard, and contributions of all kinds are welcome, from spec proposals to bug fixes to documentation improvements.

## Ways to Contribute

- **Specification (`spec/`):** Propose new modules, schema changes, or clarifications to the Open Identity Specification.
- **Core modules (`core/`):** Improve existing subsystems (identity, timeline, experience, knowledge, skills, capabilities, permissions, motivations, policies, relationships, health, evaluation).
- **Runtime (`runtime/`):** Enhance the reference runtime implementation (orchestrator, persistence, event bus, API).
- **Adapters (`adapters/`):** Add or improve support for LLM providers (OpenAI, Anthropic, Ollama, etc.).
- **CLI / SDK (`cli/`, `sdk/`):** Improve developer tooling and the Python SDK.
- **Documentation:** Improve examples, tutorials, and guides in `docs/`.
- **Tests:** Add or improve test coverage under `tests/`.

## Getting Started

1. **Fork** the repository.
2. **Clone** your fork locally:
   ```
   git clone https://github.com/<your-username>/IdentityOS.git
   cd IdentityOS
   ```
3. **Install dependencies**:
   ```
   pip install -r runtime/requirements.txt
   ```
4. **Create a feature branch**:
   ```
   git checkout -b feature/amazing-feature
   ```

## Making Changes

- Keep changes focused and scoped to a single concern per pull request.
- Follow existing code style and module boundaries — each core module should remain self-contained with clean interfaces.
- If you change the specification (`spec/identity.schema.json` or `spec/SPEC.md`), ensure backward compatibility is considered and document the rationale.
- Add or update tests for any behavioral change.
- Update relevant documentation (README, module docstrings, `docs/`) alongside code changes.

## Commit and Pull Request Guidelines

1. Write clear, descriptive commit messages (e.g. `fix: correct snapshot rollback ordering`).
2. Push your branch to your fork:
   ```
   git push origin feature/amazing-feature
   ```
3. Open a Pull Request against `main` with:
   - A clear description of what changed and why
   - Reference to any related issue
   - Notes on testing performed
4. Be responsive to review feedback. Maintainers may request changes before merging.

## Reporting Bugs and Requesting Features

Please use the issue templates provided when opening a new issue. Include as much detail as possible (steps to reproduce, expected vs actual behavior, environment).

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

If you have questions about contributing, open a discussion or issue, and a maintainer will follow up.

Thank you for helping build the infrastructure for persistent AI identities.
