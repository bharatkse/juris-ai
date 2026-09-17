# API Reference

---

## API Endpoints

**Base URL:** `http://localhost:8001/api/v1`

**Interactive Documentation:** `http://localhost:8001/docs`

---

### Health

| Method | Endpoint  | Description                     |
| :----: | --------- | ------------------------------- |
| `GET`  | `/health` | Check application health status |

---

### Users

| Method  | Endpoint           | Description           |
| :-----: | ------------------ | --------------------- |
| `POST`  | `/users`           | Create a new user     |
|  `GET`  | `/users/{user_id}` | Retrieve user details |
| `PATCH` | `/users/{user_id}` | Update user profile   |

#### User ID Format

```text
user_<32-character hexadecimal UUID>

Example:
user_f2b2d0f2e6ea4db39e23d8a24b61c74d
```

---

### Conversations

|  Method  | Endpoint                           | Description               |
| :------: | ---------------------------------- | ------------------------- |
|  `POST`  | `/conversations`                   | Create a new conversation |
|  `GET`   | `/conversations/{conversation_id}` | Retrieve a conversation   |
| `DELETE` | `/conversations/{conversation_id}` | Archive a conversation    |

#### Conversation ID Format

```text
conv_<32-character hexadecimal UUID>

Example:
conv_0c72a842cf344d52a3dc0a0b9894d7a2
```

---

### Chat

| Method | Endpoint       | Description                                           |
| :----: | -------------- | ----------------------------------------------------- |
| `POST` | `/chat`        | Generate a complete AI response                       |
| `POST` | `/chat/stream` | Stream the AI response using Server-Sent Events (SSE) |

#### Chat Request

| Field           | Type            | Required |
| --------------- | --------------- | :------: |
| conversation_id | Conversation ID |    ✅    |
| message         | string          |    ✅    |

### Streaming CURL Request

```
curl -N \
  -X POST "http://localhost:8001/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
  "conversation_id": "conv_23833e202e934590bb1306c518518aad",
  "message": "Explain Article 21 of the Constitution of India."
}'
```

#### Streaming Response

The `/chat/stream` endpoint returns a `text/event-stream` response.

Each event has the following structure:

```json
{
  "content": "Article",
  "is_final": false,
  "metadata": {}
}
```

Example stream:

```text
data: {"content":"Article","is_final":false,"metadata":{}}

data: {"content":" 21","is_final":false,"metadata":{}}

data: {"content":" guarantees","is_final":false,"metadata":{}}

data: {"content":".","is_final":true,"metadata":{}}
```

---

## Request Models

### Create User

| Field            | Type   | Required |
| ---------------- | ------ | :------: | ----- | --- |
| email            | Email  |    ✅    |
| password         | string |    ✅    |
| confirm_password | string |    ✅    |
| first_name       | string |    ❌    |
| last_name        | string |    ❌    |
| gender           | male   |  female  | other | ❌  |
| phone_number     | string |    ❌    |
| date_of_birth    | date   |    ❌    |

---

### Update User

| Field         | Type   |
| ------------- | ------ | ------ | ----- |
| first_name    | string |
| last_name     | string |
| gender        | male   | female | other |
| phone_number  | string |
| date_of_birth | date   |

---

### Create Conversation

| Field   | Type    | Required |
| ------- | ------- | :------: |
| user_id | User ID |    ✅    |
| title   | string  |    ❌    |

---

### Chat Request

| Field           | Type            | Required |
| --------------- | --------------- | :------: |
| conversation_id | Conversation ID |    ✅    |
| message         | string          |    ✅    |

---

## Response Codes

| Status | Description                    |
| :----: | ------------------------------ |
| `200`  | Request completed successfully |
| `201`  | Resource created successfully  |
| `204`  | Resource archived successfully |
| `400`  | Invalid request                |
| `404`  | Resource not found             |
| `422`  | Request validation failed      |
| `429`  | Rate limit exceeded            |
| `500`  | Internal server error          |
| `502`  | LLM provider error             |
| `504`  | LLM provider timeout           |

---

For complete request and response schemas, visit the interactive API documentation:

**http://localhost:8001/docs**
