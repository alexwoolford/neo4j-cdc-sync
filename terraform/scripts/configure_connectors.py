#!/usr/bin/env python3
"""
Configure Kafka Connect connectors for Neo4j CDC replication.

Reads configuration from environment variables (set by Terraform local-exec).
Uses PUT for idempotent connector creation/updates.
Verifies connectors reach RUNNING state before exiting.
"""

import os
import sys
import time
import requests


def wait_for_connect(url: str, timeout: int = 180) -> None:
    """Poll Kafka Connect REST API until it's ready."""
    print(f"Waiting for Kafka Connect at {url}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{url}/", timeout=10)
            if resp.status_code == 200:
                print("Kafka Connect is ready!")
                return
        except requests.RequestException:
            pass
        print(f"  Not ready yet, retrying in 5s... ({int(time.time() - start)}s elapsed)")
        time.sleep(5)
    raise TimeoutError(f"Kafka Connect not ready after {timeout}s")


def verify_topic_partitions(
    bootstrap_servers: str,
    sasl_connection_string: str,
    topic: str = "cdc-all",
    expected_partitions: int = 1
) -> None:
    """
    Verify Event Hubs topic has exactly the expected partition count.

    Multi-partition topics break CDC ordering guarantees: relationships may
    arrive before their nodes, causing sink connector failures.

    Args:
        bootstrap_servers: Event Hubs FQDN:9093
        sasl_connection_string: Event Hubs connection string
        topic: Topic name to verify
        expected_partitions: Expected partition count (default: 1)

    Raises:
        RuntimeError: If partition count doesn't match expected
    """
    print(f"Verifying topic '{topic}' partition count...")

    try:
        from kafka import KafkaAdminClient
        from kafka.errors import UnknownTopicOrPartitionError

        # Connect to Event Hubs using Kafka protocol
        admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            sasl_plain_username="$ConnectionString",
            sasl_plain_password=sasl_connection_string,
            request_timeout_ms=30000,
        )

        # Get topic metadata
        try:
            metadata = admin_client.describe_topics([topic])

            if topic not in metadata:
                # Topic doesn't exist yet - connector will create it
                print(f"  Topic '{topic}' not yet created - connector will create with {expected_partitions} partition(s)")
                return

            actual_partitions = len(metadata[topic]["partitions"])

            if actual_partitions == expected_partitions:
                print(f"  ✓ Topic has {actual_partitions} partition(s) (correct)")
            else:
                print(f"  ✗ CRITICAL: Topic has {actual_partitions} partition(s), expected {expected_partitions}", file=sys.stderr)
                print(f"\n{'='*70}", file=sys.stderr)
                print(f"PARTITION COUNT MISMATCH - CDC WILL NOT WORK CORRECTLY", file=sys.stderr)
                print(f"{'='*70}", file=sys.stderr)
                print(f"\nThe '{topic}' topic has {actual_partitions} partitions.", file=sys.stderr)
                print(f"Neo4j CDC requires exactly {expected_partitions} partition to ensure ordering:", file=sys.stderr)
                print(f"  - Nodes must arrive BEFORE relationships", file=sys.stderr)
                print(f"  - Multiple partitions break this guarantee", file=sys.stderr)
                print(f"  - Sink connector will fail with 'node not found' errors", file=sys.stderr)
                print(f"\nFix:", file=sys.stderr)
                print(f"  1. Delete the topic in Azure Portal:", file=sys.stderr)
                print(f"     Event Hubs namespace → Event Hubs → {topic} → Delete", file=sys.stderr)
                print(f"  2. Re-run terraform apply (connector will recreate with 1 partition)", file=sys.stderr)
                print(f"\nOr run: terraform destroy && terraform apply", file=sys.stderr)
                print(f"{'='*70}\n", file=sys.stderr)
                raise RuntimeError(f"Topic '{topic}' has {actual_partitions} partitions, expected {expected_partitions}")

        except UnknownTopicOrPartitionError:
            # Topic doesn't exist - connector will create it
            print(f"  Topic '{topic}' not yet created - connector will create with {expected_partitions} partition(s)")

    except ImportError:
        print("  Warning: kafka-python not installed, skipping partition check", file=sys.stderr)
        print("  Install with: pip install kafka-python>=2.0.2", file=sys.stderr)
        print("  This check ensures CDC ordering is preserved (1 partition required)", file=sys.stderr)
    except Exception as e:
        print(f"  Warning: Could not verify partition count: {e}", file=sys.stderr)
        print(f"  Continuing deployment, but CDC may fail if topic has >1 partition", file=sys.stderr)


def deploy_connector(url: str, name: str, config: dict) -> None:
    """Deploy or update a connector using PUT (idempotent)."""
    print(f"Deploying connector: {name}")
    resp = requests.put(
        f"{url}/connectors/{name}/config",
        json=config,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    if resp.status_code not in (200, 201):
        print(f"Error deploying {name}: {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        raise RuntimeError(f"Failed to deploy connector {name}")
    print(f"  Connector {name} deployed successfully")


def verify_connector(url: str, name: str, timeout: int = 60) -> None:
    """Poll connector status until task is RUNNING."""
    print(f"Verifying connector: {name}")
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{url}/connectors/{name}/status", timeout=10)
            if resp.status_code == 200:
                status = resp.json()
                connector_state = status.get("connector", {}).get("state", "")
                tasks = status.get("tasks", [])
                if tasks and tasks[0].get("state") == "RUNNING":
                    print(f"  Connector {name}: RUNNING")
                    return
                elif tasks and tasks[0].get("state") == "FAILED":
                    trace = tasks[0].get("trace", "No trace available")
                    print(f"  Connector {name} task FAILED: {trace}", file=sys.stderr)
                    raise RuntimeError(f"Connector {name} task failed")
                else:
                    task_state = tasks[0].get("state", "UNKNOWN") if tasks else "NO_TASKS"
                    print(f"  Connector state: {connector_state}, Task state: {task_state}")
        except requests.RequestException as e:
            print(f"  Error checking status: {e}")
        time.sleep(5)
    raise TimeoutError(f"Connector {name} not RUNNING after {timeout}s")


def build_source_config(master_uri: str, master_password: str) -> dict:
    """Build Neo4j CDC source connector configuration."""
    return {
        "connector.class": "org.neo4j.connectors.kafka.source.Neo4jConnector",
        "tasks.max": "1",
        "neo4j.uri": master_uri,
        "neo4j.authentication.type": "BASIC",
        "neo4j.authentication.basic.username": "neo4j",
        "neo4j.authentication.basic.password": master_password,
        # Neo4j driver connection settings for reliability
        "neo4j.connection-timeout": "30s",
        "neo4j.max-retry-time": "30s",
        "neo4j.pool.max-connection-pool-size": "10",
        "neo4j.pool.connection-acquisition-timeout": "60s",
        "neo4j.pool.max-connection-lifetime": "30m",
        "neo4j.pool.idle-time-before-connection-test": "1m",
        # CDC source settings
        "neo4j.source-strategy": "CDC",
        "neo4j.start-from": "EARLIEST",
        "neo4j.cdc.topic.cdc-all.patterns": "(),()-[]-()",
        "neo4j.cdc.poll-interval": "1s",
        # Single partition ensures strict ordering: nodes arrive before relationships
        "topic.creation.default.partitions": 1,
        "topic.creation.default.replication.factor": 1,
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "true",
        "value.converter.schemas.enable": "true",
        "errors.tolerance": "none",
        "errors.log.enable": "true",
        "errors.log.include.messages": "true",
    }


def build_sink_config(subscriber_uri: str, subscriber_password: str) -> dict:
    """Build Neo4j CDC sink connector configuration."""
    return {
        "connector.class": "org.neo4j.connectors.kafka.sink.Neo4jConnector",
        "tasks.max": "1",
        "topics": "cdc-all",
        "neo4j.uri": subscriber_uri,
        "neo4j.authentication.type": "BASIC",
        "neo4j.authentication.basic.username": "neo4j",
        "neo4j.authentication.basic.password": subscriber_password,
        # Neo4j driver connection settings for reliability
        "neo4j.connection-timeout": "30s",
        "neo4j.max-retry-time": "30s",
        "neo4j.pool.max-connection-pool-size": "10",
        "neo4j.pool.connection-acquisition-timeout": "60s",
        "neo4j.pool.max-connection-lifetime": "30m",
        "neo4j.pool.idle-time-before-connection-test": "1m",
        # CDC sink settings
        "neo4j.cdc.source-id.topics": "cdc-all",
        "neo4j.cdc.source-id.label-name": "SourceEvent",
        "neo4j.cdc.source-id.property-name": "sourceId",
        # Low-latency: flush every event immediately, no batching
        "neo4j.batch-size": "1",
        "neo4j.batch-timeout": "0s",
        "neo4j.retry-backoff-ms": "1000",
        "neo4j.retry-max-attempts": "10",
        # Reduce consumer poll latency
        "consumer.override.fetch.max.wait.ms": "100",
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "true",
        "value.converter.schemas.enable": "true",
        # Fail visibly so we see what's broken
        "errors.tolerance": "none",
        "errors.retry.timeout": "120000",
        "errors.retry.delay.max.ms": "10000",
        "errors.log.enable": "true",
        "errors.log.include.messages": "true",
        "errors.deadletterqueue.topic.name": "neo4j-cdc-dlq",
        "errors.deadletterqueue.topic.replication.factor": "1",
        "errors.deadletterqueue.context.headers.enable": "true",
    }


def main() -> int:
    """Main entry point."""
    # Read configuration from environment
    connect_url = os.environ.get("CONNECT_URL")
    master_uri = os.environ.get("MASTER_NEO4J_URI")
    master_password = os.environ.get("MASTER_NEO4J_PASSWORD")
    subscriber_uri = os.environ.get("SUBSCRIBER_NEO4J_URI")
    subscriber_password = os.environ.get("SUBSCRIBER_NEO4J_PASSWORD")

    # Validate required environment variables
    missing = []
    if not connect_url:
        missing.append("CONNECT_URL")
    if not master_uri:
        missing.append("MASTER_NEO4J_URI")
    if not master_password:
        missing.append("MASTER_NEO4J_PASSWORD")
    if not subscriber_uri:
        missing.append("SUBSCRIBER_NEO4J_URI")
    if not subscriber_password:
        missing.append("SUBSCRIBER_NEO4J_PASSWORD")

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 1

    try:
        # Wait for Kafka Connect to be ready
        wait_for_connect(connect_url)

        # CRITICAL: Verify partition count before deploying connectors
        # Multi-partition topics break CDC ordering (relationships before nodes)
        bootstrap_servers = f"{os.environ.get('EVENT_HUBS_FQDN', 'unknown')}:9093"
        connection_string = os.environ.get('EVENT_HUBS_CONNECTION_STRING', '')

        if bootstrap_servers != 'unknown:9093' and connection_string:
            verify_topic_partitions(
                bootstrap_servers=bootstrap_servers,
                sasl_connection_string=connection_string,
                topic="cdc-all",
                expected_partitions=1
            )
        else:
            print("Warning: EVENT_HUBS_FQDN or EVENT_HUBS_CONNECTION_STRING not set", file=sys.stderr)
            print("Skipping partition verification", file=sys.stderr)

        # Build connector configurations
        source_config = build_source_config(master_uri, master_password)
        sink_config = build_sink_config(subscriber_uri, subscriber_password)

        # Deploy connectors (PUT is idempotent)
        deploy_connector(connect_url, "neo4j-master-publisher", source_config)
        deploy_connector(connect_url, "neo4j-subscriber-consumer", sink_config)

        # Verify connectors are running
        verify_connector(connect_url, "neo4j-master-publisher")
        verify_connector(connect_url, "neo4j-subscriber-consumer")

        # Work around Event Hubs metadata timeout on fresh deploy:
        # The source task often stalls on its first CDC poll due to slow
        # topic metadata response. Restarting clears this stall.
        print("Restarting source task to clear Event Hubs metadata stall...")
        resp = requests.post(
            f"{connect_url}/connectors/neo4j-master-publisher/tasks/0/restart",
            timeout=10
        )
        if resp.status_code not in (200, 202, 204):
            print(f"  Warning: restart returned {resp.status_code}", file=sys.stderr)
        # Poll until task is RUNNING again (no blind sleep)
        verify_connector(connect_url, "neo4j-master-publisher")

        print("\nAll connectors deployed and running successfully!")
        return 0

    except (TimeoutError, RuntimeError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
