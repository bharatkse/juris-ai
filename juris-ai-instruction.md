# Juris-AI — Architecture Audit, Gap Analysis & Phased Completion

You are working on **Juris-AI**, a production-grade legal AI platform.

Your first responsibility is **NOT to start coding**.

Your first responsibility is to deeply understand the existing project, reconstruct its architecture, identify problems and gaps, establish a realistic completion roadmap, and then execute the project **phase-by-phase** without unnecessarily redesigning already-frozen architectural decisions.

---

# 1. PRIMARY OBJECTIVE

Take ownership of the Juris-AI codebase from its current state and drive it toward a:

- production-ready
- maintainable
- scalable
- observable
- testable
- secure
- modular
- cloud-ready
- agentic legal-AI platform

You must:

1. Understand the complete repository.
2. Review architecture and boundaries.
3. Review implementation quality.
4. Identify bugs and architectural problems.
5. Identify missing functionality.
6. Identify incomplete implementations.
7. Identify duplicate code.
8. Identify dead/unreachable code.
9. Identify unused dependencies.
10. Identify inconsistent patterns.
11. Identify incorrect abstractions.
12. Identify missing tests.
13. Identify missing error handling.
14. Identify security issues.
15. Identify observability gaps.
16. Identify performance/scalability problems.
17. Identify data/model/repository/service boundary violations.
18. Identify technical debt.
19. Build a prioritized implementation roadmap.
20. Execute that roadmap **phase-by-phase**.
21. Validate every phase before moving to the next.
22. Keep architectural decisions consistent across the entire project.

Do not optimize for the number of files changed.

Optimize for **correct architecture, correctness, simplicity, maintainability, and production readiness**.

---

# 2. IMPORTANT — ARCHITECTURE DECISIONS ALREADY FROZEN

The following decisions have already been intentionally established.

Do NOT redesign or rename these unless you discover a genuine correctness issue that requires an explicit architectural change.

## 2.1 Agentic domain

The top-level agent execution domain is:

```text
agentic/
```

NOT:

```text
ai/
intelligence/
agents_ai/
```

`agentic/` owns the agentic system, including concepts such as:

- agents
- runtime
- execution
- workflows
- collaboration
- memory
- planning
- orchestration

LLM/provider integrations do NOT belong here.

LLM/provider integrations remain under:

```text
adapters/clients/llm/
```

Retrieval remains under:

```text
rag/
```

Maintain this separation.

---

# 3. HIGH-LEVEL ARCHITECTURAL BOUNDARIES

Respect the distinction between:

```text
domain
application/service
infrastructure
adapters
API/interface
agentic
rag
```

Do not allow infrastructure concerns to leak into domain logic.

Do not allow API/DTO concerns to leak into repositories.

Do not allow provider-specific implementations to leak throughout the application.

Do not introduce shortcuts simply because they are faster to implement.

---

# 4. REPOSITORY / ENTITY RULE

Repositories must return:

```text
SQLAlchemy entity/model objects
```

They must NOT return:

```text
DTOs
dicts
API schemas
serialized objects
```

DTO conversion belongs in the application/service layer.

Entities should expose conversion where appropriate, e.g.:

```python
entity.to_dto()
```

or equivalent established project convention.

Review the entire repository layer for violations of this rule.

---

# 5. EXECUTION WORKFLOW — FROZEN ARCHITECTURE

The existing execution architecture around:

- `Executor`
- `ExecutionSession`
- LangGraph
- checkpointing
- `ActionWorkflowService`

has been intentionally established.

Treat this workflow as **frozen architecture**.

Do NOT redesign the execution workflow simply because another design may look cleaner.

Instead:

- understand the existing design
- identify bugs
- identify missing behavior
- identify implementation gaps
- improve reliability
- improve testability
- improve observability
- improve error handling
- improve performance where justified

Only propose a structural redesign if the current implementation contains a fundamental correctness/scalability problem.

If such a redesign is necessary, STOP before implementing it and explain the problem and proposed change.

---

# 6. RAG ARCHITECTURE

The RAG architecture is also an established reference design.

Review and preserve the separation between:

```text
ingestion
document processing
chunking
embedding
vector storage
retrieval
reranking
context construction
generation
evaluation
observability
```

The project has an established RAG evaluation direction:

## Online evaluation

Local LLM-as-judge sampling for:

- faithfulness
- answer relevancy
- context precision

This is asynchronous / fire-and-forget and does not require ground truth.

## Offline evaluation

Ragas-based CI evaluation for:

- faithfulness
- answer relevancy
- context precision
- context recall

using golden datasets and quality gates.

Do not casually replace this evaluation architecture.

Review whether the implementation actually matches this intended design.

---

# 7. INITIAL PROJECT AUDIT — DO NOT MODIFY CODE YET

Before making meaningful code changes, perform a complete audit.

Start with repository discovery.

Inspect:

```text
directory structure
pyproject.toml
dependency configuration
configuration files
environment configuration
Docker configuration
infrastructure/
scripts/
docs/
database/migrations
Alembic configuration
API layer
domain layer
application/services
repositories
models/entities
schemas/DTOs
agentic/
rag/
adapters/
LLM integrations
workflow/execution code
tests
evaluation
observability
logging
metrics
tracing
CI/CD
security configuration
```

Also inspect:

- imports
- dependency graph
- circular dependencies
- initialization/bootstrap flow
- application startup
- database lifecycle
- async/sync boundaries
- external service boundaries
- configuration loading
- exception hierarchy
- transaction handling
- background tasks
- retry logic
- timeouts
- idempotency
- concurrency
- resource cleanup

---

# 8. CODE QUALITY AUDIT

Look specifically for:

### Bugs

- incorrect logic
- race conditions
- incorrect async behavior
- incorrect transaction handling
- resource leaks
- incorrect exception handling
- incorrect state transitions
- checkpointing problems
- retry problems
- timeout problems
- incorrect dependency injection
- data consistency issues

### Duplicate code

Find:

- repeated business logic
- duplicated validation
- duplicated repository queries
- duplicated serialization
- repeated error handling
- repeated LLM invocation logic
- repeated configuration logic
- repeated retrieval logic
- repeated agent orchestration logic

Do not blindly consolidate code.

Only extract abstractions when they genuinely improve maintainability.

---

# 9. DEAD CODE AUDIT

Identify:

- unused modules
- unused classes
- unused functions
- unused imports
- obsolete compatibility code
- unreachable branches
- unused configuration
- unused dependencies
- abandoned implementations
- duplicate implementations of the same feature
- old architecture remnants

Distinguish between:

```text
confirmed dead code
possibly unused code
framework/runtime entry points
future/planned code
```

Do not delete something merely because static analysis says it is unused.

---

# 10. ARCHITECTURAL VIOLATION AUDIT

Look for:

- wrong layer dependencies
- domain → infrastructure leakage
- repository → DTO leakage
- API → database direct access
- service bypassing repositories
- provider-specific code outside adapters
- LLM code outside `adapters/clients/llm/`
- retrieval code outside `rag/`
- agent execution code outside `agentic/`
- business logic inside API controllers
- database logic inside agents
- DTO conversion inside repositories
- excessive utility modules
- god classes
- god services
- circular dependencies

For every violation, explain:

```text
Current dependency
Why it is wrong
Expected dependency
Recommended fix
Risk
Priority
```

---

# 11. AGENTIC SYSTEM AUDIT

Review:

```text
agentic/
```

in detail.

Evaluate:

- agent lifecycle
- agent interfaces
- agent registry
- runtime
- execution
- workflow orchestration
- planning
- collaboration
- memory
- state management
- tool execution
- MCP integration
- LangGraph integration
- checkpointing
- cancellation
- retries
- timeouts
- failure recovery
- human-in-the-loop
- execution isolation
- concurrency
- observability
- tracing
- cost/token tracking

Look for duplicated abstractions between:

```text
agentic/
services/
rag/
adapters/
```

Do not create a second orchestration architecture if one already exists.

---

# 12. LLM / PROVIDER AUDIT

Review:

```text
adapters/clients/llm/
```

for proper provider abstraction.

Evaluate:

- provider interfaces
- model routing
- fallback
- retries
- timeout
- streaming
- structured output
- token accounting
- cost tracking
- provider-specific configuration
- error normalization
- observability
- model capability handling

Provider-specific code should remain isolated behind appropriate adapter interfaces.

---

# 13. RAG AUDIT

Review the entire RAG pipeline.

Evaluate:

```text
document ingestion
document parsing
normalization
chunking
metadata
embeddings
vector store
retrieval
hybrid retrieval
reranking
context assembly
prompt construction
generation
citation/provenance
evaluation
```

Check:

- correctness
- metadata propagation
- filtering
- tenant/user isolation if applicable
- duplicate retrieval
- context overflow
- poor chunking
- missing reranking
- retrieval failure handling
- embedding failures
- retry behavior
- indexing idempotency
- observability

---

# 14. EVALUATION AUDIT

Review whether evaluation is actually implemented according to the intended architecture.

### Online

Verify asynchronous local-LLM judge sampling for:

```text
faithfulness
answer relevancy
context precision
```

No ground truth required.

### Offline

Verify Ragas CI evaluation for:

```text
faithfulness
answer relevancy
context precision
context recall
```

with:

```text
golden datasets
quality thresholds
CI quality gates
```

Identify missing:

- datasets
- metrics
- runners
- configuration
- thresholds
- CI integration
- reports
- regression detection

---

# 15. TESTING AUDIT

Assess:

```text
unit tests
integration tests
repository tests
service tests
API tests
agent tests
workflow tests
RAG tests
LLM adapter tests
evaluation tests
end-to-end tests
```

Look for:

- missing coverage
- weak assertions
- mocked internals instead of behavior
- tests coupled to implementation
- missing failure-path tests
- missing concurrency tests
- missing idempotency tests
- missing retry tests
- missing timeout tests
- missing checkpoint recovery tests

Do not pursue meaningless coverage percentages.

Prioritize tests around business-critical and failure-prone paths.

---

# 16. SECURITY AUDIT

Review:

- authentication
- authorization
- tenant isolation
- secrets
- environment variables
- prompt injection
- tool authorization
- MCP security
- agent permissions
- data access boundaries
- SQL injection
- unsafe deserialization
- SSRF
- file upload handling
- sensitive logging
- PII leakage
- model/provider credentials
- dependency vulnerabilities
- container security
- API security
- rate limiting

Classify findings:

```text
Critical
High
Medium
Low
Informational
```

---

# 17. OBSERVABILITY AUDIT

Review:

```text
logging
metrics
tracing
OpenTelemetry
LangSmith
LLM telemetry
agent execution telemetry
RAG telemetry
database telemetry
latency
token usage
cost
errors
retries
workflow state
```

Determine whether production debugging is realistically possible.

Identify missing correlation IDs / trace IDs / execution IDs where relevant.

---

# 18. PERFORMANCE / SCALABILITY AUDIT

Review:

- synchronous blocking operations
- unnecessary database queries
- N+1 queries
- excessive LLM calls
- duplicated retrieval
- unnecessary serialization
- large context windows
- inefficient embeddings
- connection management
- connection pooling
- concurrency
- task queues
- caching
- retries
- rate limits
- backpressure
- memory usage

Do not prematurely optimize.

Prioritize measurable bottlenecks and obvious architectural risks.

---

# 19. DEPENDENCY AUDIT

Inspect `pyproject.toml` and dependency configuration.

Identify:

- unused dependencies
- duplicate libraries
- conflicting libraries
- unnecessary heavy dependencies
- obsolete dependencies
- development/runtime dependency mistakes
- version compatibility problems
- missing dependencies
- dependency security concerns

Do not upgrade everything blindly.

---

# 20. DATABASE / MIGRATION AUDIT

Review:

- SQLAlchemy models
- relationships
- indexes
- constraints
- foreign keys
- transaction boundaries
- migrations
- Alembic configuration
- migration consistency
- naming conventions
- nullable fields
- cascading behavior
- query performance

Check that migrations accurately represent the model state.

---

# 21. CONFIGURATION AUDIT

Review configuration for:

- environment separation
- development/test/production
- secrets
- defaults
- validation
- typed settings
- duplicated configuration
- hard-coded values
- provider configuration
- feature flags
- observability configuration
- database configuration
- infrastructure configuration

---

# 22. API AUDIT

Review:

- routing
- request validation
- response models
- error responses
- authentication
- authorization
- dependency injection
- pagination
- filtering
- idempotency
- status codes
- API versioning
- OpenAPI documentation
- async behavior

Controllers/routes should remain thin.

Business logic belongs in application/service layers.

---

# 23. DOCUMENTATION AUDIT

Review:

```text
README
docs/
architecture documentation
API documentation
development setup
deployment documentation
environment configuration
ADR/decision documentation
agent documentation
RAG documentation
evaluation documentation
```

Identify documentation that is:

- missing
- stale
- contradictory
- misleading
- overly detailed but incorrect
- missing important operational information

Documentation must reflect the actual code after each phase.

---

# 24. PRODUCE AN ARCHITECTURE MAP

Before implementation, produce a concise architecture map.

Include:

```text
System
 ├── API
 ├── Application
 ├── Domain
 ├── Infrastructure
 ├── Adapters
 │    └── LLM
 ├── Agentic
 │    ├── Runtime
 │    ├── Execution
 │    ├── Workflows
 │    ├── Planning
 │    ├── Collaboration
 │    └── Memory
 ├── RAG
 │    ├── Ingestion
 │    ├── Processing
 │    ├── Retrieval
 │    ├── Reranking
 │    └── Evaluation
 ├── Database
 ├── Observability
 └── Infrastructure
```

Adjust the diagram to match the actual repository.

Do NOT invent components that do not exist.

Clearly distinguish:

```text
implemented
partially implemented
planned
missing
```

---

# 25. FINDINGS REGISTER

Create a structured findings register.

For every finding include:

```text
ID
Category
Severity
Location
Current behavior
Problem
Why it matters
Recommended action
Dependencies
Estimated complexity
Phase
```

Categories should include:

```text
BUG
ARCHITECTURE
DUPLICATION
DEAD_CODE
SECURITY
PERFORMANCE
TESTING
OBSERVABILITY
DATABASE
RAG
AGENTIC
LLM
API
CONFIG
DEPENDENCY
DOCUMENTATION
TECH_DEBT
```

---

# 26. PRIORITIZATION

Prioritize findings using:

```text
P0 — Critical / blocking
P1 — High / production risk
P2 — Important / architectural or quality improvement
P3 — Nice-to-have / optimization
```

Use this order:

1. correctness
2. security
3. data integrity
4. architectural integrity
5. reliability
6. observability
7. testability
8. performance
9. maintainability
10. optimization / cleanup

Do not spend time polishing low-priority code while critical architectural or correctness issues remain.

---

# 27. DEFINE PROJECT PHASES

After the audit, create a phased roadmap.

A reasonable starting structure is:

## Phase 0 — Discovery & Architecture Baseline

- repository mapping
- architecture map
- dependency map
- findings register
- frozen decisions
- technical debt inventory
- project completion definition

## Phase 1 — Foundation & Correctness

- critical bugs
- startup/bootstrap issues
- database/migration problems
- dependency issues
- configuration issues
- architectural boundary violations
- broken imports
- broken core flows

## Phase 2 — Domain & Application Integrity

- domain correctness
- service boundaries
- repository consistency
- DTO/entity boundaries
- transactions
- validation
- error handling

## Phase 3 — Agentic Runtime & Execution

- agent runtime
- execution
- workflows
- LangGraph integration
- checkpointing
- retries
- timeout
- failure recovery
- HITL
- state management
- observability

Preserve the existing frozen execution architecture.

## Phase 4 — RAG

- ingestion
- processing
- chunking
- embeddings
- retrieval
- reranking
- context assembly
- citations/provenance
- reliability

## Phase 5 — LLM / Provider Layer

- adapters
- routing
- fallback
- streaming
- structured output
- retries
- token usage
- cost tracking

## Phase 6 — Evaluation

- online evaluation
- offline Ragas evaluation
- golden datasets
- thresholds
- regression detection
- CI quality gates

## Phase 7 — Testing & Reliability

- unit tests
- integration tests
- workflow tests
- agent tests
- RAG tests
- failure-path tests
- end-to-end tests

## Phase 8 — Security

- authorization
- isolation
- prompt/tool security
- secrets
- dependency security
- input validation
- logging/privacy

## Phase 9 — Observability & Operations

- OpenTelemetry
- metrics
- traces
- structured logging
- execution correlation
- LLM telemetry
- cost/token monitoring
- operational dashboards

## Phase 10 — Performance & Scalability

- database optimization
- concurrency
- caching
- LLM call optimization
- RAG optimization
- connection management
- rate limiting
- backpressure

## Phase 11 — Cleanup & Documentation

- remove confirmed dead code
- remove duplicate implementations
- dependency cleanup
- documentation
- architecture diagrams
- developer setup
- deployment documentation

## Phase 12 — Production Readiness

- full validation
- CI/CD
- migrations
- deployment
- security validation
- observability validation
- performance validation
- disaster/failure scenarios
- final architecture review

These phases are a starting point, not a mandate.

Change the phase structure if the actual repository indicates a better dependency/order.

Explain why.

---

# 28. DEFINE "DONE"

Do not treat:

```text
code compiles
```

as completion.

A phase is complete only when:

- implementation is complete
- tests exist for important behavior
- failure paths are covered
- architectural boundaries are preserved
- lint/type checks pass where configured
- migrations are valid
- documentation is updated
- observability is adequate
- no known P0/P1 regression remains
- related dead/duplicate code is addressed
- acceptance criteria are satisfied

---

# 29. EXECUTION RULE

After completing the audit and roadmap:

**DO NOT attempt to implement the entire project in one pass.**

Start with the highest-priority phase.

For each phase:

### Step 1

State:

```text
Phase
Objective
Scope
Files/components affected
Dependencies
Acceptance criteria
```

### Step 2

Implement the phase.

### Step 3

Run appropriate validation:

```text
tests
lint
type checking
imports
migration checks
build
static analysis
```

Use whatever tooling actually exists in the project.

### Step 4

Review your own changes.

Look for:

- regressions
- duplicated abstractions
- accidental architecture changes
- unnecessary complexity
- missing tests
- incorrect assumptions

### Step 5

Update:

```text
findings register
roadmap
documentation
TODOs
```

### Step 6

Summarize:

```text
Completed
Changed
Tests
Validation
Remaining issues
New findings
Next phase
```

Then proceed to the next phase.

---

# 30. DO NOT MAKE THESE MISTAKES

Do NOT:

- rewrite the project from scratch
- redesign frozen architecture without justification
- rename major directories for cosmetic reasons
- create a second execution/orchestration system
- create duplicate agent abstractions
- move LLM integrations out of `adapters/clients/llm/`
- move RAG outside `rag/`
- move agentic execution outside `agentic/`
- return DTOs from repositories
- put business logic in API routes
- put database access directly inside agents
- introduce unnecessary generic abstractions
- add frameworks merely because they are popular
- upgrade dependencies blindly
- delete code without evidence
- mark code dead based only on static search
- optimize prematurely
- create speculative infrastructure
- create placeholder implementations and call them complete
- hide errors with broad exception handling
- use `Any` to bypass typing problems
- disable tests to make CI pass
- lower quality gates to hide failures

---

# 31. DECISION-MAKING PRINCIPLE

When multiple solutions are possible, prefer:

```text
simpler
explicit
well-bounded
testable
observable
replaceable
production-oriented
```

over:

```text
clever
generic
over-engineered
framework-heavy
implicit
```

Prefer composition over inheritance unless inheritance is clearly justified.

Prefer explicit dependency injection.

Prefer narrow interfaces.

Prefer clear ownership of responsibilities.

---

# 32. CHANGE MANAGEMENT

For every meaningful architectural or structural change, explain:

```text
Why current implementation is insufficient
Why this solution is preferred
What alternatives were considered
What risks exist
How the change will be tested
```

Do not make large unrelated changes in the same phase.

Keep commits/change sets logically scoped.

---

# 33. CODE SEARCH EXPECTATIONS

Do not assume a problem exists in only one location.

When finding a pattern such as:

```text
duplicate validation
duplicate repository behavior
wrong DTO usage
LLM invocation
agent execution
exception handling
configuration access
```

search the entire repository for the same pattern.

Fix the architectural pattern consistently rather than patching one occurrence.

---

# 34. ARCHITECTURAL CONSISTENCY CHECK

Before finishing every phase, ask:

```text
Did this change introduce another abstraction that already exists?

Did this change duplicate an existing service?

Did this change violate domain/application/infrastructure boundaries?

Did this change violate the agentic/LLM/RAG boundaries?

Did this change bypass repositories?

Did this change leak DTOs into persistence?

Did this change create provider coupling?

Did this change duplicate workflow/execution logic?

Did this change create dead code?

Did this change introduce unnecessary dependencies?

Did this change make testing harder?

Did this change reduce observability?
```

If yes, fix it before proceeding.

---

# 35. FINAL PROJECT COMPLETION CRITERIA

The project should ultimately reach a state where:

### Architecture

- clear bounded layers
- clear dependency direction
- no unexplained architectural violations
- agentic architecture is coherent
- RAG architecture is coherent
- LLM adapters are isolated

### Backend

- APIs are stable
- services own business logic
- repositories own persistence
- entities remain persistence/domain objects
- DTO conversion occurs at the application boundary

### Agentic

- execution is reliable
- workflows are deterministic where required
- state/checkpointing works
- failures recover correctly
- HITL works
- tools are controlled
- agents are observable

### RAG

- retrieval is reliable
- context quality is measurable
- citations/provenance are maintained
- evaluation is automated

### LLM

- providers are abstracted
- routing/fallback is reliable
- failures are normalized
- token/cost usage is measurable

### Evaluation

- online evaluation exists
- offline Ragas evaluation exists
- golden datasets exist
- CI quality gates exist
- regressions are detected

### Reliability

- critical failure paths are tested
- retries/timeouts are correct
- idempotency is handled
- concurrency is safe

### Security

- secrets are protected
- authorization is enforced
- data boundaries are respected
- tools/agents cannot perform unauthorized actions
- prompt/tool attack surfaces are addressed

### Observability

- logs
- metrics
- traces
- execution IDs
- LLM telemetry
- RAG telemetry
- cost/token tracking

are available where needed.

### Operations

- Docker works
- migrations work
- CI/CD works
- configuration is environment-safe
- deployment is reproducible

### Maintainability

- dead code removed
- meaningful duplication removed
- dependencies cleaned
- documentation matches implementation
- architecture is understandable to a new engineer

---

# 36. FIRST RESPONSE / FIRST ACTION

Your first task is therefore:

## DO NOT MODIFY THE CODEBASE YET.

Perform the complete **Juris-AI Architecture & Codebase Audit**.

Return:

### A. Executive Summary

What exists today and what state the project is in.

### B. Current Architecture

Actual architecture based on the repository.

### C. Architecture Diagram

Show major components and dependency direction.

### D. Frozen Decisions

List the architectural decisions you will preserve.

### E. Findings

Prioritized P0/P1/P2/P3 findings.

### F. Duplicate Code

Concrete examples with locations.

### G. Dead Code

Concrete examples with evidence.

### H. Missing/Incomplete Features

What appears unfinished.

### I. Architectural Violations

Concrete examples and recommended fixes.

### J. Testing Gaps

Critical missing tests.

### K. Security Gaps

Critical security concerns.

### L. Observability Gaps

Missing telemetry and operational visibility.

### M. Dependency / Infrastructure Issues

Dependency, Docker, migration, CI/CD and infrastructure problems.

### N. Recommended Target Architecture

Only where changes are actually justified.

Do not redesign frozen architecture.

### O. Phased Roadmap

Phase 0 → Phase N.

For every phase provide:

```text
Objective
Scope
Tasks
Dependencies
Risk
Acceptance criteria
```

### P. Definition of Done

Define what "Juris-AI production ready" means.

### Q. Recommended Starting Phase

Identify the single most important phase to begin with and explain why.

---

# 37. AFTER THE AUDIT

Once the audit is complete, wait for approval before making broad changes.

After approval, execute the roadmap **one phase at a time**.

Do not lose the findings register.

Treat the audit and roadmap as the working project plan.

Every subsequent phase should reference:

```text
previous findings
previous changes
remaining risks
acceptance criteria
```

The goal is not merely to make the repository "look cleaner."

The goal is to **finish Juris-AI as a coherent, production-grade legal AI system without destroying the architectural decisions that have already been deliberately established.**
