#
# Neo4j Aura Instance Module
# Creates a Neo4j Aura instance with CDC enabled using neo4jaura provider
#

resource "neo4jaura_instance" "this" {
  name           = var.name
  memory         = "${var.memory_gb}GB"
  region         = var.region
  type           = "business-critical"
  project_id     = var.tenant_id
  cloud_provider = var.cloud_provider

  # Enable Change Data Capture
  # Options: OFF, DIFF, FULL
  # Set to OFF for subscriber instances (they only receive changes via sink connector)
  cdc_enrichment_mode = var.enable_cdc ? var.cdc_enrichment_mode : "OFF"
}
