# Security and Privacy Implementation

## 1. Authentication

Required:
- individual user accounts
- strong password hashing where passwords are used
- MFA capability
- session expiry
- session/device revocation
- failed-login throttling

## 2. Authorization

- server-side checks on every protected operation
- least privilege
- separate export permission
- separate sensitive-field permission
- admin endpoints never rely on hidden navigation

## 3. Transport / Storage

- TLS in transit
- PostgreSQL encryption at rest via infrastructure
- private object storage
- secrets outside repository
- sensitive identifier field encryption where specified

## 4. Government ID

Recommended:
- encrypt full value using application-level key management
- store deterministic/one-way normalized hash for duplicate lookup
- return masked value unless authorized

## 5. Logging

Never log:
- password
- MFA secret
- refresh/session token
- full government ID
- full uploaded CV text by default
- raw file bytes

## 6. Files

- allow-list MIME types
- enforce size limits
- malware scan before trusted download
- signed/expiring download URLs
- authorization before URL issuance

## 7. CORS / CSRF

If cookie-based auth:
- strict origin allow-list
- SameSite and Secure cookies
- CSRF protection for state-changing requests as required by architecture

## 8. Rate Limiting

At minimum:
- login
- password reset
- public/self-service forms
- file upload initialization
- expensive search
- AI/parser endpoints

## 9. Privacy

Data minimization applies.

Do not collect a sensitive field only because it existed in a legacy spreadsheet.

## 10. Consent

Store consent as a versioned, auditable entity.

Withdrawal should:
- preserve history
- affect future processing according to policy
- not erase required audit evidence

## 11. Export

Sensitive export:
- explicit permission
- server-side field projection
- audit
- expiration for generated files
- no public links

## 12. Environment Separation

Development/staging:
- synthetic or anonymized records
- no production secrets
- visually distinct environment indicator

## 13. Security Testing

Must cover:
- horizontal access control
- vertical privilege escalation
- file authorization
- mass assignment
- insecure direct object references
- stale session access
- export bypass
- search leakage
