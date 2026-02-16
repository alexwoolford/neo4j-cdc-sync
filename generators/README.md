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

**Important — warm the pipeline first**

If the CDC pipeline has been idle, Azure Event Hubs connections can be stale and the bulk load may not replicate. Before running the generator:

1. **Warm up the pipeline** (from repo root):
   ```bash
   cd terraform
   export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)
   export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)
   export SUBSCRIBER_NEO4J_URI=$(terraform output -raw subscriber_neo4j_uri)
   export SUBSCRIBER_NEO4J_PASSWORD=$(terraform output -raw subscriber_neo4j_password)
   cd ../python
   python test_live_cdc.py
   ```
   This ensures the connectors are talking to Event Hubs before you do a big write.

2. **Run the generator**:
   ```bash
   cd ../generators
   python social_network.py
   ```

3. **Wait for propagation** — a bulk load of 110 nodes + 445 relationships can take 1–2 minutes to flow through. Then verify:
   ```bash
   cd ../python
   python verify_cdc.py
   ```

## Troubleshooting: Missing Relationships

If `verify_cdc.py` shows matching node counts but fewer relationships on the subscriber, the most likely cause is **topic partition ordering**.

The CDC topic (`cdc-all`) must have **exactly 1 partition** so Kafka preserves the order of events (nodes before relationships). The pipeline is configured with `topic.creation.default.partitions: 1` in `terraform/scripts/configure_connectors.py`.

**If the topic was created with more than 1 partition** (e.g., from an older deployment):

1. Delete the `cdc-all` Event Hub in the Azure portal, or
2. Run `terraform destroy && terraform apply` for a clean slate

After recreation, the source connector will create `cdc-all` with 1 partition, and relationships will no longer be lost.

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
