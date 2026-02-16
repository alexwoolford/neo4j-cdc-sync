#!/usr/bin/env python3
"""
Test true CDC by making individual changes and verifying event propagation.
Tests CREATE, UPDATE, and DELETE events to ensure true event-based CDC is working.

Includes a warm-up phase that ensures the CDC pipeline is actively flowing
before running tests. This handles Azure Event Hubs metadata connection
stalls that can cause 30-100+ second delays after idle periods.

Usage:
    cd terraform
    export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)
    export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)
    export SUBSCRIBER_NEO4J_URI=$(terraform output -raw subscriber_neo4j_uri)
    export SUBSCRIBER_NEO4J_PASSWORD=$(terraform output -raw subscriber_neo4j_password)
    cd ../python
    python test_live_cdc.py
"""

import os
import sys
import time
import uuid
from typing import Callable
from rich.console import Console
from utils.neo4j_client import Neo4jClient

console = Console()

PROPAGATION_TIMEOUT = 90


def wait_for_condition(
    check_fn: Callable[[], bool],
    timeout_seconds: float = PROPAGATION_TIMEOUT,
    poll_interval_seconds: float = 0.5
) -> tuple[bool, float]:
    """
    Poll until check_fn returns True or timeout.

    Returns:
        (success, elapsed_seconds) - success is True if condition was met
    """
    start = time.time()
    while True:
        elapsed = time.time() - start
        if check_fn():
            return True, elapsed
        if elapsed >= timeout_seconds:
            return False, elapsed
        time.sleep(poll_interval_seconds)


def warm_up_pipeline(source: Neo4jClient, target: Neo4jClient) -> bool:
    """
    Send a disposable event through the CDC pipeline and wait for it to arrive.
    This ensures the Kafka Connect producer/consumer connections to Azure Event
    Hubs are active before running the actual tests.

    Returns True if warm-up succeeded.
    """
    warmup_id = str(uuid.uuid4())[:8]
    warmup_label = f"_CDCWarmUp"

    console.print("[dim]Warming up CDC pipeline...[/dim]")
    console.print("[dim]  (Azure Event Hubs may need up to 2 min to establish connections)[/dim]")

    source.execute_write(
        f"CREATE (w:{warmup_label} {{wid: $wid}})",
        {"wid": warmup_id}
    )

    def check_warmup():
        try:
            result = target.execute_read(
                f"MATCH (w:{warmup_label} {{wid: $wid}}) RETURN w",
                {"wid": warmup_id}
            )
            return len(result) >= 1
        except Exception:
            return False

    start = time.time()
    last_status = start
    success = False
    while True:
        elapsed = time.time() - start
        if check_warmup():
            success = True
            break
        if elapsed >= 180:
            break
        if time.time() - last_status >= 15:
            console.print(f"[dim]  Still warming up... {int(elapsed)}s[/dim]")
            last_status = time.time()
        time.sleep(1)

    # Clean up warmup node on master (CDC will propagate the delete)
    source.execute_write(
        f"MATCH (w:{warmup_label} {{wid: $wid}}) DELETE w",
        {"wid": warmup_id}
    )

    if success:
        console.print(f"[dim]  Pipeline warm ({int(time.time() - start)}s). Ready to test.[/dim]\n")
    else:
        console.print(f"[bold red]  Pipeline did not respond after 180s.[/bold red]")

    return success


def main():
    """Run event-level CDC tests."""

    # Connect to databases
    console.print("[bold blue]Connecting to databases...[/bold blue]")
    try:
        source = Neo4jClient(
            os.getenv("MASTER_NEO4J_URI"),
            "neo4j",
            os.getenv("MASTER_NEO4J_PASSWORD")
        )
        target = Neo4jClient(
            os.getenv("SUBSCRIBER_NEO4J_URI"),
            "neo4j",
            os.getenv("SUBSCRIBER_NEO4J_PASSWORD")
        )
    except Exception as e:
        console.print(f"[bold red]Error connecting to databases: {e}[/bold red]")
        sys.exit(1)

    console.print("[green]✓ Connected to both databases[/green]\n")

    # Clean up any leftover test nodes from previous runs
    console.print("[dim]Cleaning up leftover test data...[/dim]")
    source.execute_write("MATCH (p:Person {id: 9999}) DELETE p")
    source.execute_write("MATCH (w:_CDCWarmUp) DELETE w")

    def check_cleanup():
        try:
            result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p")
            return len(result) == 0
        except Exception:
            return False

    # Don't wait long for cleanup - it's just best-effort
    if not check_cleanup():
        wait_for_condition(check_cleanup, timeout_seconds=10)
    console.print("[dim]  Done.[/dim]\n")

    # Warm up the pipeline before running tests
    if not warm_up_pipeline(source, target):
        console.print("[bold red]CDC pipeline is not responding. Check connector status.[/bold red]")
        sys.exit(1)

    # Test 1: CREATE event
    console.print("[bold cyan]Test 1: CREATE Event[/bold cyan]")
    console.print("Creating new node in master graph...")

    try:
        source.execute_write(
            "MERGE (p:Person {id: 9999}) SET p.name = 'CDC Test User', p.email = 'cdc@test.com', p.testRun = timestamp()"
        )
        console.print("[green]✓ Node created in source[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to create node: {e}[/red]")
        sys.exit(1)

    console.print("Waiting for CDC propagation...")

    def check_create():
        try:
            result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name, p.email as email")
            return len(result) >= 1 and result[0]["name"] == "CDC Test User"
        except Exception:
            return False

    success, elapsed = wait_for_condition(check_create)
    if success:
        result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name, p.email as email")
        console.print(f"[bold green]✓ CREATE event propagated in {elapsed:.1f}s[/bold green]")
        console.print(f"  Found: {result[0]}")
    else:
        console.print(f"[bold red]✗ CREATE event failed - node not found after {elapsed:.1f}s[/bold red]")
        sys.exit(1)

    console.print()

    # Test 2: UPDATE event
    console.print("[bold cyan]Test 2: UPDATE Event[/bold cyan]")
    console.print("Updating node property in master graph...")

    try:
        source.execute_write("MATCH (p:Person {id: 9999}) SET p.name = 'Updated CDC User', p.lastModified = timestamp()")
        console.print("[green]✓ Node updated in source[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to update node: {e}[/red]")
        sys.exit(1)

    console.print("Waiting for CDC propagation...")

    def check_update():
        try:
            result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name")
            return len(result) >= 1 and all(r["name"] == "Updated CDC User" for r in result)
        except Exception:
            return False

    success, elapsed = wait_for_condition(check_update)
    if success:
        result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name")
        console.print(f"[bold green]✓ UPDATE event propagated in {elapsed:.1f}s[/bold green]")
        console.print(f"  Updated name: {result[0]['name']}")
    else:
        result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name")
        console.print(f"[bold red]✗ UPDATE event failed after {elapsed:.1f}s[/bold red]")
        console.print(f"  Expected: 'Updated CDC User', Got: {result[0]['name'] if result else 'NOT FOUND'}")
        sys.exit(1)

    console.print()

    # Test 3: DELETE event
    console.print("[bold cyan]Test 3: DELETE Event[/bold cyan]")
    console.print("Deleting node from master graph...")

    try:
        source.execute_write("MATCH (p:Person {id: 9999}) DELETE p")
        console.print("[green]✓ Node deleted from source[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to delete node: {e}[/red]")
        sys.exit(1)

    console.print("Waiting for CDC propagation...")

    def check_delete():
        try:
            result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p")
            return len(result) == 0
        except Exception:
            return False

    success, elapsed = wait_for_condition(check_delete)
    if success:
        console.print(f"[bold green]✓ DELETE event propagated in {elapsed:.1f}s[/bold green]")
        console.print(f"  Node no longer exists in target")
    else:
        console.print(f"[bold red]✗ DELETE event failed - node still exists after {elapsed:.1f}s[/bold red]")
        sys.exit(1)

    console.print()
    console.print("[bold green]" + "="*60 + "[/bold green]")
    console.print("[bold green]✓ All CDC event types working correctly![/bold green]")
    console.print("[bold green]" + "="*60 + "[/bold green]")

    # Cleanup
    source.close()
    target.close()

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        sys.exit(130)
