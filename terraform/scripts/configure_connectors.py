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
        "neo4j.source-strategy": "CDC",
        "neo4j.start-from": "EARLIEST",
        "neo4j.cdc.topic.cdc-all.patterns": "(),()-[]-()",
        "topic.creation.default.partitions": 3,
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
        "neo4j.cdc.source-id.topics": "cdc-all",
        "neo4j.cdc.source-id.label-name": "SourceEvent",
        "neo4j.cdc.source-id.property-name": "sourceId",
        "neo4j.batch-size": "50",
        "neo4j.batch-timeout": "30s",
        "neo4j.retry-backoff-ms": "1000",
        "neo4j.retry-max-attempts": "5",
        "consumer.override.max.poll.records": "100",
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "true",
        "value.converter.schemas.enable": "true",
        "errors.tolerance": "all",
        "errors.retry.timeout": "60000",
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

        # Build connector configurations
        source_config = build_source_config(master_uri, master_password)
        sink_config = build_sink_config(subscriber_uri, subscriber_password)

        # Deploy connectors (PUT is idempotent)
        deploy_connector(connect_url, "neo4j-master-publisher", source_config)
        deploy_connector(connect_url, "neo4j-subscriber-consumer", sink_config)

        # Verify connectors are running
        verify_connector(connect_url, "neo4j-master-publisher")
        verify_connector(connect_url, "neo4j-subscriber-consumer")

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
