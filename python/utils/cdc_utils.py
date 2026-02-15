"""CDC utility functions for verifying readiness and health."""

import time
from typing import Optional
from .neo4j_client import Neo4jClient


def wait_for_cdc_ready(client: Neo4jClient, timeout_seconds: int = 60) -> bool:
    """
    Wait for CDC to be fully initialized and ready to capture changes.

    This calls db.cdc.current() to verify the CDC transaction log is active.

    Args:
        client: Neo4jClient instance connected to CDC-enabled database
        timeout_seconds: Maximum seconds to wait (default 60)

    Returns:
        True if CDC is ready, raises Exception if timeout
    """
    print(f"⏳ Waiting for CDC to initialize (timeout: {timeout_seconds}s)...")

    for i in range(timeout_seconds):
        try:
            # Call db.cdc.current() to verify CDC is ready
            result = client.execute_read("CALL db.cdc.current()")

            if result and len(result) > 0:
                change_id = result[0].get('id', 'unknown')
                print(f"✓ CDC is ready! Current change ID: {change_id}")
                return True

        except Exception as e:
            error_msg = str(e).lower()

            # Check for known "not ready" errors
            if any(x in error_msg for x in ['procedure', 'not found', 'no procedure', 'cdc']):
                if i == timeout_seconds - 1:
                    raise Exception(f"CDC not ready after {timeout_seconds} seconds: {e}")

                if i % 10 == 0:  # Print every 10 seconds
                    print(f"  Waiting... ({i+1}/{timeout_seconds}s)")

                time.sleep(1)
            else:
                # Different error - raise immediately
                raise Exception(f"Unexpected error checking CDC: {e}")

    raise Exception(f"CDC readiness check timed out after {timeout_seconds} seconds")


def verify_cdc_capturing(client: Neo4jClient) -> bool:
    """
    Verify CDC is actively capturing changes by writing a test node.

    Args:
        client: Neo4jClient instance connected to CDC-enabled database

    Returns:
        True if CDC captured the test change
    """
    print("🔬 Verifying CDC is actively capturing changes...")

    # Get current change ID
    result = client.execute_read("CALL db.cdc.current()")
    from_id = result[0]['id']

    # Write a test node
    test_id = f"cdc-test-{int(time.time())}"
    client.execute_write(
        "CREATE (t:_CDCTest {id: $id, timestamp: timestamp()})",
        {"id": test_id}
    )

    # Delete it
    client.execute_write(
        "MATCH (t:_CDCTest {id: $id}) DELETE t",
        {"id": test_id}
    )

    # Query CDC log to see if changes were captured
    time.sleep(2)  # Small delay for CDC to process

    result = client.execute_read("""
        CALL db.cdc.query($fromId, null)
        YIELD event
        WHERE event.metadata.executingUser IS NOT NULL
        RETURN count(*) as changes
    """, {"fromId": from_id})

    changes = result[0]['changes']

    if changes >= 2:  # Should see CREATE + DELETE
        print(f"✓ CDC is actively capturing changes ({changes} events captured)")
        return True
    else:
        print(f"✗ CDC not capturing changes (expected 2+ events, got {changes})")
        return False
