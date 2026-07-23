---

## API Endpoints

**Base URL:** `http://localhost:8001/api/v1`

**Interactive Documentation:** `http://localhost:8001/docs`

### Health

| Method | Endpoint | Description |
| :----: | -------- | ----------- |
| `GET` | `/health` | Check application health status |

---

### Users

| Method  | Endpoint           | Description           |
| :-----: | ------------------ | --------------------- |
| `POST`  | `/users`           | Create a new user     |
|  `GET`  | `/users/{user_id}` | Retrieve user details |
| `PATCH` | `/users/{user_id}` | Update user profile   |

**User ID Format**

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

**Conversation ID Format**

```text
conv_<32-character hexadecimal UUID>
Example:
conv_0c72a842cf344d52a3dc0a0b9894d7a2
```

---

### Request Models

#### Create User

| Field            | Type                    | Required |
| ---------------- | ----------------------- | :------: |
| email            | Email                   |    ✅    |
| password         | string                  |    ✅    |
| confirm_password | string                  |    ✅    |
| first_name       | string                  |    ❌    |
| last_name        | string                  |    ❌    |
| gender           | male \| female \| other |    ❌    |
| phone_number     | string                  |    ❌    |
| date_of_birth    | date                    |    ❌    |

#### Update User

| Field         | Type                    |
| ------------- | ----------------------- |
| first_name    | string                  |
| last_name     | string                  |
| gender        | male \| female \| other |
| phone_number  | string                  |
| date_of_birth | date                    |

#### Create Conversation

| Field   | Type    | Required |
| ------- | ------- | :------: |
| user_id | User ID |    ✅    |
| title   | string  |    ❌    |

---

### Response Codes

| Status | Description                    |
| :----: | ------------------------------ |
| `200`  | Request completed successfully |
| `201`  | Resource created successfully  |
| `204`  | Resource archived successfully |
| `422`  | Request validation failed      |

For complete request and response schemas, visit the interactive API documentation:

**http://localhost:8001/docs**
