output "kafka_connect_ip" {
  description = "Public IP address of Kafka Connect"
  value       = azurerm_container_group.kafka_connect.ip_address
}

output "kafka_connect_fqdn" {
  description = "FQDN of Kafka Connect (if assigned)"
  value       = azurerm_container_group.kafka_connect.fqdn
}

output "kafka_connect_rest_api" {
  description = "Kafka Connect REST API endpoint"
  value       = "http://${azurerm_container_group.kafka_connect.ip_address}:8083"
}

output "container_group_id" {
  description = "Resource ID of the container group"
  value       = azurerm_container_group.kafka_connect.id
}
