# Clients

First-party applications that consume the Juris AI API.

| Client | Path | Status |
| --- | --- | --- |
| Web | [`web/`](web/) | Next.js 15 app on port 3100 |

The server remains a complete product on its own — a REST API with
interactive documentation (Swagger UI at `/docs`, ReDoc at `/redoc`
once running) that any HTTP client can use directly.

See the root [README.md](../README.md)'s Repository Map for how this
directory fits into the overall layout, and
[CONTRIBUTING.md](CONTRIBUTING.md) for how to add another client.
