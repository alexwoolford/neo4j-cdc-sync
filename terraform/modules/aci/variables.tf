variable "container_name" {
  description = "Name of the container group"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region for the container"
  type        = string
}

variable "image_name" {
  description = "Full image name from ACR (e.g., myregistry.azurecr.io/neo4j-kafka-connect:5.2.0)"
  type        = string
}

variable "heartbeat_image_name" {
  description = "Full image name for the heartbeat sidecar (e.g., myregistry.azurecr.io/cdc-heartbeat:latest)"
  type        = string
}

variable "acr_login_server" {
  description = "ACR login server URL"
  type        = string
}

variable "acr_admin_username" {
  description = "ACR admin username"
  type        = string
}

variable "acr_admin_password" {
  description = "ACR admin password"
  type        = string
  sensitive   = true
}

variable "cpu_cores" {
  description = "Number of CPU cores (0.5, 1, 2, or 4)"
  type        = number
  default     = 1
}

variable "memory_gb" {
  description = "Memory in GB (1.5, 3.5, 7, or 14)"
  type        = number
  default     = 1.5
}

variable "event_hubs_fqdn" {
  description = "Event Hubs namespace FQDN"
  type        = string
}

variable "event_hubs_connection_string" {
  description = "Event Hubs connection string (with SAS key)"
  type        = string
  sensitive   = true
}

variable "master_neo4j_uri" {
  description = "Master Neo4j URI"
  type        = string
}

variable "master_neo4j_password" {
  description = "Master Neo4j password"
  type        = string
  sensitive   = true
}

variable "subscriber_neo4j_uri" {
  description = "Subscriber Neo4j URI"
  type        = string
}

variable "subscriber_neo4j_password" {
  description = "Subscriber Neo4j password"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
