#!/usr/bin/env python3
"""
Social Network Demo Data Generator

Creates a sample social network graph with people working at companies.
This is OPTIONAL - CDC works with any graph schema.

Usage:
    # Set env vars from terraform output, then run:
    cd terraform
    export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)
    export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)
    cd ../generators
    python social_network.py
"""

import os
import sys
from pathlib import Path

# Add python directory to path for utils
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from rich.console import Console
from rich.table import Table
from utils.neo4j_client import Neo4jClient


console = Console()


def main():
    """Initialize master graph with sample data."""
    source_uri = os.getenv("MASTER_NEO4J_URI")
    source_username = os.getenv("MASTER_NEO4J_USERNAME", "neo4j")
    source_password = os.getenv("MASTER_NEO4J_PASSWORD")

    if not source_uri or not source_password:
        console.print("[bold red]Error: Database credentials not set[/bold red]")
        console.print("\nSet environment variables from terraform output:")
        console.print("  cd terraform")
        console.print("  export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)")
        console.print("  export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)")
        sys.exit(1)

    console.print(f"[bold blue]Connecting to master graph:[/bold blue] {source_uri}")

    # Connect to master graph
    with Neo4jClient(source_uri, source_username, source_password) as client:
        # Test connection
        if not client.test_connection():
            console.print("[bold red]Failed to connect to master graph![/bold red]")
            sys.exit(1)

        console.print("[bold green]Connected successfully![/bold green]\n")

        # Clear existing data (optional - comment out if you want to keep existing data)
        console.print("[yellow]Clearing existing data...[/yellow]")
        client.clear_database()

        # Create constraints
        console.print("[bold blue]Creating constraints and indexes...[/bold blue]")
        client.execute_write(
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE"
        )
        client.execute_write(
            "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE"
        )
        console.print("[green]Constraints created successfully[/green]\n")

        # Create companies
        console.print("[bold blue]Creating 10 companies...[/bold blue]")
        client.execute_write("""
            UNWIND range(1, 10) AS id
            CREATE (c:Company {
                id: id,
                name: 'Company ' + toString(id),
                industry: CASE id % 3
                    WHEN 0 THEN 'Technology'
                    WHEN 1 THEN 'Finance'
                    ELSE 'Healthcare'
                END,
                founded: 2000 + id,
                employees: (id * 100) + 50
            })
        """)
        console.print("[green]Companies created successfully[/green]\n")

        # Create people (nodes only) so CDC has all nodes before relationship events
        console.print("[bold blue]Creating 100 people...[/bold blue]")
        client.execute_write("""
            UNWIND range(1, 100) AS id
            CREATE (p:Person {
                id: id,
                name: 'Person ' + toString(id),
                email: 'person' + toString(id) + '@example.com',
                age: 25 + (id % 40),
                department: CASE id % 4
                    WHEN 0 THEN 'Engineering'
                    WHEN 1 THEN 'Sales'
                    WHEN 2 THEN 'Marketing'
                    ELSE 'Operations'
                END
            })
        """)
        console.print("[green]People created successfully[/green]\n")

        # Create WORKS_AT relationships (after all nodes exist — helps CDC ordering)
        console.print("[bold blue]Creating WORKS_AT relationships...[/bold blue]")
        client.execute_write("""
            UNWIND range(1, 100) AS id
            MATCH (p:Person {id: id}), (c:Company {id: (id % 10) + 1})
            CREATE (p)-[:WORKS_AT {
                since: date({year: 2015 + (id % 8), month: (id % 12) + 1, day: 1}),
                role: CASE id % 3
                    WHEN 0 THEN 'Senior'
                    WHEN 1 THEN 'Junior'
                    ELSE 'Manager'
                END
            }]->(c)
        """)
        console.print("[green]WORKS_AT relationships created successfully[/green]\n")

        # Create some KNOWS relationships between people
        console.print("[bold blue]Creating social connections between people...[/bold blue]")
        client.execute_write("""
            MATCH (p1:Person), (p2:Person)
            WHERE p1.id < p2.id AND p1.id % 10 = p2.id % 10 AND p1.id < 50
            CREATE (p1)-[:KNOWS {
                since: date({year: 2018 + (p1.id % 5), month: 1, day: 1}),
                relationship: 'Colleague'
            }]->(p2)
        """)
        console.print("[green]Social connections created successfully[/green]\n")

        # Get statistics
        node_count = client.get_node_count()
        rel_count = client.get_relationship_count()
        label_counts = client.get_label_counts()

        # Display summary table
        table = Table(title="Source Database Summary")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta")

        table.add_row("Total Nodes", str(node_count))
        table.add_row("Total Relationships", str(rel_count))
        table.add_row("", "")  # Separator

        for label, count in label_counts.items():
            table.add_row(f"{label} Nodes", str(count))

        console.print(table)
        console.print("\n[bold green]Master graph initialized successfully![/bold green]")
        console.print("[bold yellow]CDC will now capture all changes to this database.[/bold yellow]")


if __name__ == "__main__":
    main()
