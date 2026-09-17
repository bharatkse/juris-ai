# LangSmith

## Obtaining a LangSmith API Key and Creating a Tracing Project

This guide explains how to configure LangSmith for the Juris-AI development environment.

## 1. Open LangSmith

Open LangSmith and sign in:

https://smith.langchain.com/

## 2. Create a Tracing Project

Before configuring the API key in Juris-AI, create the tracing project that will contain the application's traces.

In LangSmith, open:

```text
Tracing
   ↓
Create a new tracing project
```

You should see:

```text
Create a new tracing project

A project is a container for traces related to a single application or service.
You can have multiple projects, and each project can contain multiple traces.
```

Configure the project as follows:

| Field            | Value            |
| ---------------- | ---------------- |
| **Project name** | `juris-ai-dev`   |
| **Application**  | `No application` |
| **Tags**         | Optional         |

### Project name

Use:

```text
juris-ai-dev
```

This is the project name that Juris-AI will use when sending traces to LangSmith.

### Application

For the current Juris-AI setup, select:

```text
No application
```

### Tags

Tags are optional. You can leave them empty for the development environment.

Create the project.

After creation, you should have a tracing project:

```text
juris-ai-dev
```

## 3. Open API Key Settings

Now create the API key that Juris-AI will use to authenticate with LangSmith.

1. Open **Settings**.
2. Go to **API Keys**.
3. Select **Create API Key**.

## 4. Configure the API Key

For Juris-AI, use:

| Field                     | Value                                 |
| ------------------------- | ------------------------------------- |
| **Description**           | `juris-ai-dev`                        |
| **Key Type**              | **Service Key**                       |
| **Scope for Service Key** | **Specific Workspaces**               |
| **Workspaces**            | Select the workspace used by Juris-AI |
| **Expiration Date**       | **1 year**                            |

### Why Service Key?

Juris-AI is an application/service, so a **Service Key** is appropriate for application authentication.

A Personal Access Token is intended for authenticating with LangSmith as an individual user.

### Why Specific Workspaces?

Use **Specific Workspaces** instead of **Full Organization** to follow the principle of least privilege.

## 5. Create the Key

1. Review the settings.
2. Create the API key.
3. Copy the generated key immediately.

**Important:** Never commit the API key to Git or put it directly into source code.

## 6. Configure Juris-AI `.env`

Add the generated API key and the **same project name created in Step 8**:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_sk_...
LANGSMITH_PROJECT=juris-ai-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

The important relationship is:

```text
LangSmith
│
└── Tracing
    │
    └── Project: juris-ai-dev
             ▲
             │
             │ LANGSMITH_PROJECT
             │
       Juris-AI
```

So `LANGSMITH_PROJECT` must exactly match the tracing project name:

```text
juris-ai-dev
```

### Final configuration

```text
LangSmith
│
├── Workspace
│
├── Tracing
│   └── juris-ai-dev
│       └── Juris-AI traces
│
└── API Keys
    └── juris-ai-dev
```

This is the setup to complete before wiring `configure_langsmith()` into the Juris-AI application.
