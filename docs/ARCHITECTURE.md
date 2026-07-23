```
                                         +----------------------+
                                         |      React UI        |
                                         +----------+-----------+
                                                    |
                                           REST / WebSocket
                                                    |
                                                    ▼
                                    +-------------------------------+
                                    |         FastAPI API           |
                                    |  Auth / Rate Limit / Logging  |
                                    +---------------+---------------+
                                                    |
                                                    ▼
                                    +-------------------------------+
                                    |      LangGraph Supervisor     |
                                    +---------------+---------------+
                                                    |
                           +------------------------+------------------------+
                           |                         |                       |
                           ▼                         ▼                       ▼
                   Intent Detection          Conversation Memory      Session Manager
                           |                         |                       |
                           +-------------------------+-----------------------+
                                                     |
                                                     ▼
                                            Task Planner Node
                                                     |
                                                     ▼
                                             Tool Selection Node
                                                     |
                +----------------------+-------------+--------------+----------------------+
                |                      |                            |                      |
                ▼                      ▼                            ▼                      ▼
        General Legal Tool     Document QA Tool             Legal Search Tool      Compare Tool
                |                      |                            |                      |
                |                      |                            |                      |
                |              +-------+--------+          +--------+---------+            |
                |              |                |          |                  |            |
                |              ▼                ▼          ▼                  ▼            |
                |          Qdrant         PostgreSQL   India Code      Court Search        |
                |                                                            |
                +----------------------+----------------------+--------------+
                                                       |
                                                       ▼
                                            Context Aggregator
                                                       |
                                                       ▼
                                              Prompt Builder
                                                       |
                                                       ▼
                                                 ChatGroq
                                                       |
                                                       ▼
                                                Citation Checker
                                                       |
                                                       ▼
                                                Response Formatter
                                                       |
                                                       ▼
                                                   LangSmith
                                                       |
                                                       ▼
                                                     Client

```
