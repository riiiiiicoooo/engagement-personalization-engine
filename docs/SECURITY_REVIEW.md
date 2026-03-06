# Security Review: Engagement & Personalization Engine

**Review Date:** 2026-03-06
**Reviewer:** Automated Security Audit
**Scope:** All source files in `src/`, `pipelines/`, `trigger-jobs/`, `n8n/`, `supabase/`, `posthog/`, `experimentation/`, `dashboard/`, `emails/`, `demo/`, `notebooks/`, plus `docker-compose.yml`, `vercel.json`, `Makefile`, `.env.example`, `requirements.txt`, `.gitignore`

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 4     |
| HIGH     | 8     |
| MEDIUM   | 8     |
| LOW      | 5     |
| **Total** | **25** |

---

## 1. Hardcoded Secrets and API Keys

### FINDING 1.1 -- Hardcoded PostgreSQL Password in Docker Compose

- **Severity:** CRITICAL
- **File:** `docker-compose.yml`, lines 25-27
- **Description:** The PostgreSQL password is hardcoded as the literal string `password`. While this is a local development file, these credentials are often copy-pasted into staging or production environments, and the same password appears in multiple locations across the project (Makefile, n8n workflows, docker-compose comments).
- **Code Evidence:**
  ```yaml
  POSTGRES_USER: engagement
  POSTGRES_PASSWORD: password
  POSTGRES_DB: engagement
  ```
- **Fix:** Use environment variable substitution in docker-compose.yml:
  ```yaml
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme_dev_only}
  ```
  Require `.env` file for local development and document that production must override all defaults.

---

### FINDING 1.2 -- Hardcoded Redis Password in Docker Compose

- **Severity:** CRITICAL
- **File:** `docker-compose.yml`, line 48
- **Description:** The Redis password is hardcoded as `password` in the server start command.
- **Code Evidence:**
  ```yaml
  command: redis-server --appendonly yes --requirepass "password"
  ```
- **Fix:** Use environment variable:
  ```yaml
  command: redis-server --appendonly yes --requirepass "${REDIS_PASSWORD:-changeme_dev_only}"
  ```

---

### FINDING 1.3 -- Hardcoded Database Connection Strings in n8n Workflows

- **Severity:** HIGH
- **File:** `n8n/notification_orchestration.json`, lines 25, 41, 112
- **File:** `n8n/cohort_recalculation.json`, lines 23, 66, 82, 98, 143
- **Description:** Multiple n8n workflow nodes contain the hardcoded connection string `postgres://user:pass@localhost/engagement_engine`. Even though these use n8n credentials references (`postgresCredential`), the `url` parameter also embeds credentials in plaintext, which will appear in n8n execution logs and workflow exports.
- **Code Evidence (notification_orchestration.json, line 25):**
  ```json
  "url": "=postgres://user:pass@localhost/engagement_engine"
  ```
- **Fix:** Remove the `url` parameter from all n8n Postgres nodes. Rely exclusively on the `credentials` reference (`postgresCredential: supabase_engagement_db`) which stores the connection string encrypted in n8n's credential store.

---

### FINDING 1.4 -- Plaintext Password Printed in Makefile

- **Severity:** MEDIUM
- **File:** `Makefile`, line 88
- **Description:** The `docker-up` target echoes the PostgreSQL password in plaintext to the terminal, which may be captured in CI/CD logs or shell history.
- **Code Evidence:**
  ```makefile
  @echo "  - PostgreSQL: localhost:5432 (user: engagement, password: password)"
  ```
- **Fix:** Remove the password from the echo statement:
  ```makefile
  @echo "  - PostgreSQL: localhost:5432 (user: engagement, see .env for password)"
  ```

---

### FINDING 1.5 -- Docker Compose Comment Embeds Credentials

- **Severity:** LOW
- **File:** `docker-compose.yml`, lines 13, 130-131
- **Description:** Comments in docker-compose.yml contain full connection strings with embedded passwords: `user: engagement, password: password` and `redis://:password@redis:6379`.
- **Code Evidence:**
  ```yaml
  #   PostgreSQL: localhost:5432 (user: engagement, password: password, db: engagement)
  #     REDIS_URL: redis://:password@redis:6379
  #     POSTGRES_URL: postgresql://engagement:password@postgres:5432/engagement
  ```
- **Fix:** Replace inline credentials in comments with references to `.env` file.

---

## 2. Authentication Vulnerabilities and Missing Auth

### FINDING 2.1 -- No Authentication on Webhook Endpoints

- **Severity:** CRITICAL
- **File:** `pipelines/segment_receiver.py`, lines 99-103, 106, 183, 249
- **Description:** The FastAPI application exposes three data-ingestion endpoints (`/segment/track`, `/segment/identify`, `/segment/batch`) with zero authentication. Any internet-accessible attacker can submit arbitrary events, inject fake user profiles, and pollute the data pipeline. Segment webhooks should be authenticated using a shared secret or signature verification.
- **Code Evidence:**
  ```python
  app = FastAPI(
      title="Segment Event Receiver",
      description="Webhook receiver for Segment events with validation and routing",
      version="1.0.0"
  )

  @app.post("/segment/track")
  async def receive_track_event(event: TrackEvent) -> Dict[str, Any]:
  ```
- **Fix:** Implement Segment webhook signature verification:
  ```python
  from fastapi import Depends, Header

  async def verify_segment_signature(
      request: Request,
      x_signature: str = Header(..., alias="x-signature")
  ):
      body = await request.body()
      expected = hmac.new(
          SEGMENT_SHARED_SECRET.encode(),
          body,
          hashlib.sha1
      ).hexdigest()
      if not hmac.compare_digest(expected, x_signature):
          raise HTTPException(status_code=401, detail="Invalid signature")
  ```
  Apply as a dependency to all `/segment/*` routes.

---

### FINDING 2.2 -- Metrics Endpoint Exposed Without Authentication

- **Severity:** MEDIUM
- **File:** `pipelines/segment_receiver.py`, lines 308-325
- **Description:** The `/metrics` endpoint is publicly accessible. In production, metrics endpoints can reveal system internals (event counts, error rates, latencies) that aid reconnaissance.
- **Code Evidence:**
  ```python
  @app.get("/metrics")
  async def metrics() -> Dict[str, Any]:
  ```
- **Fix:** Protect metrics endpoint with a bearer token or restrict to internal network via middleware. Alternatively, serve metrics on a separate internal-only port.

---

### FINDING 2.3 -- Trigger.dev Jobs Use Anon Key Instead of Service Role Key

- **Severity:** HIGH
- **File:** `trigger-jobs/engagement_scoring.ts`, line 23
- **File:** `trigger-jobs/recommendation_generation.ts`, line 21
- **Description:** Both Trigger.dev background jobs initialize the Supabase client with `SUPABASE_KEY` (the anonymous/public key) rather than `SUPABASE_SERVICE_ROLE_KEY`. The anon key is subject to Row Level Security (RLS) policies, which will cause server-side batch operations to silently return empty results or fail, since there is no authenticated user context in a background job.
- **Code Evidence (engagement_scoring.ts, line 23):**
  ```typescript
  const supabase = createClient(process.env.SUPABASE_URL || '', process.env.SUPABASE_KEY || '');
  ```
- **Fix:** Use the service role key for server-side operations that need to bypass RLS:
  ```typescript
  const supabase = createClient(
    process.env.SUPABASE_URL || '',
    process.env.SUPABASE_SERVICE_ROLE_KEY || ''
  );
  ```
  Ensure `SUPABASE_SERVICE_ROLE_KEY` is stored as a secret in Trigger.dev environment variables and never exposed client-side.

---

### FINDING 2.4 -- Unauthenticated HTTP Request in Engagement Scoring Job

- **Severity:** HIGH
- **File:** `trigger-jobs/engagement_scoring.ts`, lines 307-324
- **Description:** The `detectTransitions` function makes an HTTP POST to `${process.env.API_URL}/api/events` without any Authorization header. If the API requires authentication, this call will silently fail. If the API does not require authentication, this is an additional unauthenticated endpoint.
- **Code Evidence:**
  ```typescript
  await fetch(`${process.env.API_URL}/api/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      event: 'cohort_transition',
      user_id: userId,
      // ...
    }),
  });
  ```
- **Fix:** Add an Authorization header with a service-to-service API key or JWT:
  ```typescript
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${process.env.API_SECRET}`
  },
  ```

---

### FINDING 2.5 -- Kafka UI Exposed Without Authentication

- **Severity:** HIGH
- **File:** `docker-compose.yml`, lines 104-116
- **Description:** Kafka UI is exposed on port 8080 with no authentication configured. Anyone on the network can browse topics, view messages (which may contain PII), and modify configurations.
- **Code Evidence:**
  ```yaml
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    ports:
      - "8080:8080"
  ```
- **Fix:** Add basic authentication to Kafka UI:
  ```yaml
  environment:
    AUTH_TYPE: LOGIN_FORM
    SPRING_SECURITY_USER_NAME: ${KAFKA_UI_USER:-admin}
    SPRING_SECURITY_USER_PASSWORD: ${KAFKA_UI_PASSWORD}
  ```
  For local development, bind to `127.0.0.1:8080:8080` to prevent network exposure.

---

## 3. Input Validation Issues

### FINDING 3.1 -- Batch Endpoint Accepts Untyped Dict Payloads

- **Severity:** HIGH
- **File:** `pipelines/segment_receiver.py`, lines 89-91
- **Description:** The `SegmentBatch` model accepts `batch: List[Dict[str, Any]]` with no schema validation on individual items. While items are later parsed into `TrackEvent` or `IdentifyEvent`, the initial acceptance of arbitrary dicts means oversized payloads, deeply nested objects, or malformed data can reach the application layer before validation.
- **Code Evidence:**
  ```python
  class SegmentBatch(BaseModel):
      """Segment batch API payload."""
      batch: List[Dict[str, Any]]
      timestamp: datetime = Field(default_factory=datetime.utcnow)
  ```
- **Fix:** Add size constraints and use a discriminated union type:
  ```python
  from pydantic import conlist
  from typing import Union, Literal

  class BatchTrackItem(TrackEvent):
      type: Literal["track"]

  class BatchIdentifyItem(IdentifyEvent):
      type: Literal["identify"]

  class SegmentBatch(BaseModel):
      batch: conlist(Union[BatchTrackItem, BatchIdentifyItem], max_length=32)
  ```

---

### FINDING 3.2 -- Weak Hash Function for Experiment Assignment

- **Severity:** MEDIUM
- **File:** `posthog/experiments.ts`, lines 571-574
- **Description:** The `assignVariant` function uses a simple character code accumulation hash (`(acc << 5) - acc + charCode`) instead of a cryptographic or well-distributed hash function. This can produce biased bucket distribution, leading to statistically invalid experiment results.
- **Code Evidence:**
  ```typescript
  const hash = Array.from(combined).reduce((acc, char) => {
    return (acc << 5) - acc + char.charCodeAt(0);
  }, 0);
  ```
- **Fix:** Use a proper hash function such as MurmurHash3 or SHA-256 (as already done in `src/experiments/experiment_framework.py`):
  ```typescript
  import { createHash } from 'crypto';
  const hash = parseInt(
    createHash('sha256').update(combined).digest('hex').substring(0, 8),
    16
  );
  ```

---

### FINDING 3.3 -- No Request Size Limits on FastAPI App

- **Severity:** MEDIUM
- **File:** `pipelines/segment_receiver.py`, lines 99-103
- **Description:** The FastAPI app does not configure any request body size limits. An attacker could send multi-gigabyte payloads to exhaust memory and crash the service.
- **Fix:** Add request size limits via middleware or reverse proxy configuration:
  ```python
  from starlette.middleware.trustedhost import TrustedHostMiddleware

  app = FastAPI(...)

  @app.middleware("http")
  async def limit_request_size(request: Request, call_next):
      content_length = request.headers.get("content-length")
      if content_length and int(content_length) > 1_000_000:  # 1MB
          raise HTTPException(status_code=413, detail="Request too large")
      return await call_next(request)
  ```

---

## 4. Customer PII Handling and Exposure

### FINDING 4.1 -- User ID Logged and Returned in API Responses

- **Severity:** MEDIUM
- **File:** `pipelines/segment_receiver.py`, lines 124, 172, 200, 237
- **Description:** User IDs are logged in plaintext and returned in API responses. If user IDs are PII-adjacent (e.g., email-based or sequential), this leaks user information in logs and to callers.
- **Code Evidence:**
  ```python
  logger.info(f"Track event received: {event.event} from {event.user_id}")
  # ...
  return {
      "status": "success",
      "segment_id": enriched_event['segment_id'],
      "event_type": event.event,
      "user_id": event.user_id
  }
  ```
- **Fix:** Hash or truncate user IDs in log output. Remove `user_id` from API responses (the caller already knows it):
  ```python
  logger.info(f"Track event received: {event.event} from user {hash(event.user_id) % 10000}")
  return {"status": "success", "segment_id": enriched_event['segment_id'], "event_type": event.event}
  ```

---

### FINDING 4.2 -- IP Address Captured and Stored in Enriched Events

- **Severity:** MEDIUM
- **File:** `pipelines/segment_receiver.py`, lines 143, 159, 345
- **Description:** Client IP addresses are extracted from the event context and from `request.client.host`, then stored in the enriched event payload. IP addresses are classified as personal data under GDPR and require explicit legal basis for processing and storage.
- **Code Evidence:**
  ```python
  ip_address = event.context.get('ip')
  # ...
  enriched_event = {
      # ...
      'ip_address': ip_address,
  }
  ```
  ```python
  def enrich_event_context(request: Request, event: TrackEvent) -> Dict[str, Any]:
      return {
          'ip_address': request.client.host,
          # ...
      }
  ```
- **Fix:** Remove IP address storage unless there is a documented legal basis. If needed for geo-resolution, resolve to country/region at ingestion time and discard the raw IP:
  ```python
  enriched_event = {
      # ...
      'geo_region': resolve_ip_to_region(ip_address),  # Store region, not IP
  }
  ```

---

### FINDING 4.3 -- Email Stored as Online-Serving Feature in Feast

- **Severity:** HIGH
- **File:** `pipelines/feast_features.py`, lines 226-228
- **Description:** The user's email address is defined as a feature in the `user_profile` FeatureView with `online=True`. This means emails are materialized into Redis for real-time serving. Redis is typically not encrypted at rest, and email as a feature is accessible to any service that can query the online store, expanding the PII blast radius.
- **Code Evidence:**
  ```python
  user_profile_view = FeatureView(
      name="user_profile",
      # ...
      online=True,
      features=[
          Field(name="email", dtype=String,
                description="User email address"),
  ```
- **Fix:** Remove email from the online feature store. Email should be fetched directly from the primary database when needed, not cached in Redis:
  ```python
  features=[
      # Removed: Field(name="email", ...) -- PII should not be in feature store
      Field(name="lifecycle_stage", dtype=String, ...),
  ```

---

### FINDING 4.4 -- Email Used Directly in n8n Notification Template Body

- **Severity:** MEDIUM
- **File:** `n8n/notification_orchestration.json`, line 98
- **Description:** The re-engagement email body template includes the user's email address as a greeting: `Hi {{ $node["Fetch User Profile"].json[0].email }}`. This is a minor PII concern, but the bigger risk is that the n8n execution logs will store the rendered email body (containing the email address) in plaintext.
- **Code Evidence:**
  ```json
  "<p>Hi {{ $node[\"Fetch User Profile\"].json[0].email }},</p>"
  ```
- **Fix:** Use the user's display name instead of email for greetings. If name is unavailable, use a generic greeting.

---

### FINDING 4.5 -- At-Risk User Query Selects Email

- **Severity:** MEDIUM
- **File:** `n8n/cohort_recalculation.json`, line 100
- **Description:** The "Identify At-Risk Users" query selects `u.email` alongside engagement data. This email is then passed to downstream workflow nodes and potentially logged.
- **Code Evidence:**
  ```sql
  SELECT u.id, u.user_id, u.email, u.engagement_score, u.behavioral_cohort, u.engagement_tier
  FROM users u
  WHERE ...
  ```
- **Fix:** Remove `u.email` from this query. The notification orchestration workflow can fetch email only when needed, minimizing PII propagation:
  ```sql
  SELECT u.id, u.user_id, u.engagement_score, u.behavioral_cohort, u.engagement_tier
  ```

---

## 5. API Security (Rate Limiting, CORS)

### FINDING 5.1 -- Rate Limiting Is Commented Out

- **Severity:** CRITICAL
- **File:** `pipelines/segment_receiver.py`, lines 147-149
- **Description:** Rate limiting logic exists only as commented-out pseudocode. Without rate limiting, the API is vulnerable to abuse, including event flooding that could exhaust downstream resources (Kafka, PostgreSQL, Redis).
- **Code Evidence:**
  ```python
  # Rate limiting (in production, would check Redis)
  # user_events_per_minute = await rate_limiter.check(event.user_id)
  # if user_events_per_minute > 1000:
  #     raise HTTPException(status_code=429, detail="Rate limit exceeded")
  ```
- **Fix:** Implement rate limiting using `slowapi` or a Redis-based limiter:
  ```python
  from slowapi import Limiter
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter

  @app.post("/segment/track")
  @limiter.limit("100/minute")
  async def receive_track_event(request: Request, event: TrackEvent):
  ```

---

### FINDING 5.2 -- No CORS Middleware Configured

- **Severity:** HIGH
- **File:** `pipelines/segment_receiver.py`, lines 99-103
- **Description:** The FastAPI app has no CORS middleware. If the API is called from browser-based clients, the absence of CORS headers means either all origins are implicitly blocked (if the browser enforces it) or the API provides no cross-origin protection. Additionally, without explicit CORS configuration, a future developer might disable the browser's default protections.
- **Fix:** Add explicit CORS middleware:
  ```python
  from fastapi.middleware.cors import CORSMiddleware

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://app.example.com"],
      allow_methods=["POST"],
      allow_headers=["Content-Type", "Authorization"],
  )
  ```

---

## 6. Infrastructure Misconfigurations

### FINDING 6.1 -- All Service Ports Bound to 0.0.0.0

- **Severity:** HIGH
- **File:** `docker-compose.yml`, lines 30, 50, 71, 89-90, 114
- **Description:** Every service binds to all network interfaces: PostgreSQL (5432), Redis (6379), Zookeeper (2181), Kafka (9092, 29092), and Kafka UI (8080). On a developer machine with a public IP or shared network, these services are accessible to anyone on the network.
- **Code Evidence:**
  ```yaml
  ports:
    - "5432:5432"   # PostgreSQL
    - "6379:6379"   # Redis
    - "2181:2181"   # Zookeeper
    - "9092:9092"   # Kafka
    - "8080:8080"   # Kafka UI
  ```
- **Fix:** Bind to localhost for local development:
  ```yaml
  ports:
    - "127.0.0.1:5432:5432"
    - "127.0.0.1:6379:6379"
    - "127.0.0.1:2181:2181"
    - "127.0.0.1:9092:9092"
    - "127.0.0.1:8080:8080"
  ```

---

### FINDING 6.2 -- Redis Health Check Does Not Use Password

- **Severity:** LOW
- **File:** `docker-compose.yml`, lines 53-54
- **Description:** Redis is configured with `--requirepass "password"`, but the health check uses `redis-cli ping` without authentication. This means the health check will fail with `NOAUTH Authentication required`, potentially causing Docker to restart the container in a loop.
- **Code Evidence:**
  ```yaml
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
  ```
- **Fix:**
  ```yaml
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-password}", "ping"]
  ```

---

### FINDING 6.3 -- Kafka Auto-Create Topics Enabled

- **Severity:** LOW
- **File:** `docker-compose.yml`, line 87
- **Description:** `KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"` allows any producer to create topics by publishing to a non-existent topic name. In production, this can lead to topic sprawl, naming inconsistencies, and misconfigured partition counts.
- **Code Evidence:**
  ```yaml
  KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
  ```
- **Fix:** Disable auto-create in production and pre-create topics with proper partition and replication settings. Keep enabled only in local dev if desired, with a clear comment.

---

### FINDING 6.4 -- No Resource Limits on Docker Services

- **Severity:** LOW
- **File:** `docker-compose.yml` (entire file)
- **Description:** No CPU or memory limits are set for any container. A runaway process (e.g., Kafka or PostgreSQL under load) can consume all host resources, affecting other services and the host system.
- **Fix:** Add resource limits (as noted in the file's own comments at lines 186-194):
  ```yaml
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
  ```

---

### FINDING 6.5 -- No TLS/SSL Configured for Any Service

- **Severity:** HIGH
- **File:** `docker-compose.yml` (entire file)
- **Description:** PostgreSQL, Redis, and Kafka all communicate over unencrypted connections. Data in transit (including credentials, PII, and event payloads) is transmitted in plaintext. Kafka listeners are explicitly configured as `PLAINTEXT`.
- **Code Evidence:**
  ```yaml
  KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
  ```
- **Fix:** For production deployments, configure TLS for all services. For Kafka, use `SSL` or `SASL_SSL` protocol. For PostgreSQL, enable `ssl = on` in the server config. For Redis, use `redis-server --tls-port 6380 --tls-cert-file ...`.

---

### FINDING 6.6 -- Missing Security Headers in Vercel Configuration

- **Severity:** MEDIUM
- **File:** `vercel.json`, lines 65-83
- **Description:** The Vercel configuration sets `X-Content-Type-Options`, `X-Frame-Options`, and `X-XSS-Protection` headers, which is good. However, two critical security headers are missing: `Content-Security-Policy` (CSP) and `Strict-Transport-Security` (HSTS).
- **Code Evidence:**
  ```json
  "headers": [
    {
      "source": "/:path*",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ]
  ```
- **Fix:** Add CSP and HSTS headers:
  ```json
  { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://app.posthog.com https://*.supabase.co" },
  { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains; preload" },
  { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
  { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
  ```

---

## 7. Dependency Vulnerabilities

### FINDING 7.1 -- Using Unmaintained kafka-python Library

- **Severity:** MEDIUM
- **File:** `requirements.txt`, line 33
- **Description:** The project depends on `kafka-python==2.0.2`. The `kafka-python` library has been unmaintained since 2020 and has known issues including a lack of security patches. The project also includes `confluent-kafka==2.3.0`, which is the actively maintained alternative.
- **Code Evidence:**
  ```
  kafka-python==2.0.2
  ```
- **Fix:** Remove `kafka-python` and use `confluent-kafka` exclusively:
  ```
  # Remove: kafka-python==2.0.2
  confluent-kafka==2.3.0
  ```

---

### FINDING 7.2 -- No Dependency Hash Verification

- **Severity:** LOW
- **File:** `requirements.txt` (entire file)
- **Description:** Dependencies are pinned by version but do not include hash verification (`--hash`). This means a supply chain attack (compromised PyPI package) would not be detected during installation.
- **Fix:** Generate hashes with `pip-compile --generate-hashes` or use `pip install --require-hashes -r requirements.txt`.

---

## 8. Additional Security Concerns

### FINDING 8.1 -- Overlapping RLS Policies on Users Table

- **Severity:** LOW
- **File:** `supabase/migrations/001_initial_schema.sql`, lines 216-227
- **Description:** Two overlapping SELECT policies exist on the `users` table. The first policy (line 216-218) already grants `product_team` access via `auth.jwt() ->> 'role' = 'product_team'`. The second policy (lines 225-227) grants the same access again. PostgreSQL RLS policies are combined with OR logic, so the duplicate is harmless but creates maintenance confusion and makes it unclear what the intended access model is.
- **Code Evidence:**
  ```sql
  -- Policy 1 (line 216-218)
  CREATE POLICY "Users can view their own profile"
    ON users FOR SELECT
    USING (auth.uid()::text = user_id OR auth.jwt() ->> 'role' = 'admin' OR auth.jwt() ->> 'role' = 'product_team');

  -- Policy 2 (lines 225-227) -- DUPLICATE
  CREATE POLICY "Product team can view aggregated stats"
    ON users FOR SELECT
    USING (auth.jwt() ->> 'role' = 'product_team');
  ```
- **Fix:** Remove the duplicate policy or differentiate them. If the intent is to restrict product_team to aggregated data (no individual emails), implement that via a separate view rather than a duplicate SELECT policy on the base table.

---

## Recommendations Summary

### Immediate Actions (Critical/High)

1. **Add webhook authentication** to `segment_receiver.py` using Segment signature verification
2. **Implement rate limiting** on all API endpoints
3. **Replace SUPABASE_KEY with SUPABASE_SERVICE_ROLE_KEY** in both Trigger.dev jobs
4. **Remove hardcoded credentials** from docker-compose.yml and n8n workflows; use environment variable substitution
5. **Bind Docker ports to 127.0.0.1** for local development
6. **Remove email from Feast online feature store** to reduce PII exposure
7. **Add CORS middleware** to the FastAPI application
8. **Add authentication to Kafka UI** and the `/metrics` endpoint
9. **Configure TLS** for all services in production deployments
10. **Add Authorization headers** to service-to-service HTTP calls

### Short-Term Improvements (Medium)

1. Add `Content-Security-Policy` and `Strict-Transport-Security` headers to Vercel config
2. Replace weak hash in PostHog experiment assignment with SHA-256
3. Add request body size limits to FastAPI
4. Stop logging raw user IDs; use hashed identifiers in logs
5. Remove IP address storage or implement proper GDPR-compliant handling
6. Remove email column from n8n at-risk user query
7. Remove `kafka-python` dependency in favor of `confluent-kafka`
8. Use typed discriminated unions for batch endpoint validation

### Long-Term Improvements (Low)

1. Enable dependency hash verification in requirements.txt
2. Clean up duplicate RLS policies
3. Add resource limits to Docker containers
4. Disable Kafka auto-create topics in staging/production
5. Fix Redis health check to include password authentication
