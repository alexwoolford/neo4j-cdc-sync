output "instance_id" {
  description = "Aura instance ID"
  value       = neo4jaura_instance.this.instance_id
}

output "connection_url" {
  description = "Neo4j connection URI"
  value       = neo4jaura_instance.this.connection_url
}

output "username" {
  description = "Neo4j username"
  value       = neo4jaura_instance.this.username
}

output "password" {
  description = "Neo4j password"
  value       = neo4jaura_instance.this.password
  sensitive   = true
}

output "status" {
  description = "Instance status"
  value       = neo4jaura_instance.this.status
}

output "cdc_enrichment_mode" {
  description = "CDC enrichment mode (OFF, DIFF, FULL)"
  value       = neo4jaura_instance.this.cdc_enrichment_mode
}
