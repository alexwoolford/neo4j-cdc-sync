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
  description = "SKU for ACR (Basic, Standard, or Premium). Geo-replication only applies to Premium."
  type        = string
  default     = "Basic"  # Cheapest option, sufficient for demo
}

variable "admin_enabled" {
  description = "Enable admin user for ACR. Required for ACI pull + local docker push in this demo. Set to false in production and use managed identity + az acr build."
  type        = bool
  default     = true
}

variable "georeplication_locations" {
  description = "Optional list of Azure regions for ACR geo-replication (Premium SKU only). Example: [\"eastus2\"]"
  type        = list(string)
  default     = []
}

variable "neo4j_connector_version" {
  description = "Version of Neo4j Kafka Connector to install"
  type        = string
  default     = "5.2.0"
}

variable "dockerhub_username" {
  description = "Docker Hub username for authenticated image imports"
  type        = string
}

variable "dockerhub_token" {
  description = "Docker Hub access token for authenticated image imports"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
