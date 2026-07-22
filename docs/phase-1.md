```
backend/
├── app/
│
│── api/
│   ├── dependencies/
│   │   ├── auth.py
│   │   └── graph.py
│   │
│   ├── middleware/
│   │   ├── logging.py
│   │   └── exception.py
│   │
│   ├── routes/
│   │   ├── health.py
│   │   ├── conversations.py
│   │   └── messages.py
│   │
│   └── router.py
│
├── agents/
│   ├── legal_assistant.py
│   └── registry.py
│
├── graph/
│   ├── builder.py
│   ├── state.py
│   │
│   └── nodes/
│       ├── intent.py
│       ├── planner.py
│       ├── router.py
│       ├── llm.py
│       └── formatter.py
│
├── chains/
│   ├── legal_chain.py
│   └── prompt_chain.py
│
├── prompts/
│   ├── system_prompt.py
│   ├── legal_prompt.py
│   └── planner_prompt.py
│
├── tools/
│   ├── base.py
│   ├── search.py
│   ├── calculator.py
│   └── registry.py
│
├── clients/
│   ├── groq.py
│   ├── langsmith.py
│   └── search.py
│
├── services/
│   ├── conversation_service.py
│   ├── message_service.py
│   └── agent_service.py
│
├── repositories/
│   ├── conversation_repository.py
│   └── message_repository.py
│
├── db/
│   ├── session.py
│   ├── base.py
│   └── models/
│       ├── conversation.py
│       └── message.py
│
├── schemas/
│   ├── conversation.py
│   ├── message.py
│   └── common.py
│
├── core/
│   ├── config.py
│   ├── logging.py
│   ├── security.py
│   └── constants.py
│
├── utils/
│
├── main.py
│
tests/
│
docker/
│
docs/
│   ├── HLD.md
│   ├── LLD.md
│   └── API.md
│
pyproject.toml

```
