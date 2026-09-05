# Coding Standards

## Java (Spring Boot)
- **Classes**: `PascalCase`
- **Methods/Variables**: `camelCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Organization**: Clear package organization (e.g., `controller`, `service`, `config`, `repository`).
- **Dependency Injection**: Use constructor-based dependency injection. Avoid field injection (`@Autowired`).
- **Controllers**: Keep controllers thin. Avoid unnecessary business logic in controllers; delegate to services.

## Python (FastAPI RAG Service)
- **Functions/Variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_CASE`
- **Typing**: Use Type hints (`: str`, `: int`, `-> dict`) wherever possible.
- **Organization**: Clear module responsibilities (`api`, `core`, `ingestion`, `retrieval`, `llm`).
- **Functions**: Avoid large monolithic functions; break them down into testable units.

## General
- **Secrets**: NEVER commit secrets, API keys, or passwords.
- **Configuration**: Use environment variables for all configuration values. Provide placeholder `.env.example` or `application-dev.yml` files.
- **Naming**: Use meaningful, descriptive names for variables, methods, and classes.
- **Validation**: Validate all external inputs at the boundaries (Controllers/API layer).
- **Testing**: Write automated tests for important business logic and edge cases.
- **Documentation**: Document architectural decisions via ADRs (Architecture Decision Records).
