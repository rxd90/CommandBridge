# CommandBridge Load Tests

Load testing for the CommandBridge API using [Locust](https://locust.io).

## Setup

```bash
pip install locust
```

## Running

```bash
COMMANDBRIDGE_API_URL=https://xxx.execute-api.eu-west-2.amazonaws.com \
AUTH_TOKEN=eyJraWQiO... \
locust -f tests/load/locustfile.py
```

Open http://localhost:8089 in your browser.

## Configuration

- **Users**: 10-50 concurrent users (simulating L1/L2 operators)
- **Spawn rate**: 5 users/second
- **Duration**: 5 minutes recommended

## Test Scenarios

| Task | Weight | Description |
|------|--------|-------------|
| GET /actions/permissions | 5 | Dashboard page load |
| POST /actions/execute (pull-logs) | 2 | Low-risk action execution |
| POST /actions/execute (purge-cache) | 2 | Medium-risk action execution |
| POST /actions/request (maintenance-mode) | 1 | High-risk approval request |
| GET /actions/audit | 1 | Audit log view |

## Notes

- Requires a valid JWT token in `AUTH_TOKEN` env var
- The token must belong to a user with L1-operator or higher role
- For production load tests, coordinate with the platform team
