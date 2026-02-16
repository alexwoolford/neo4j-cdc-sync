"""Neo4j client utility for database operations."""

from typing import Dict, Any, List, Optional
import logging
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import Neo4jError

# Suppress Neo4j driver notification warnings about non-existent labels/properties
# (expected when polling a subscriber database that hasn't received data yet)
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


class Neo4jClient:
    """Client for interacting with Neo4j database."""

    def __init__(self, uri: str, username: str, password: str):
        """
        Initialize Neo4j client.

        Args:
            uri: Neo4j connection URI (neo4j+s://...)
            username: Database username (usually 'neo4j')
            password: Database password
        """
        self.uri = uri
        self.username = username
        self.driver: Driver = GraphDatabase.driver(uri, auth=(username, password))

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a write query (CREATE, MERGE, UPDATE, DELETE).

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.execute_write(
                    lambda tx: tx.run(query, parameters or {}).data()
                )
                return result
        except Neo4jError as e:
            print(f"Error executing write query: {e}")
            raise

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a read query (MATCH, RETURN).

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.execute_read(
                    lambda tx: tx.run(query, parameters or {}).data()
                )
                return result
        except Neo4jError as e:
            print(f"Error executing read query: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test if the database connection is working.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS num")
                return result.single()["num"] == 1
        except Neo4jError as e:
            print(f"Connection test failed: {e}")
            return False

    def get_node_count(self) -> int:
        """
        Get total number of nodes in the database.

        Returns:
            Node count
        """
        result = self.execute_read("MATCH (n) RETURN count(n) AS count")
        return result[0]["count"] if result else 0

    def get_relationship_count(self) -> int:
        """
        Get total number of relationships in the database.

        Returns:
            Relationship count
        """
        result = self.execute_read("MATCH ()-[r]->() RETURN count(r) AS count")
        return result[0]["count"] if result else 0

    def get_label_counts(self) -> Dict[str, int]:
        """
        Get count of nodes for each label.

        Returns:
            Dictionary mapping label names to counts
        """
        result = self.execute_read("""
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count
            ORDER BY count DESC
        """)
        return {record["label"]: record["count"] for record in result}

    def clear_database(self) -> None:
        """
        Clear all nodes and relationships from the database.
        Use with caution!
        """
        self.execute_write("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        """Close the database connection."""
        self.driver.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
