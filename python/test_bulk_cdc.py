#!/usr/bin/env python3
"""
Automated bulk CDC test: warm pipeline, run social_network generator, verify exact replication.

This test ensures zero data loss: all 110 nodes and 445 relationships created by
the social_network generator must appear on the subscriber.

Usage:
    cd terraform
    export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)
    export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)
    export SUBSCRIBER_NEO4J_URI=$(terraform output -raw subscriber_neo4j_uri)
    export SUBSCRIBER_NEO4J_PASSWORD=$(terraform output -raw subscriber_neo4j_password)
    cd ../python
    python test_bulk_cdc.py
"""

import os
import sys
import time
import subprocess
from pathlib import Path

from rich.console import Console
from utils.neo4j_client import Neo4jClient

# Import warm_up_pipeline from test_live_cdc
from test_live_cdc import warm_up_pipeline

console = Console()

# Expected counts from social_network.py
EXPECTED_NODES = 110       # 10 Company + 100 Person
EXPECTED_RELS = 445        # 100 WORKS_AT + 345 KNOWS
PROPAGATION_TIMEOUT = 180  # 3 minutes max for bulk propagation


def clear_databases(source: Neo4jClient, target: Neo4jClient) -> None:
    """Clear all nodes and relationships from both databases."""
    console.print("[dim]Clearing existing data from both databases...[/dim]")

    # Clear source
    source.execute_write("MATCH (n) DETACH DELETE n")

    # Wait briefly for CDC to propagate deletes
    time.sleep(2)

    # Clear target (in case CDC delete propagation is slow or incomplete)
    target.execute_write("MATCH (n) DETACH DELETE n")

    console.print("[dim]  Done.[/dim]\n")


def run_social_network_generator() -> bool:
    """Run the social_network.py generator script."""
    console.print("[bold blue]Running social_network generator...[/bold blue]")

    # Find the generators directory relative to this script
    repo_root = Path(__file__).parent.parent
    generator_path = repo_root / "generators" / "social_network.py"

    if not generator_path.exists():
        console.print(f"[red]Error: Generator not found at {generator_path}[/red]")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(generator_path)],
            cwd=str(repo_root / "generators"),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            console.print(f"[red]Generator failed with exit code {result.returncode}[/red]")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
            return False

        console.print("[green]Generator completed successfully[/green]\n")
        return True

    except subprocess.TimeoutExpired:
        console.print("[red]Generator timed out after 120s[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Error running generator: {e}[/red]")
        return False


def check_counts(source: Neo4jClient, target: Neo4jClient) -> tuple[bool, dict]:
    """
    Check node and relationship counts on both databases.

    Returns:
        (all_match, counts_dict)
    """
    source_nodes = source.get_node_count()
    source_rels = source.get_relationship_count()
    target_nodes = target.get_node_count()
    target_rels = target.get_relationship_count()

    counts = {
        "source_nodes": source_nodes,
        "source_rels": source_rels,
        "target_nodes": target_nodes,
        "target_rels": target_rels,
    }

    all_match = (
        source_nodes == EXPECTED_NODES and
        source_rels == EXPECTED_RELS and
        target_nodes == EXPECTED_NODES and
        target_rels == EXPECTED_RELS
    )

    return all_match, counts


def wait_for_propagation(source: Neo4jClient, target: Neo4jClient) -> tuple[bool, dict, float]:
    """
    Poll until source and target both have expected counts, or timeout.

    Returns:
        (success, final_counts, elapsed_seconds)
    """
    console.print("[bold blue]Waiting for CDC propagation...[/bold blue]")
    console.print(f"[dim]  Expected: {EXPECTED_NODES} nodes, {EXPECTED_RELS} relationships[/dim]")
    console.print(f"[dim]  Timeout: {PROPAGATION_TIMEOUT}s[/dim]\n")

    start = time.time()
    last_status = start
    poll_interval = 10  # Check every 10 seconds

    while True:
        elapsed = time.time() - start
        success, counts = check_counts(source, target)

        if success:
            return True, counts, elapsed

        if elapsed >= PROPAGATION_TIMEOUT:
            return False, counts, elapsed

        # Print status update every 30 seconds
        if time.time() - last_status >= 30:
            console.print(
                f"[dim]  {int(elapsed)}s: target has {counts['target_nodes']} nodes, "
                f"{counts['target_rels']} rels (waiting for {EXPECTED_NODES}/{EXPECTED_RELS})...[/dim]"
            )
            last_status = time.time()

        time.sleep(poll_interval)


def main() -> int:
    """Run the full bulk CDC test."""
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]")
    console.print("[bold magenta]       Bulk CDC Test: Zero Data Loss Verification[/bold magenta]")
    console.print("[bold magenta]" + "=" * 60 + "[/bold magenta]\n")

    # Validate environment
    required_vars = [
        "MASTER_NEO4J_URI",
        "MASTER_NEO4J_PASSWORD",
        "SUBSCRIBER_NEO4J_URI",
        "SUBSCRIBER_NEO4J_PASSWORD",
    ]

    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        console.print("[bold red]Error: Missing required environment variables:[/bold red]")
        for var in missing:
            console.print(f"  - {var}")
        console.print("\nSet them from terraform output:")
        console.print("  cd terraform")
        console.print("  export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)")
        console.print("  export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)")
        console.print("  export SUBSCRIBER_NEO4J_URI=$(terraform output -raw subscriber_neo4j_uri)")
        console.print("  export SUBSCRIBER_NEO4J_PASSWORD=$(terraform output -raw subscriber_neo4j_password)")
        return 1

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
        return 1

    console.print("[green]Connected to both databases[/green]\n")

    try:
        # Step 1: Clear databases
        clear_databases(source, target)

        # Step 2: Warm up the pipeline
        console.print("[bold blue]Step 1: Warming up CDC pipeline...[/bold blue]")
        if not warm_up_pipeline(source, target):
            console.print("[bold red]Pipeline warm-up failed. Check connector status.[/bold red]")
            return 1

        # Step 3: Run the generator
        console.print("[bold blue]Step 2: Running bulk data generator...[/bold blue]")
        if not run_social_network_generator():
            console.print("[bold red]Generator failed.[/bold red]")
            return 1

        # Step 4: Wait for propagation
        console.print("[bold blue]Step 3: Verifying CDC propagation...[/bold blue]")
        success, counts, elapsed = wait_for_propagation(source, target)

        # Print final results
        console.print()
        console.print("[bold cyan]Final Counts:[/bold cyan]")
        console.print(f"  Source:     {counts['source_nodes']} nodes, {counts['source_rels']} relationships")
        console.print(f"  Target:     {counts['target_nodes']} nodes, {counts['target_rels']} relationships")
        console.print(f"  Expected:   {EXPECTED_NODES} nodes, {EXPECTED_RELS} relationships")
        console.print()

        if success:
            console.print("[bold green]" + "=" * 60 + "[/bold green]")
            console.print(f"[bold green]SUCCESS: All data replicated in {elapsed:.1f}s[/bold green]")
            console.print(f"[bold green]Zero data loss confirmed: {EXPECTED_NODES} nodes, {EXPECTED_RELS} relationships[/bold green]")
            console.print("[bold green]" + "=" * 60 + "[/bold green]")
            return 0
        else:
            console.print("[bold red]" + "=" * 60 + "[/bold red]")
            console.print(f"[bold red]FAILED: Data mismatch after {elapsed:.1f}s[/bold red]")

            # Detailed failure info
            if counts['source_nodes'] != EXPECTED_NODES or counts['source_rels'] != EXPECTED_RELS:
                console.print("[red]  Source counts don't match expected - generator may have failed[/red]")

            if counts['target_nodes'] != counts['source_nodes']:
                delta = counts['source_nodes'] - counts['target_nodes']
                console.print(f"[red]  Missing {delta} nodes on target[/red]")

            if counts['target_rels'] != counts['source_rels']:
                delta = counts['source_rels'] - counts['target_rels']
                console.print(f"[red]  Missing {delta} relationships on target[/red]")

            console.print()
            console.print("[yellow]Troubleshooting:[/yellow]")
            console.print("  1. Check connector status: curl $KAFKA_CONNECT/connectors/neo4j-master-publisher/status")
            console.print("  2. If cdc-all topic has >1 partition, delete it and re-apply terraform")
            console.print("  3. Run: python verify_cdc.py for detailed diagnostics")
            console.print("[bold red]" + "=" * 60 + "[/bold red]")
            return 1

    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        sys.exit(130)
