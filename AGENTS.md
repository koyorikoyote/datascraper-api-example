# Project Agents.md Guide for OpenAI Codex

This **Agents.md** file gives OpenAI Codex (and any other AI-powered assistants) a single, opinionated reference for navigating, extending, and maintaining the **Python + FastAPI + Pydantic + SQLAlchemy + Alembic**.

---

## Project Flow
Route --> Service --> Repository --> DB

## Project Structure for OpenAI Codex Navigation

/sales_assistant_api
├── src/                       # application source
│   ├── config/                # settings, dependency-injection helpers
│   ├── models/                # SQLAlchemy ORM entities  ←  DB layer
│   ├── repositories/          # data-access logic       ←  Repository layer
│   ├── services/              # business rules          ←  Service layer
│   ├── routers/               # FastAPI endpoints       ←  Route layer
│   ├── schemas/               # Pydantic DTOs           ←  contract between layers
│   ├── utils/                 # pure helper functions (no I/O side effects)
│   └── main.py                # FastAPI app entry-point
├── alembic/                   # Alembic revision files (DDL history)
├── tests/                     # pytest suites
├── scripts/                   # one-off admin / seed scripts
├── Dockerfile                 # container recipe
└── docker-compose.yml         # dev-stack orchestration

> **Tip for Codex:** Treat every directory as the single source of truth for its layer; never cross layer boundaries.

---

## Coding Conventions for OpenAI Codex

### 1. Pydantic Schema Guidelines

- Always inherit from `BaseModel`; never bypass validation.  
- Split schemas by intent: `AgentCreate`, `AgentUpdate`, `AgentRead`.  

### 2. FastAPI Route Guidelines

- Prefer **function-based** async routes (`async def`).  
- Use helper function `get_service` from `src/utils/dependencies` to inject service dependencies.
- Inject dependencies with `Depends` instead of importing layers directly.  
- `HTTPException` are handled here

### 3. Service Layer Guidelines

- One service per aggregate (`AgentService`).  
- Remain **framework-agnostic**—no FastAPI or SQLAlchemy imports here.  

### 4. Repository Layer Guidelines

- Operate on **pure SQLAlchemy** and **AsyncSession**.  
- `create`, `get`, `list`, `update`, `delete` are mandatory; add custom queries sparingly.  
- Never import FastAPI, Pydantic, or business logic.

### 5. Alembic Migration Standards

- Generate with  
  ```bash
  alembic revision --autogenerate -m "your concise title"

### 6. Final Notes for OpenAI Codex

- Follow the Route → Service → Repository → DB flow—no shortcuts.
- Keep Pydantic schemas, ORM models, and Alembic migrations in sync.
- Prefer dependency injection over singleton imports for testability.
- Document edge cases and assumptions; future Codex runs depend on them.