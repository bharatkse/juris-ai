# ⚖️ Juris AI

Juris AI is a modern backend service for AI-powered legal assistance.

Built with FastAPI and PostgreSQL, it provides secure authentication, conversation management, AI integration, and a modular architecture that supports future feature expansion while maintaining clean separation of concerns.

---

# ✨ Features

- 🤖 AI-powered legal assistant
- 👤 User registration and authentication
- 💬 Conversation management
- ⚡ FastAPI REST APIs with OpenAPI documentation
- 🔒 Secure password hashing using Argon2 (`pwdlib`)
- 🗄️ PostgreSQL with SQLAlchemy 2.x ORM
- 🚀 Alembic database migrations
- ⚙️ Environment-based configuration using Pydantic Settings
- ⚡ Redis or in-memory caching
- 🐳 Docker & Docker Compose support
- 🧪 Automated testing, linting, formatting, and CI/CD

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

Open:

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

---

# 📂 Project Structure

```text
src/
├── api/                # FastAPI routes and dependencies
├── core/               # Configuration, logging, constants, exceptions
├── db/
│   ├── migrations/     # Alembic migrations
│   ├── models/         # SQLAlchemy ORM models
│   ├── session.py      # Database session
│   └── base.py
├── repositories/       # Repository layer
├── schemas/            # Request & response schemas
├── security/           # Password hashing & authentication
├── services/           # Business logic
├── agent/                # AI provider integrations
├── cache/              # Redis / Memory cache
└── main.py             # Application entry point
```

---

# 📚 Documentation

| Document               | Description           |
| ---------------------- | --------------------- |
| `docs/README.md`       | Getting Started Guide |
| `docs/API.md`          | REST API Reference    |
| `docs/ARCHITECTURE.md` | System Architecture   |
| `docs/DEPLOYMENT.md`   | Deployment Guide      |

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

# 👨‍💻 Maintainer

**Bharat Kumar**

Senior Software Engineer | Backend & Cloud

📧 kumar.bhart28@gmail.com

🔗 LinkedIn: https://www.linkedin.com/in/bharat-kumar28

---

# 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
