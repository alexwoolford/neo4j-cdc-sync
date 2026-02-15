# Production-Grade Kafka Connect Setup

This directory contains a production-ready Kafka Connect deployment with the Neo4j Kafka Connector pre-installed.

## Architecture

```
Dockerfile
    ↓ (builds custom image)
neo4j-kafka-connect:5.2.0
    ↓ (used by)
docker-compose.yml
    ↓ (starts container)
Kafka Connect with Neo4j Connector 5.2.0 (pinned)
```

## Key Production Features

### 1. **Pinned Connector Version**
- Neo4j Kafka Connector version **5.2.0** is pinned in the Dockerfile
- No more `confluent-hub install :latest` at runtime
- Ensures reproducible builds across environments
- Version can be changed via build arg: `--build-arg NEO4J_CONNECTOR_VERSION=5.3.0`

### 2. **Pre-Built Docker Image**
- Connector is installed during image build, not at container startup
- Faster startup time (~5 seconds vs ~30+ seconds)
- Offline deployments supported (no internet required at runtime)
- Immutable infrastructure pattern

### 3. **Security: Non-Root User**
- Container runs as `appuser` (UID 1000, GID 1000)
- Follows principle of least privilege
- Reduces attack surface
- Compatible with Kubernetes PodSecurityPolicy

### 4. **Health Checks**
- Built-in health check in Dockerfile
- Polls `http://localhost:8083/` every 30 seconds
- Docker/Kubernetes can automatically detect and restart unhealthy containers

### 5. **Restart Policy**
- `restart: unless-stopped` in docker-compose.yml
- Automatically recovers from failures
- Stops only on explicit `docker-compose down`

## Building the Image

### Manual Build

```bash
cd kafka-connect

# Build with default pinned version (5.2.0)
docker-compose build

# Build with different version
docker-compose build --build-arg NEO4J_CONNECTOR_VERSION=5.3.0
```

### Automatic Build

The image is automatically built when you run:

```bash
docker-compose up -d
```

If the image doesn't exist, Docker Compose will build it first.

## Starting Kafka Connect

```bash
cd kafka-connect

# Build and start in one command
docker-compose up -d

# View logs
docker-compose logs -f

# Check health
curl http://localhost:8083/
```

## Verifying the Neo4j Connector

After starting, verify the connector is available:

```bash
# List installed connectors
curl -s http://localhost:8083/connector-plugins | jq '.[] | select(.class | contains("Neo4j"))'
```

Expected output:
```json
{
  "class": "org.neo4j.connectors.kafka.source.Neo4jConnector",
  "type": "source",
  "version": "5.2.0"
}
{
  "class": "org.neo4j.connectors.kafka.sink.Neo4jConnector",
  "type": "sink",
  "version": "5.2.0"
}
```

## File Structure

```
kafka-connect/
├── Dockerfile                        # Custom image with pre-installed connector
├── docker-compose.yml                # Service definition
├── .dockerignore                     # Exclude files from build context
├── connect-distributed.properties    # Kafka Connect configuration
├── connectors/                       # Connector configurations (generated)
│   ├── neo4j-master-publisher.json.template
│   └── neo4j-subscriber-consumer.json.template
└── README.md                         # This file
```

## Why Non-Root?

The Confluent base image creates a user `appuser` (UID 1000) specifically for running Kafka Connect.

**Security Benefits:**
1. **Least Privilege**: Process cannot modify system files or escalate privileges
2. **Container Escape Mitigation**: Even if exploited, attacker has limited permissions
3. **Kubernetes Compliance**: Meets PodSecurityPolicy requirements
4. **Audit Trail**: Actions are traceable to a specific non-root user

**Build Process:**
1. Dockerfile starts as `root` (needed to install connector)
2. Installs Neo4j connector using `confluent-hub`
3. Switches to `appuser` before CMD/ENTRYPOINT
4. Container runs entire lifecycle as `appuser`

**Verification:**
```bash
# Check which user the process runs as
docker exec kafka-connect whoami
# Output: appuser

docker exec kafka-connect id
# Output: uid=1000(appuser) gid=1000(appuser) groups=1000(appuser)
```

## Upgrading the Connector Version

### Option 1: Rebuild with New Version

```bash
# Edit Dockerfile line 9:
ARG NEO4J_CONNECTOR_VERSION=5.3.0

# Rebuild
docker-compose build --no-cache
docker-compose up -d
```

### Option 2: Build Arg Override

```bash
docker-compose build --build-arg NEO4J_CONNECTOR_VERSION=5.3.0
docker-compose up -d
```

### Option 3: Update docker-compose.yml

```yaml
build:
  args:
    NEO4J_CONNECTOR_VERSION: "5.3.0"  # Change this line
```

## Troubleshooting

### Connector Not Found

If connector-plugins endpoint doesn't show Neo4j:

```bash
# Check if connector JAR exists
docker exec kafka-connect ls -la /usr/share/confluent-hub-components/neo4j-kafka-connect-neo4j/

# Check plugin path
docker exec kafka-connect env | grep CONNECT_PLUGIN_PATH
```

### Permission Denied Errors

If you see permission errors, verify the user:

```bash
# Should be appuser (UID 1000)
docker exec kafka-connect whoami

# Check file permissions
docker exec kafka-connect ls -la /usr/share/confluent-hub-components/
```

### Build Failures

If build fails downloading the connector:

```bash
# Check internet connectivity
docker run --rm curlimages/curl curl -I https://www.confluent.io

# Try explicit version
docker-compose build --build-arg NEO4J_CONNECTOR_VERSION=5.2.0 --no-cache
```

## Production Deployment Considerations

### For Kubernetes

This Dockerfile is Kubernetes-ready:
- Non-root user (passes PodSecurityPolicy)
- Health check (for liveness/readiness probes)
- Immutable image (no runtime modifications)

Example Kubernetes deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-connect
spec:
  replicas: 1
  template:
    spec:
      securityContext:
        runAsUser: 1000
        runAsNonRoot: true
        fsGroup: 1000
      containers:
      - name: kafka-connect
        image: neo4j-kafka-connect:5.2.0
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false  # Kafka Connect needs to write logs
```

### For Azure Container Instances

This image works with Azure Container Instances:

```bash
# Tag for Azure Container Registry
docker tag neo4j-kafka-connect:5.2.0 myregistry.azurecr.io/neo4j-kafka-connect:5.2.0

# Push to ACR
docker push myregistry.azurecr.io/neo4j-kafka-connect:5.2.0

# Deploy to ACI
az container create \
  --resource-group neo4j-cdc-rg \
  --name kafka-connect \
  --image myregistry.azurecr.io/neo4j-kafka-connect:5.2.0 \
  --ports 8083 \
  --environment-variables CONNECT_BOOTSTRAP_SERVERS=... \
  --secure-environment-variables EVENT_HUBS_CONNECTION_STRING=...
```

## Image Size

- **Base image** (confluentinc/cp-kafka-connect:7.5.0): ~1.5 GB
- **Neo4j connector**: ~50 MB
- **Total**: ~1.55 GB

The image size is reasonable for a production Kafka Connect deployment.
