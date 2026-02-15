# Neo4j Aura Master Instance Outputs (Authoritative Graph)
output "master_neo4j_uri" {
  description = "Master Neo4j Aura connection URI"
  value       = module.aura_master.connection_url
}

output "master_neo4j_username" {
  description = "Master Neo4j username"
  value       = module.aura_master.username
}

output "master_neo4j_password" {
  description = "Master Neo4j password"
  value       = module.aura_master.password
  sensitive   = true
}

# Neo4j Aura Subscriber Instance Outputs (Replica Graph)
output "subscriber_neo4j_uri" {
  description = "Subscriber Neo4j Aura connection URI"
  value       = module.aura_subscriber.connection_url
}

output "subscriber_neo4j_username" {
  description = "Subscriber Neo4j username"
  value       = module.aura_subscriber.username
}

output "subscriber_neo4j_password" {
  description = "Subscriber Neo4j password"
  value       = module.aura_subscriber.password
  sensitive   = true
}

# Event Hubs Outputs
output "event_hubs_namespace" {
  description = "Event Hubs namespace name"
  value       = module.event_hubs.namespace_name
}

output "event_hubs_fqdn" {
  description = "Event Hubs namespace FQDN for Kafka connections"
  value       = module.event_hubs.namespace_fqdn
}

output "event_hubs_connection_string" {
  description = "Event Hubs connection string for Kafka Connect"
  value       = module.event_hubs.primary_connection_string
  sensitive   = true
}

output "event_hubs_topics" {
  description = "List of created Event Hubs topics"
  value       = module.event_hubs.topic_names
}

output "resource_group_name" {
  description = "Azure resource group name"
  value       = azurerm_resource_group.main.name
}

output "azure_region" {
  description = "Azure region where resources are deployed"
  value       = azurerm_resource_group.main.location
}

# Kafka Connect Outputs (runs on Azure Container Instance)
output "kafka_connect_ip" {
  description = "Public IP address of Kafka Connect running on Azure"
  value       = module.kafka_connect_aci.kafka_connect_ip
}

output "kafka_connect_rest_api" {
  description = "Kafka Connect REST API endpoint"
  value       = module.kafka_connect_aci.kafka_connect_rest_api
}

# Summary output for deployment success
output "deployment_summary" {
  description = "Summary of deployed resources"
  value = <<-EOT

    ========================================
    Neo4j CDC Sync - Deployment Complete!
    ========================================

    Master Neo4j:     ${module.aura_master.connection_url}
    Subscriber Neo4j: ${module.aura_subscriber.connection_url}
    Event Hubs:       ${module.event_hubs.namespace_fqdn}
    Kafka Connect:    ${module.kafka_connect_aci.kafka_connect_rest_api}

    Kafka Connect is running on Azure Container Instance.
    Connectors have been automatically deployed.

    Get credentials:
      terraform output master_neo4j_password
      terraform output subscriber_neo4j_password

    Verify connectors:
      curl ${module.kafka_connect_aci.kafka_connect_rest_api}/connectors

    Check connector status:
      curl ${module.kafka_connect_aci.kafka_connect_rest_api}/connectors/neo4j-master-publisher/status
      curl ${module.kafka_connect_aci.kafka_connect_rest_api}/connectors/neo4j-subscriber-consumer/status

    Destroy all resources:
      terraform destroy

  EOT
}
