# ⚖️ Juris AI

Juris-AI is an AI-powered legal assistant designed around explicit agent execution strategies and provider-independent AI infrastructure.

The architecture separates **planning, execution, reasoning, external actions, persistence, and API concerns**, allowing the system to evolve from a small multi-agent application into a multi-agent, multi-provider, multi-source legal AI platform.

## Architecture Principles

The core architectural boundaries are:

- **FastAPI** — HTTP, authentication, request validation, and streaming.
- **ChatService** — conversation lifecycle and database transaction coordination.
- **AIOrchestrator** — coordinates the AI lifecycle; it does not perform planning or agent execution.
- **Planner** — converts a user request into an explicit `ExecutionPlan`.
- **Executor** — executes the plan; it never creates the plan.
- **Agents** — perform domain-specific reasoning.
- **Tools** — perform external actions such as document parsing, retrieval, and web search.
- **Registries** — resolve agents and tools.
- **LLM Clients / Gateway** — hide provider-specific SDK details.
- **Validator** — validates generated execution results.
- **Aggregator** — combines agent outputs and preserves provenance.
- **Execution Runtime / Memory** — holds transient execution artifacts.
- **ConversationEventService** — persists conversation events and remains independent from AI execution.

The architecture intentionally keeps **planning and execution separate**:

```text
User Request
     │
     ▼
ChatService
     │
     ▼
AIOrchestrator
     │
     ▼
Planner ───────────► LLM #1
     │
     ▼
ExecutionPlan
     │
     ▼
Executor
     │
     ├───────────────┐
     ▼               ▼
 Sequential       Parallel
     │               │
     └───────┬───────┘
             ▼
          Agents
             │
             ├── Tools
             │
             └── LLM #2+
             │
             ▼
      Execution Results
             │
             ▼
         Validator
             │
             ▼
        Aggregator
             │
             ▼
    OrchestratorResponse
             │
             ▼
        ChatService
             │
             ├── USER event
             ├── ASSISTANT event
             └── COMMIT
```

## Execution Strategies

Juris-AI supports three explicit execution strategies:

### Sequential

Steps execute one after another.

```text
Step A
  │
  ▼
Step B
  │
  ▼
Step C
```

### Parallel

Independent steps execute concurrently.

```text
          ExecutionPlan
               │
        ┌──────┼──────┐
        ▼      ▼      ▼
      Agent A Agent B Agent C
        │      │      │
        └──────┼──────┘
               ▼
           Aggregator
```

### Hybrid

The plan combines sequential dependencies with parallel branches.

```text
Step A
  │
  ▼
Step B
  │
  ├──────────────┐
  ▼              ▼
Step C          Step D
  │              │
  └───────┬──────┘
          ▼
        Step E
```

This execution model is intentionally preserved in the architecture rather than reducing execution to a single linear call.

---

# ✨ Features

- AI-powered legal assistant
- Multiple domain-specific agents
- Explicit sequential, parallel, and hybrid execution
- LLM-based execution planning
- Provider-independent LLM abstraction
- Document retrieval and parsing
- Web search integration
- Conversation and event persistence
- User registration and authentication
- FastAPI REST APIs with OpenAPI documentation
- Secure password hashing using Argon2 (`pwdlib`)
- PostgreSQL with SQLAlchemy 2.x
- Alembic database migrations
- Environment-based configuration using Pydantic Settings
- Redis or in-memory caching
- Docker and Docker Compose support
- Automated testing, linting, formatting, and CI/CD

---

# 🚀 Quick Start

## Clone the repository

```bash
git clone <repository-url>
cd juris-ai
```

## Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

## Install dependencies

```bash
poetry install
```

## Configure environment

```bash
cp .env.example .env
```

Update the required values in `.env`.

## Start the application

```bash
make dev-deploy
```

## Run database migrations

```bash
make alembic-upgrade
```

The API will be available at:

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

---

# 📂 Project Structure

```text
src/
├── agents/             # Domain reasoning
├── aggregation/        # Response aggregation
├── api/                # HTTP/API layer
├── cache/              # Cache abstraction
├── clients/            # External provider integrations
├── core/               # Shared application primitives
├── db/                 # Database and ORM
├── execution/          # Execution engine
├── middleware/         # Application middleware
├── orchestration/      # AI lifecycle coordination
├── planning/           # Intent and execution planning
├── registry/           # Agent/tool lookup
├── repositories/       # Database persistence
├── runtime/            # Dependency wiring/composition
├── schemas/            # API schemas
├── security/           # Security functionality
├── services/           # Application workflows
├── tools/              # External actions
├── validation/         # Result validation
└── main.py             # Application entry point
```

### Module Responsibilities

| Module          | Responsibility                                               |
| --------------- | ------------------------------------------------------------ |
| `agents`        | Domain-specific reasoning                                    |
| `aggregation`   | Merge agent results and provenance                           |
| `api`           | HTTP endpoints, authentication, and streaming                |
| `cache`         | Cache abstraction                                            |
| `clients`       | External provider integrations                               |
| `core`          | Shared types, DTOs, configuration, exceptions, and utilities |
| `db`            | Database engine, sessions, and ORM models                    |
| `execution`     | Execution of sequential, parallel, and hybrid plans          |
| `middleware`    | Request-level middleware                                     |
| `orchestration` | Coordinate the overall AI lifecycle                          |
| `planning`      | Intent analysis and `ExecutionPlan` creation                 |
| `registry`      | Agent and tool resolution                                    |
| `repositories`  | Database persistence operations                              |
| `runtime`       | Dependency and component composition                         |
| `schemas`       | API request and response models                              |
| `security`      | Authentication-related security utilities                    |
| `services`      | Application-level workflows                                  |
| `tools`         | Retrieval, parsing, search, and other external actions       |
| `validation`    | Validate execution and response results                      |

---

# 🛠 Technology Stack

| Layer              | Technology              |
| ------------------ | ----------------------- |
| Language           | Python 3.11+            |
| Framework          | FastAPI                 |
| ASGI Server        | Uvicorn                 |
| Database           | PostgreSQL              |
| ORM                | SQLAlchemy 2.x          |
| Database Migration | Alembic                 |
| Validation         | Pydantic v2             |
| Authentication     | pwdlib (Argon2)         |
| Cache              | Redis / In-Memory       |
| AI Provider        | Groq (Pluggable)        |
| Containerization   | Docker & Docker Compose |
| Code Quality       | Ruff, MyPy, Pre-commit  |
| Testing            | Pytest                  |

---

# 🔌 Provider Independence

LLM provider-specific implementations are isolated behind the LLM client abstraction.

```text
                    LLM Gateway
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
        Groq          OpenAI        Future
```

Agents and the rest of the application depend on the provider-independent LLM interface rather than directly depending on a provider SDK.

This allows providers to be changed or added without modifying agent reasoning or orchestration logic.

---

# 🧠 Agent Architecture

Agents are responsible for **reasoning**, not infrastructure or execution orchestration.

```text
Agent
 │
 ├── PromptBuilder
 │
 ├── RetrieverTool
 │      ├── Documents
 │      ├── Vector Search
 │      └── Web Search
 │
 └── LLM Client
```

The same agent abstraction can support multiple domain agents:

```text
Agents
 ├── LegalAgent
 ├── ContractAgent
 └── Future Agents
```

---

# 🔄 Request Lifecycle

For a normal legal question:

```text
POST /chat
   │
   ▼
ChatService
   │
   ├── Create USER event
   │
   ▼
AIOrchestrator
   │
   ▼
Planner
   │
   ├── LLM #1
   │
   ▼
ExecutionPlan
   │
   ▼
Executor
   │
   ▼
LegalAgent
   │
   ├── RetrieverTool
   │      ├── Document
   │      ├── Vector
   │      └── Web
   │
   ├── PromptBuilder
   │
   └── LLM #2
   │
   ▼
ExecutionResult
   │
   ▼
ResponseValidator
   │
   ▼
Aggregator
   │
   ├── Content
   ├── Citations
   ├── Sources
   ├── Usage
   └── Agents
   │
   ▼
OrchestratorResponse
   │
   ▼
ChatService
   │
   ├── Create ASSISTANT event
   │
   └── COMMIT
   │
   ▼
API Response
```

---

# 🧩 Responsibility Matrix

| Component                    | Owns                                   | Must NOT Own            |
| ---------------------------- | -------------------------------------- | ----------------------- |
| **FastAPI**                  | HTTP, authentication, validation, SSE  | AI logic                |
| **ChatService**              | Conversation lifecycle, DB transaction | Planning                |
| **Orchestrator**             | AI lifecycle coordination              | Agent execution         |
| **Planner**                  | Intent and `ExecutionPlan`             | Actual execution        |
| **Executor**                 | Plan execution                         | Planning/reasoning      |
| **Agent**                    | Domain reasoning                       | Infrastructure          |
| **Tool**                     | External actions                       | Domain reasoning        |
| **Agent Registry**           | Agent lookup                           | Agent execution         |
| **Tool Registry**            | Tool lookup                            | Tool execution          |
| **LLM Gateway**              | Provider abstraction                   | Business logic          |
| **Aggregator**               | Merge outputs/provenance               | Planning                |
| **Validator**                | Result validation                      | Answer generation       |
| **Execution Memory**         | Runtime artifacts                      | Persistent conversation |
| **ConversationEventService** | DB event persistence                   | AI execution            |
| **Observability**            | Logs, traces, metrics                  | Business decisions      |

---

# 📚 Documentation

| Document               | Description                                 |
| ---------------------- | ------------------------------------------- |
| `docs/README.md`       | [Getting Started Guide](docs/README.md)     |
| `docs/API.md`          | [REST API Reference](docs/API.md)           |
| `docs/ARCHITECTURE.md` | [System Architecture](docs/ARCHITECTURE.md) |
| `docs/DEPLOYMENT.md`   | [Deployment Guide](docs/DEPLOYMENT.md)      |

---

# 👨‍💻 Maintainer

**Bharat Kumar**

Senior Software Engineer | Backend & Cloud

📧 `kumar.bhart28@gmail.com`

🔗 [LinkedIn](https://www.linkedin.com/in/bharat-kumar28)

---

# 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
