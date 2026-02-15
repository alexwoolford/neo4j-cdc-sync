#!/usr/bin/env python3
"""
Test true CDC by making individual changes and verifying event propagation.
Tests CREATE, UPDATE, and DELETE events to ensure true event-based CDC is working.

Usage:
    # Set env vars from terraform output, then run:
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
from rich.console import Console
from utils.neo4j_client import Neo4jClient

console = Console()

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

    # Test 1: CREATE event
    console.print("[bold cyan]Test 1: CREATE Event[/bold cyan]")
    console.print("Creating new node in master graph...")

    try:
        source.execute_write(
            "CREATE (p:Person {id: 9999, name: 'CDC Test User', email: 'cdc@test.com', testRun: timestamp()})"
        )
        console.print("[green]✓ Node created in source[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to create node: {e}[/red]")
        sys.exit(1)

    console.print("Waiting 5 seconds for CDC propagation...")
    time.sleep(5)

    try:
        result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name, p.email as email")
        if len(result) == 1 and result[0]["name"] == "CDC Test User":
            console.print(f"[bold green]✓ CREATE event propagated successfully![/bold green]")
            console.print(f"  Found: {result[0]}")
        else:
            console.print(f"[bold red]✗ CREATE event failed - node not found in target[/bold red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error verifying CREATE: {e}[/red]")
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

    console.print("Waiting 5 seconds for CDC propagation...")
    time.sleep(5)

    try:
        result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p.name as name")
        if len(result) == 1 and result[0]["name"] == "Updated CDC User":
            console.print(f"[bold green]✓ UPDATE event propagated successfully![/bold green]")
            console.print(f"  Updated name: {result[0]['name']}")
        else:
            console.print(f"[bold red]✗ UPDATE event failed - property not updated in target[/bold red]")
            console.print(f"  Expected: 'Updated CDC User', Got: {result[0]['name'] if result else 'NOT FOUND'}")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error verifying UPDATE: {e}[/red]")
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

    console.print("Waiting 5 seconds for CDC propagation...")
    time.sleep(5)

    try:
        result = target.execute_read("MATCH (p:Person {id: 9999}) RETURN p")
        if len(result) == 0:
            console.print(f"[bold green]✓ DELETE event propagated successfully![/bold green]")
            console.print(f"  Node no longer exists in target")
        else:
            console.print(f"[bold red]✗ DELETE event failed - node still exists in target[/bold red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error verifying DELETE: {e}[/red]")
        sys.exit(1)

    console.print()
    console.print("[bold green]" + "="*60 + "[/bold green]")
    console.print("[bold green]✓ All CDC event types working correctly![/bold green]")
    console.print("[bold green]" + "="*60 + "[/bold green]")
    console.print()
    console.print("True event-based CDC is operational:")
    console.print("  ✓ CREATE events propagate")
    console.print("  ✓ UPDATE events propagate")
    console.print("  ✓ DELETE events propagate")
    console.print()
    console.print("[dim]CDC latency: ~5 seconds end-to-end[/dim]")

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
