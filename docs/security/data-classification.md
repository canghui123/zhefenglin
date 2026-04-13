# Data Classification Policy

## Classification Levels

| Level | Label | Examples | Controls |
|-------|-------|----------|----------|
| 1 | Public | API docs, health endpoint | None |
| 2 | Internal | Aggregate portfolio stats, error codes | Auth required |
| 3 | Confidential | Asset packages, valuations, simulation results | Auth + tenant isolation |
| 4 | Restricted | User credentials, API keys, audit logs | Encrypted at rest, limited access |

## Data Categories

### Level 3 — Confidential
- **Asset packages**: Excel uploads containing VINs, loan principals, buyout prices
- **Valuation results**: che300 pricing data per vehicle
- **Simulation results**: Five-path analysis with financial projections
- **Reports**: Generated HTML reports with detailed financial analysis

### Level 4 — Restricted
- **User credentials**: Password hashes (bcrypt), JWT secrets
- **API keys**: che300 access credentials, DeepSeek API key
- **Audit logs**: User actions with IP addresses and user agents
- **Session tokens**: JWT tokens in cookies

## Handling Rules

1. **Never log** Level 4 data (passwords, tokens, API keys)
2. **Mask** VINs in logs (show only last 4 characters)
3. **Tenant isolation** enforced at repository layer for all Level 3+ data
4. **Audit trail** required for all write operations on Level 3+ data
5. **Encryption at rest** required for Level 4 in production (database-level)
