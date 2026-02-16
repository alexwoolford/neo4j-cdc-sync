#!/usr/bin/env python3
"""
Verify CDC propagation by comparing source and subscriber Neo4j databases.

Usage:
    # Set env vars from terraform output, then run:
    cd terraform
    export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)
    export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)
    export SUBSCRIBER_NEO4J_URI=$(terraform output -raw subscriber_neo4j_uri)
    export SUBSCRIBER_NEO4J_PASSWORD=$(terraform output -raw subscriber_neo4j_password)
    cd ../python
    python verify_cdc.py
"""

import os
import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table
from utils.neo4j_client import Neo4jClient


console = Console()


def compare_databases(source: Neo4jClient, target: Neo4jClient) -> bool:
    """
    Compare source and subscriber graphs for CDC verification.

    Args:
        source: Master graph client
        target: Subscriber graph client

    Returns:
        True if databases match, False otherwise
    """
    console.print("[bold blue]Comparing source and subscriber graphs...[/bold blue]\n")

    all_match = True

    # Compare node counts
    source_nodes = source.get_node_count()
    target_nodes = target.get_node_count()
    nodes_match = source_nodes == target_nodes

    # Compare relationship counts
    source_rels = source.get_relationship_count()
    target_rels = target.get_relationship_count()
    rels_match = source_rels == target_rels

    # Compare label counts
    source_labels = source.get_label_counts()
    target_labels = target.get_label_counts()
    labels_match = source_labels == target_labels

    # Create comparison table
    table = Table(title="CDC Verification Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", width=25)
    table.add_column("Source", style="yellow", justify="right")
    table.add_column("Target", style="yellow", justify="right")
    table.add_column("Status", style="green", width=15)

    # Add summary rows
    table.add_row(
        "Total Nodes",
        str(source_nodes),
        str(target_nodes),
        "[green]✓ Match[/green]" if nodes_match else "[red]✗ Mismatch[/red]"
    )
    table.add_row(
        "Total Relationships",
        str(source_rels),
        str(target_rels),
        "[green]✓ Match[/green]" if rels_match else "[red]✗ Mismatch[/red]"
    )

    # Add separator
    table.add_row("", "", "", "")

    # Add label counts (excluding SourceEvent which is expected only in target)
    all_labels = set(source_labels.keys()) | set(target_labels.keys())
    source_event_count = 0

    for label in sorted(all_labels):
        source_count = source_labels.get(label, 0)
        target_count = target_labels.get(label, 0)

        # SourceEvent is expected only in target (added by sink connector)
        if label == "SourceEvent":
            source_event_count = target_count
            table.add_row(
                f"{label} Nodes",
                str(source_count),
                str(target_count),
                "[green]✓ CDC Tracking[/green]"
            )
            continue

        match = source_count == target_count

        table.add_row(
            f"{label} Nodes",
            str(source_count),
            str(target_count),
            "[green]✓ Match[/green]" if match else "[red]✗ Mismatch[/red]"
        )

        if not match:
            all_match = False

    console.print(table)
    console.print()

    # Overall status
    # Note: all_match checks label counts excluding SourceEvent
    if nodes_match and rels_match and all_match:
        console.print("[bold green]✓ CDC is working correctly![/bold green]")
        console.print("[bold green]Source and subscriber graphs are in perfect sync.[/bold green]")

        if source_event_count > 0:
            console.print(f"\n[bold cyan]ℹ Info:[/bold cyan] {source_event_count} nodes have SourceEvent label in subscriber")
            console.print("[dim]This is expected - the sink connector adds this label to track CDC-replicated nodes[/dim]")

        return True
    else:
        console.print("[bold red]✗ CDC sync issue detected![/bold red]")
        console.print("[bold yellow]Possible causes:[/bold yellow]")
        console.print("  1. Bulk load still propagating — wait 1-2 minutes, then run verify_cdc.py again")
        console.print("  2. Connector not running (check connector status below)")
        console.print("  3. Heartbeat sidecar not running — if it stopped, Event Hubs connections may have gone idle")
        console.print("  4. Topic has multiple partitions — relationships may arrive before nodes")
        console.print("     The cdc-all topic must have exactly 1 partition. If it has more, delete it in")
        console.print("     Azure Event Hubs and re-apply terraform so it is recreated with 1 partition.")
        console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("  cd terraform")
        console.print("  KAFKA_CONNECT=$(terraform output -raw kafka_connect_rest_api)")
        console.print("  curl -s $KAFKA_CONNECT/connectors/neo4j-master-publisher/status | jq .")
        console.print("  curl -s $KAFKA_CONNECT/connectors/neo4j-subscriber-consumer/status | jq .")
        return False


def main():
    """Main verification function."""
    # Get database credentials from environment variables
    source_uri = os.getenv("MASTER_NEO4J_URI")
    source_username = os.getenv("MASTER_NEO4J_USERNAME", "neo4j")
    source_password = os.getenv("MASTER_NEO4J_PASSWORD")

    target_uri = os.getenv("SUBSCRIBER_NEO4J_URI")
    target_username = os.getenv("SUBSCRIBER_NEO4J_USERNAME", "neo4j")
    target_password = os.getenv("SUBSCRIBER_NEO4J_PASSWORD")

    # Validate credentials
    if not all([source_uri, source_password, target_uri, target_password]):
        console.print("[bold red]Error: Database credentials not set[/bold red]")
        console.print("\nSet environment variables from terraform output:")
        console.print("  cd terraform")
        console.print("  export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)")
        console.print("  export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)")
        console.print("  export SUBSCRIBER_NEO4J_URI=$(terraform output -raw subscriber_neo4j_uri)")
        console.print("  export SUBSCRIBER_NEO4J_PASSWORD=$(terraform output -raw subscriber_neo4j_password)")
        sys.exit(1)

    console.print(f"[bold blue]Source Database:[/bold blue] {source_uri}")
    console.print(f"[bold blue]Target Database:[/bold blue] {target_uri}\n")

    # Connect to both databases
    try:
        with Neo4jClient(source_uri, source_username, source_password) as source, \
             Neo4jClient(target_uri, target_username, target_password) as target:

            # Test connections
            if not source.test_connection():
                console.print("[bold red]Failed to connect to master graph![/bold red]")
                sys.exit(1)

            if not target.test_connection():
                console.print("[bold red]Failed to connect to subscriber graph![/bold red]")
                sys.exit(1)

            console.print("[green]Connected to both databases successfully[/green]\n")

            # Compare databases
            success = compare_databases(source, target)

            # Exit with appropriate code
            sys.exit(0 if success else 1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
