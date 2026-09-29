"""Generate 40 synthetic resolved incidents using templates.

Run:  python data/generate_incidents.py
Output: data/incidents_seed.json

Deterministic output via random.seed(42).
Does NOT include the three demo incidents from Section 12.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)

SERVICES = [
    "payments-api",
    "auth-service",
    "order-service",
    "inventory-service",
    "notification-service",
    "search-service",
]

# 8 root-cause families × 5 incidents each = 40
# Each family maps to (name, root_cause_template, fix_steps, base_res_minutes)
FAMILIES = [
    {
        "name": "db_pool_exhaustion",
        "severities": ["SEV1", "SEV1", "SEV2", "SEV2", "SEV2"],
        "title_templates": [
            "{service} — HikariPool connection timeout causing 5xx flood",
            "{service} — DB connection pool saturated, requests queuing",
            "{service} — connection pool limit reached, elevated latency",
            "{service} — JDBC connection exhaustion on peak traffic",
            "{service} — connection-not-available errors spiking",
        ],
        "symptom_templates": [
            "5xx error rate climbed to 40%. HikariPool-1 timeout errors in logs.",
            "P99 latency exceeded 20 s. Connection pool wait queue backed up.",
            "Requests timing out after 30 s. DB connections at max.",
            "Dashboard showed DB errors. All pool slots occupied.",
            "On-call alerted by PagerDuty: 503s from {service}.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:12.345Z ERROR HikariPool-1"
                " — Connection is not available, request timed out after 30000ms\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:12.350Z ERROR"
                " com.zaxxer.hikari.pool.HikariPool — HikariPool-1 — Exception during pool initialization.\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:12.400Z WARN"
                " {pod} — Pool size: 20/20 active connections\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:13.001Z ERROR"
                " {pod} — org.postgresql.util.PSQLException: FATAL: sorry, too many clients already\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z ERROR"
                " {pod} — Timeout waiting for connection from pool\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z ERROR"
                " {pod} — Active pool connections: 20, pending: 47\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z WARN"
                " {pod} — HikariCP pool {service}-pool exhausted\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:07Z ERROR"
                " {pod} — java.sql.SQLException: Timeout: Pool empty, cannot acquire connection\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:08Z ERROR"
                " {pod} — max_connections=20 reached on db-primary\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:15Z ERROR"
                " {pod} — [ERROR] HikariPool-2 - Connection is not available\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:16Z ERROR"
                " {pod} — Caused by: PSQLException: FATAL: remaining connection slots are reserved\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:22Z WARN"
                " {pod} — Connection pool at 100% utilisation\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:23Z ERROR"
                " {pod} — Unable to acquire JDBC Connection\n"
            ),
        ],
        "root_cause": "DB connection pool exhausted after traffic spike",
        "fix_steps": [
            "Increase connection pool size to 50 in application config",
            "Restart {service} pods to apply new pool settings",
            "Add pool-timeout alert at 80% utilisation threshold",
            "Implement connection pool monitoring dashboard",
        ],
        "base_minutes": [58, 52, 30, 22, 18],
    },
    {
        "name": "redis_oom",
        "severities": ["SEV2", "SEV1", "SEV2", "SEV2", "SEV3"],
        "title_templates": [
            "{service} — Redis OOM errors causing cache write failures",
            "{service} — Redis maxmemory exceeded, key eviction storm",
            "{service} — Redis OOM command not allowed, login failures",
            "{service} — cache eviction causing thundering-herd on DB",
            "{service} — Redis memory full, session data lost",
        ],
        "symptom_templates": [
            "Redis OOM command not allowed when used memory > 'maxmemory' errors in logs.",
            "Cache miss rate jumped to 95%. DB load tripled.",
            "User sessions expiring immediately. Redis memory at limit.",
            "Random login failures. Redis evicting session keys aggressively.",
            "High error rate from {service}. Redis memory graphs maxed out.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:05Z ERROR"
                " {pod} — OOM command not allowed when used memory > 'maxmemory'\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:05Z ERROR"
                " {pod} — redis.clients.jedis.exceptions.JedisDataException: OOM\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:06Z WARN"
                " {pod} — Redis used_memory: 3.9GB / maxmemory: 4GB\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — COMMAND OOM: used_memory 4294967296 maxmemory 4294967296\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z WARN"
                " {pod} — Eviction policy: noeviction — refusing writes\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:33Z ERROR"
                " {pod} — RedisCommandExecutionException: OOM command not allowed\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:34Z ERROR"
                " {pod} — Session store write failed: Redis out of memory\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:44Z WARN"
                " {pod} — redis evicted 50000 keys in last 60s\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:45Z ERROR"
                " {pod} — Cache stampede detected, DB connections spiking\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:55Z ERROR"
                " {pod} — redis: ERR OOM — used memory 100% of maxmemory\n"
            ),
        ],
        "root_cause": "Redis maxmemory limit reached; noeviction policy blocking all writes",
        "fix_steps": [
            "Raise Redis maxmemory to 8 GB on cache-cluster-01",
            "Set eviction policy to allkeys-lru",
            "Flush stale session keys older than 7 days",
            "Add Redis memory utilisation alert at 75%",
        ],
        "base_minutes": [65, 50, 28, 24, 15],
    },
    {
        "name": "tls_cert_expired",
        "severities": ["SEV1", "SEV1", "SEV2", "SEV2", "SEV3"],
        "title_templates": [
            "{service} — TLS certificate expired, HTTPS handshake failures",
            "{service} — SSL cert expired causing client connection errors",
            "{service} — certificate validity expired, 525 errors from CDN",
            "{service} — mTLS cert expired, internal service auth broken",
            "{service} — TLS handshake error due to expired certificate",
        ],
        "symptom_templates": [
            "Clients reporting SSL_ERROR_RX_RECORD_TOO_LONG. Certificate expired.",
            "HTTPS connections refused. Certificate expired yesterday.",
            "CDN returning 525 SSL Handshake Failed errors. Cert expired.",
            "Internal service-to-service calls failing with handshake timeout.",
            "Browser console shows NET::ERR_CERT_DATE_INVALID for {service}.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z ERROR"
                " {pod} — SSL routines:ssl3_read_bytes:sslv3 alert certificate expired\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z ERROR"
                " {pod} — Certificate expired at 2025-{month:02d}-{day:02d}T00:00:00Z\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z WARN"
                " nginx — upstream SSL certificate verify error: (10:certificate has expired)\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — certificate verify failed: certificate has expired (_ssl.c:1129)\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z ERROR"
                " ingress — SSL_CTX_use_certificate: error:0200100D\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:20Z WARN"
                " {pod} — TLS handshake failed: certificate expired\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:21Z ERROR"
                " {pod} — x509: certificate has expired or is not yet valid\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:30Z ERROR"
                " ingress-nginx — upstream timed out (110: Connection timed out) certificate expired\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:40Z ERROR"
                " {pod} — TLS: remote error: tls: certificate expired\n"
            ),
        ],
        "root_cause": "TLS certificate for the service endpoint expired without automated renewal",
        "fix_steps": [
            "Renew TLS certificate via cert-manager / Let's Encrypt",
            "Reload ingress controller to pick up new certificate",
            "Verify certificate validity with: openssl s_client -connect {service}:443",
            "Add certificate expiry monitor alerting 30 days before expiry",
        ],
        "base_minutes": [45, 40, 25, 20, 15],
    },
    {
        "name": "bad_deploy",
        "severities": ["SEV1", "SEV2", "SEV2", "SEV3", "SEV3"],
        "title_templates": [
            "{service} — bad deploy introduced env var misconfiguration",
            "{service} — broken config in release v{ver} causing start-up failures",
            "{service} — rollout introduced null-pointer crash on startup",
            "{service} — misconfigured feature flag causing request routing errors",
            "{service} — wrong DB URL in new config map causing connection refusals",
        ],
        "symptom_templates": [
            "Pods crashing on startup after release. CrashLoopBackOff observed.",
            "Error rate spiked immediately after deploy. Rollback candidate.",
            "NullPointerException on every request after upgrade.",
            "Feature flag misconfiguration routing traffic to wrong endpoint.",
            "DB connection refused errors after config map update.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z ERROR"
                " {pod} — Failed to initialise application context\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z ERROR"
                " {pod} — Caused by: IllegalArgumentException: Could not resolve placeholder 'DB_HOST'\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z WARN"
                " k8s — Pod {pod} restarting (CrashLoopBackOff) — restarts: 5\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:05Z ERROR"
                " {pod} — java.lang.NullPointerException at Config.load(Config.java:42)\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:06Z ERROR"
                " {pod} — APPLICATION FAILED TO START: env var REDIS_URL not found\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — OCI runtime error: env var KAFKA_BROKERS missing\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z WARN"
                " argocd — Rollout {service}-v{ver} degraded\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:15Z ERROR"
                " {pod} — Feature flag client: config parse error at line 7\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:20Z ERROR"
                " {pod} — psycopg2.OperationalError: could not connect to server: Connection refused\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:21Z ERROR"
                " {pod} — DB_HOST=localhost but expected postgres-primary.internal\n"
            ),
        ],
        "root_cause": "Bad deploy: missing or incorrect env var introduced in config map",
        "fix_steps": [
            "Rollback to previous release using: kubectl rollout undo deploy/{service}",
            "Correct the environment variable in the config map",
            "Redeploy with validated config",
            "Add config validation step to CI pipeline",
        ],
        "base_minutes": [40, 35, 25, 15, 12],
    },
    {
        "name": "kafka_consumer_lag",
        "severities": ["SEV2", "SEV2", "SEV2", "SEV3", "SEV3"],
        "title_templates": [
            "{service} — Kafka consumer lag growing, messages backing up",
            "{service} — consumer group stalled, partition offset stuck",
            "{service} — Kafka lag caused by slow downstream DB writes",
            "{service} — message processing delay affecting downstream {svc2}",
            "{service} — Kafka partition rebalance storm causing consumer lag",
        ],
        "symptom_templates": [
            "Consumer lag on topic orders-events exceeded 500k messages.",
            "Kafka partition offset stuck, consumers not advancing.",
            "Downstream DB latency causing Kafka consumer to fall behind.",
            "Messages delayed 45 minutes causing SLA breach.",
            "Consumer group rebalancing every 30 s due to slow consumer.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z WARN"
                " {pod} — consumer-group={service}-cg lag=523441 topic=orders-events\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z WARN"
                " {pod} — Commit offset failed: org.apache.kafka.clients.consumer.CommitFailedException\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z INFO"
                " kafka — Group {service}-cg is rebalancing\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — Offset commit failed after 3 retries; partition 4 stuck\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z WARN"
                " {pod} — Consumer poll records=0 — possible broker timeout\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:20Z WARN"
                " {pod} — max.poll.interval.ms exceeded; consumer kicked out of group\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:21Z ERROR"
                " {pod} — Rebalance loop detected; consumer lag=128000\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:30Z WARN"
                " {pod} — Slow message processing: 8200ms per message\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:31Z ERROR"
                " {pod} — DB write latency 7500ms causing consumer timeout\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:40Z ERROR"
                " {pod} — kafka.common.LeaderNotAvailableException partition=7\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:41Z WARN"
                " {pod} — Consumer lag=89000 and growing\n"
            ),
        ],
        "root_cause": "Kafka consumer group fell behind due to slow processing; stuck partition offset",
        "fix_steps": [
            "Scale {service} consumer pods from 2 to 6",
            "Reset stuck partition offset: kafka-consumer-groups.sh --reset-offsets",
            "Identify and fix slow downstream DB query causing processing delay",
            "Add consumer lag alert at 10k messages threshold",
        ],
        "base_minutes": [60, 45, 30, 20, 15],
    },
    {
        "name": "disk_full",
        "severities": ["SEV2", "SEV2", "SEV2", "SEV3", "SEV3"],
        "title_templates": [
            "{service} — disk full from log growth, writes failing",
            "{service} — filesystem 100% full causing application errors",
            "{service} — log rotation misconfiguration filling disk",
            "{service} — temp files filling /var/log causing write errors",
            "{service} — PV (persistent volume) full causing data loss risk",
        ],
        "symptom_templates": [
            "Application throwing 'No space left on device' errors.",
            "Write operations failing. df -h shows /var/log at 100%.",
            "Log files not rotating. Disk full on node-03.",
            "/tmp filesystem exhausted by core dumps.",
            "PersistentVolume at 100% utilisation. Data writes rejected.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z ERROR"
                " {pod} — IOException: No space left on device\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z ERROR"
                " {pod} — Failed to write log: /var/log/{service}/app.log\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z WARN"
                " node-agent — node-03 disk usage: 100% on /var/log\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:05Z ERROR"
                " {pod} — OSError: [Errno 28] No space left on device: '/tmp/upload'\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:06Z WARN"
                " {pod} — Disk /dev/sda1 at 99.8% — write buffer flushing\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — logrotate: error: stat of /var/log/{service}/*.log failed: No such file\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z WARN"
                " {pod} — Log rotation SKIPPED: disk quota exceeded\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:15Z ERROR"
                " {pod} — core dumped: write failed (device full)\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:16Z WARN"
                " node — /tmp usage: 32GB/32GB (100%)\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:20Z ERROR"
                " {pod} — PVC {service}-pv: no free blocks\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:21Z WARN"
                " kubelet — PV disk usage at 100%: {service}-data-pvc\n"
            ),
        ],
        "root_cause": "Disk full due to log file accumulation without proper rotation",
        "fix_steps": [
            "Rotate and purge logs older than 7 days: find /var/log -name '*.log' -mtime +7 -delete",
            "Free space immediately: rm -rf /var/log/{service}/old-*.log",
            "Resize the volume if disk growth is structural",
            "Add disk usage alert at 80% threshold",
        ],
        "base_minutes": [55, 40, 25, 20, 15],
    },
    {
        "name": "dns_failure",
        "severities": ["SEV1", "SEV2", "SEV2", "SEV3", "SEV3"],
        "title_templates": [
            "{service} — DNS resolution failures causing upstream timeouts",
            "{service} — CoreDNS crash causing name resolution failures",
            "{service} — intermittent DNS NXDOMAIN for internal service",
            "{service} — DNS cache poisoning causing wrong IP resolution",
            "{service} — DNS search domain misconfiguration in pod spec",
        ],
        "symptom_templates": [
            "Service-to-service calls failing with 'dial tcp: no such host'.",
            "CoreDNS pods crashing. kubectl get pods -n kube-system shows CrashLoopBackOff.",
            "Intermittent NXDOMAIN responses for internal service names.",
            "Wrong IP resolved for database endpoint after DNS update.",
            "Pod unable to resolve {svc2}.svc.cluster.local.",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z ERROR"
                " {pod} — dial tcp: lookup db-primary.internal on 10.96.0.10:53: no such host\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z ERROR"
                " {pod} — Get 'http://{svc2}': dial tcp: lookup {svc2}: NXDOMAIN\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z WARN"
                " coredns — [ERROR] plugin/errors: 2 NXDOMAIN for {svc2}.svc.cluster.local.\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:05Z ERROR"
                " {pod} — net.UnknownHostException: {service}.internal\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:06Z WARN"
                " coredns — plugin/reload: reload failed: opening 'Corefile': no such file\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — requests.exceptions.ConnectionError: Name or service not known\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z WARN"
                " {pod} — DNS timeout after 5000ms for {service}.internal\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:20Z ERROR"
                " {pod} — Resolved IP 10.0.0.255 for db-primary — routing black-hole\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:21Z WARN"
                " {pod} — DNS answer TTL=0, caching disabled\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:30Z ERROR"
                " {pod} — SERVFAIL response from 10.96.0.10:53\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:31Z WARN"
                " {pod} — ndots:5 search path causing NXDOMAIN on short names\n"
            ),
        ],
        "root_cause": "CoreDNS misconfiguration causing internal DNS resolution failures",
        "fix_steps": [
            "Restart CoreDNS pods: kubectl rollout restart deploy/coredns -n kube-system",
            "Correct resolver config in Corefile or DNS ConfigMap",
            "Verify resolution: kubectl exec -it {pod} -- nslookup {service}.svc.cluster.local",
            "Add DNS failure rate alert via CoreDNS metrics",
        ],
        "base_minutes": [50, 40, 25, 18, 12],
    },
    {
        "name": "oom_killed",
        "severities": ["SEV1", "SEV2", "SEV2", "SEV3", "SEV3"],
        "title_templates": [
            "{service} — OOMKilled pods from JVM heap leak",
            "{service} — memory leak causing repeated OOMKilled restarts",
            "{service} — container OOM due to unbounded in-memory cache",
            "{service} — JVM heap exhaustion causing process crashes",
            "{service} — RSS memory growth leading to OOMKilled evictions",
        ],
        "symptom_templates": [
            "Pods OOMKilled repeatedly. Memory usage growing before each crash.",
            "JVM heap dump shows growing object retention in cache layer.",
            "Container memory limit hit. OOMKilled every 30 minutes.",
            "kubectl describe pod shows OOMKilled exit code 137.",
            "Memory graph shows sawtooth pattern (grow, crash, restart).",
        ],
        "log_templates": [
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:00Z ERROR"
                " k8s — OOMKilled {pod}: container {service} exceeded memory limit 2Gi\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:01Z WARN"
                " {pod} — GC overhead limit exceeded\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:02Z ERROR"
                " {pod} — java.lang.OutOfMemoryError: Java heap space\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:03Z WARN"
                " {pod} — Heap usage: 1.98GB/2GB (99%)\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:05Z ERROR"
                " k8s — Container {service} in pod {pod} OOMKilled (exit 137)\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:06Z WARN"
                " {pod} — RSS: 1.9GB — approaching kernel OOM limit\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:10Z ERROR"
                " {pod} — RuntimeError: CUDA out of memory — falling back to CPU\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:11Z ERROR"
                " {pod} — MemoryError: Unable to allocate 512 MiB\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:15Z WARN"
                " {pod} — LRU cache size: 2.1M entries, 1.8GB resident\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:16Z ERROR"
                " k8s — Evicted pod {pod}: The node was low on resource: memory\n"
            ),
            (
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:20Z WARN"
                " {pod} — GC pause 8s — memory pressure high\n"
                "2025-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:21Z ERROR"
                " {pod} — Killed process (oom-kill event) in cgroup\n"
            ),
        ],
        "root_cause": "JVM / application memory leak causing container memory limit to be exceeded",
        "fix_steps": [
            "Restart affected pods immediately to restore service",
            "Apply JVM heap limit: -Xmx1536m to prevent OOM",
            "Identify leaking cache: take heap dump and analyse with Eclipse MAT",
            "Patch the leaking cache with a bounded size (e.g. Caffeine maxSize=10000)",
        ],
        "base_minutes": [70, 55, 30, 25, 18],
    },
]


def _random_pod(service: str) -> str:
    suffix = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=5))
    return f"{service}-{suffix}-pod"


def _random_ver() -> str:
    return f"{random.randint(1, 9)}.{random.randint(0, 20)}.{random.randint(0, 9)}"


def generate() -> list:
    """Generate and return 40 incident dicts."""
    incidents = []
    base_date = datetime(2025, 4, 1, tzinfo=timezone.utc)
    inc_num = 1

    for family in FAMILIES:
        service_pool = list(SERVICES)
        random.shuffle(service_pool)
        for i in range(5):
            service = service_pool[i % len(service_pool)]
            svc2 = random.choice([s for s in SERVICES if s != service])
            severity = family["severities"][i]
            base_min = family["base_minutes"][i]
            # Small variation ±5 min
            resolution_minutes = max(5, base_min + random.randint(-5, 5))

            # Random date in last 180 days
            days_offset = random.randint(0, 179)
            created_at = base_date + timedelta(days=days_offset, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            resolved_at = created_at + timedelta(minutes=resolution_minutes)

            month = created_at.month
            day = created_at.day
            hour = created_at.hour
            minute = created_at.minute
            pod = _random_pod(service)
            ver = _random_ver()

            title = family["title_templates"][i].format(service=service, svc2=svc2, ver=ver)
            symptoms = family["symptom_templates"][i].format(service=service, svc2=svc2)
            log = family["log_templates"][i].format(
                service=service, svc2=svc2, pod=pod, month=month, day=day,
                hour=hour, min=minute, ver=ver
            )
            root_cause = family["root_cause"]
            fix_steps = [
                s.format(service=service, svc2=svc2, pod=pod, ver=ver)
                for s in family["fix_steps"]
            ]

            incidents.append({
                "incident_id": f"INC-{inc_num:04d}",
                "title": title,
                "service": service,
                "severity": severity,
                "error_log": log,
                "symptoms": symptoms,
                "root_cause": root_cause,
                "fix_steps": fix_steps,
                "resolution_minutes": resolution_minutes,
                "status": "resolved",
                "created_at": created_at.isoformat(),
                "resolved_at": resolved_at.isoformat(),
            })
            inc_num += 1

    return incidents


if __name__ == "__main__":
    incidents = generate()
    output_path = Path(__file__).parent / "incidents_seed.json"
    output_path.write_text(json.dumps(incidents, indent=2, default=str))
    print(f"Generated {len(incidents)} incidents -> {output_path}")
