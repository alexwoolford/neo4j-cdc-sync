# Production-grade Kafka Connect image with Neo4j connector pre-installed
FROM confluentinc/cp-kafka-connect:7.5.0

# Metadata
LABEL maintainer="Neo4j CDC Demo"
LABEL description="Kafka Connect with Neo4j Kafka Connector 5.2.0"
LABEL version="1.0"

# Pin to a specific, tested version of the Neo4j Kafka Connector
# Using 5.2.0 which is the stable version validated in this project
ARG NEO4J_CONNECTOR_VERSION=5.2.0

# Switch to root to install connector
USER root

# Install Neo4j Kafka Connector using Confluent Hub
# The --no-prompt flag ensures non-interactive installation
# The --component-dir specifies where to install (must be in CONNECT_PLUGIN_PATH)
RUN confluent-hub install --no-prompt \
    neo4j/kafka-connect-neo4j:${NEO4J_CONNECTOR_VERSION} && \
    # Verify installation
    ls -la /usr/share/confluent-hub-components/neo4j-kafka-connect-neo4j/ && \
    # Clean up any temporary files to reduce image size
    rm -rf /tmp/* /var/tmp/*

# The Confluent base image creates an appuser (UID 1000, GID 1000)
# Switch back to non-root user for runtime security
# This follows the principle of least privilege
USER appuser

# Document which ports are exposed
# 8083 is the Kafka Connect REST API
EXPOSE 8083

# Set working directory
WORKDIR /home/appuser

# Health check to ensure Kafka Connect is responding
# This allows Docker/Kubernetes to automatically detect unhealthy containers
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8083/ || exit 1

# The command is specified in docker-compose.yml, not here
# This allows for flexibility in how the container is started
