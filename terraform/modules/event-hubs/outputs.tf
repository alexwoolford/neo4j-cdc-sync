output "namespace_id" {
  description = "Event Hubs namespace ID"
  value       = azurerm_eventhub_namespace.main.id
}

output "namespace_name" {
  description = "Event Hubs namespace name"
  value       = azurerm_eventhub_namespace.main.name
}

output "namespace_fqdn" {
  description = "Event Hubs namespace FQDN for Kafka API connections"
  value       = "${azurerm_eventhub_namespace.main.name}.servicebus.windows.net"
}

output "event_hubs_fqdn" {
  description = "Alias for namespace_fqdn"
  value       = "${azurerm_eventhub_namespace.main.name}.servicebus.windows.net"
}

output "primary_connection_string" {
  description = "Primary connection string for Kafka Connect"
  value       = azurerm_eventhub_namespace_authorization_rule.kafka_connect.primary_connection_string
  sensitive   = true
}

output "kafka_connect_connection_string" {
  description = "Alias for primary_connection_string"
  value       = azurerm_eventhub_namespace_authorization_rule.kafka_connect.primary_connection_string
  sensitive   = true
}

output "secondary_connection_string" {
  description = "Secondary connection string for failover"
  value       = azurerm_eventhub_namespace_authorization_rule.kafka_connect.secondary_connection_string
  sensitive   = true
}

output "topic_names" {
  description = "List of created Event Hub topic names"
  value       = [for topic in azurerm_eventhub.topics : topic.name]
}

output "topic_ids" {
  description = "Map of topic names to IDs"
  value       = { for k, topic in azurerm_eventhub.topics : k => topic.id }
}

output "consumer_groups" {
  description = "Map of consumer group names"
  value       = { for k, cg in azurerm_eventhub_consumer_group.sink : k => cg.name }
}
