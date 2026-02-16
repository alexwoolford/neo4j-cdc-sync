#!/usr/bin/env python3
"""
CDC pipeline heartbeat.

Writes a small event to the source Neo4j database every HEARTBEAT_INTERVAL
seconds. This generates continuous CDC traffic, preventing Azure Event Hubs
from silently dropping idle AMQP connections.

Without this, Event Hubs drops idle connections after ~4 minutes. Kafka Connect
doesn't detect the dead connection (task still reports RUNNING), so CDC events
produced during the stall are never delivered to the subscriber.

Environment variables:
    NEO4J_URI          - bolt URI for the source (master) database
    NEO4J_PASSWORD     - password for the source database
    NEO4J_USERNAME     - username (default: neo4j)
    HEARTBEAT_INTERVAL - seconds between heartbeats (default: 30)
"""

import logging
import os
import signal
import sys
import time

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [heartbeat] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

SHUTDOWN = False


def handle_signal(signum, frame):
    global SHUTDOWN
    log.info("Shutdown signal received, exiting...")
    SHUTDOWN = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def send_heartbeat(driver) -> bool:
    """Write a heartbeat node to the source database. Returns True on success."""
    try:
        with driver.session() as session:
            session.run(
                "MERGE (h:_Heartbeat {id: 'cdc-pipeline'}) "
                "SET h.ts = datetime(), h.seq = COALESCE(h.seq, 0) + 1"
            ).consume()
        return True
    except (ServiceUnavailable, SessionExpired) as e:
        log.warning("Neo4j connection issue: %s", e)
        return False
    except Exception as e:
        log.error("Heartbeat failed: %s", e)
        return False


def main():
    uri = os.environ.get("NEO4J_URI")
    password = os.environ.get("NEO4J_PASSWORD")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    interval = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))

    if not uri or not password:
        log.error("NEO4J_URI and NEO4J_PASSWORD must be set")
        sys.exit(1)

    log.info("Starting CDC heartbeat (interval=%ds, target=%s)", interval, uri)

    driver = GraphDatabase.driver(uri, auth=(username, password))

    # Verify connectivity before entering loop
    try:
        driver.verify_connectivity()
        log.info("Connected to Neo4j")
    except Exception as e:
        log.error("Cannot connect to Neo4j: %s", e)
        sys.exit(1)

    consecutive_failures = 0
    max_failures = 10

    try:
        while not SHUTDOWN:
            if send_heartbeat(driver):
                consecutive_failures = 0
                log.info("Heartbeat sent")
            else:
                consecutive_failures += 1
                log.warning(
                    "Heartbeat failed (%d/%d consecutive)",
                    consecutive_failures,
                    max_failures,
                )
                if consecutive_failures >= max_failures:
                    log.error(
                        "Too many consecutive failures, reconnecting..."
                    )
                    try:
                        driver.close()
                    except Exception:
                        pass
                    driver = GraphDatabase.driver(
                        uri, auth=(username, password)
                    )
                    consecutive_failures = 0

            # Sleep in small increments so we respond to SIGTERM quickly
            for _ in range(interval):
                if SHUTDOWN:
                    break
                time.sleep(1)
    finally:
        driver.close()
        log.info("Heartbeat stopped")


if __name__ == "__main__":
    main()
