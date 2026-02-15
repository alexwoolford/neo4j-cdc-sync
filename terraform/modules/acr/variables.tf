variable "registry_name" {
  description = "Name of the Azure Container Registry (must be globally unique, alphanumeric only)"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region for the registry"
  type        = string
}

variable "sku" {
  description = "SKU for ACR (Basic, Standard, or Premium)"
  type        = string
  default     = "Basic"  # Cheapest option, sufficient for demo
}

variable "neo4j_connector_version" {
  description = "Version of Neo4j Kafka Connector to install"
  type        = string
  default     = "5.2.0"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
