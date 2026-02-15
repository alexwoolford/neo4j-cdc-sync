# Demo Data Generators

This folder contains **optional** data generators for testing and demonstrating the CDC pipeline.

**Important**: The CDC infrastructure is completely independent of these generators. Kafka Connect captures ALL node and relationship changes regardless of labels or schema.

## Purpose

These generators are provided for:
- Testing the CDC pipeline after deployment
- Demonstrating CDC with realistic scenarios
- Benchmarking replication performance

You can use your own data instead - CDC will work with any graph schema.

## Available Generators

### social_network.py

Creates a social network graph with people working at companies.

**Schema:**
- `Person` nodes (100): id, name, email
- `Company` nodes (10): id, name, industry
- `WORKS_AT` relationships (100): since property

**Usage:**
```bash
cd generators
python social_network.py
```

## Adding Custom Generators

Create a new Python script following this pattern:

```python
#!/usr/bin/env python3
"""Generator description"""

from utils.neo4j_client import Neo4jClient
from rich.console import Console
import os
from dotenv import load_dotenv

load_dotenv()
console = Console()

def main():
    client = Neo4jClient(
        os.getenv("MASTER_NEO4J_URI"),
        "neo4j",
        os.getenv("MASTER_NEO4J_PASSWORD")
    )

    console.print("[bold blue]Creating sample data...[/bold blue]")

    # Your data generation logic here
    client.execute_write("""
        CREATE (n:YourLabel {property: 'value'})
    """)

    # Verify
    result = client.execute_read("MATCH (n) RETURN count(n) AS count")
    console.print(f"Created {result[0]['count']} nodes")

    client.close()

if __name__ == "__main__":
    main()
```

## Ideas for Additional Generators

- **knowledge_graph.py**: Documents, concepts, and citations
- **supply_chain.py**: Products, warehouses, suppliers, shipments
- **fraud_detection.py**: Accounts, transactions, devices
- **recommendation.py**: Users, products, ratings, purchases
- **biomedical.py**: Genes, proteins, diseases, treatments
