output "acr_login_server" {
  description = "Login server URL for the container registry"
  value       = azurerm_container_registry.acr.login_server
}

output "acr_admin_username" {
  description = "Admin username for the container registry"
  value       = azurerm_container_registry.acr.admin_username
}

output "acr_admin_password" {
  description = "Admin password for the container registry"
  value       = azurerm_container_registry.acr.admin_password
  sensitive   = true
}

output "image_name" {
  description = "Full image name in ACR"
  value       = "${azurerm_container_registry.acr.login_server}/neo4j-kafka-connect:${var.neo4j_connector_version}"
}

output "acr_id" {
  description = "Resource ID of the container registry"
  value       = azurerm_container_registry.acr.id
}
