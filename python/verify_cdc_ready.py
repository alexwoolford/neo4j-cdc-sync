#!/usr/bin/env python3
"""
Verify CDC is fully initialized and ready to capture changes.
This must run AFTER Terraform creates the instance but BEFORE writing data.

Usage:
    cd terraform
    export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)
    export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)
    cd ../python
    python verify_cdc_ready.py
"""

import os
import sys

# Add utils to path
sys.path.insert(0, os.path.dirname(__file__))

from utils.neo4j_client import Neo4jClient
from utils.cdc_utils import wait_for_cdc_ready

def main():
    uri = os.getenv('MASTER_NEO4J_URI')
    password = os.getenv('MASTER_NEO4J_PASSWORD')

    if not uri or not password:
        print("Error: Database credentials not set")
        print("\nSet environment variables from terraform output:")
        print("  cd terraform")
        print("  export MASTER_NEO4J_URI=$(terraform output -raw master_neo4j_uri)")
        print("  export MASTER_NEO4J_PASSWORD=$(terraform output -raw master_neo4j_password)")
        sys.exit(1)

    # Connect to master (which has CDC enabled)
    master = Neo4jClient(uri, 'neo4j', password)

    try:
        # Wait for CDC to be ready
        wait_for_cdc_ready(master, timeout_seconds=90)
        print("\n✅ CDC is fully initialized and ready to capture changes")
        print("   Safe to proceed with data population\n")
    finally:
        master.close()

if __name__ == "__main__":
    main()
