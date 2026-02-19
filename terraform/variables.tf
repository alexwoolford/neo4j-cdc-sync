variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "neo4j-cdc-demo"
}

variable "azure_region" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "aura_client_id" {
  description = "Neo4j Aura API client ID"
  type        = string
  sensitive   = true
}

variable "aura_client_secret" {
  description = "Neo4j Aura API client secret"
  type        = string
  sensitive   = true
}

variable "aura_tenant_id" {
  description = "Neo4j Aura API tenant ID"
  type        = string
  sensitive   = true
}

variable "aura_instance_memory_gb" {
  description = "Memory size for Aura instances in GB"
  type        = number
  default     = 8
}

variable "aura_instance_storage_gb" {
  description = "Storage size for Aura instances in GB"
  type        = number
  default     = 16
}

variable "event_hubs_sku" {
  description = "Event Hubs namespace SKU (Basic, Standard, or Premium)"
  type        = string
  default     = "Standard"
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.event_hubs_sku)
    error_message = "Event Hubs SKU must be Basic, Standard, or Premium"
  }
}

variable "event_hubs_capacity" {
  description = "Event Hubs throughput units (1-20 for Standard, 1-10 for Premium)"
  type        = number
  default     = 1
}

variable "cdc_topics" {
  description = "List of CDC topics to create in Event Hubs"
  type        = list(string)
  default     = ["cdc-all"]
}

variable "neo4j_connector_version" {
  description = "Version of Neo4j Kafka Connector to install"
  type        = string
  default     = "5.2.0"
}

variable "dockerhub_username" {
  description = "Docker Hub username for authenticated image pulls (avoids rate limits)"
  type        = string
}

variable "dockerhub_token" {
  description = "Docker Hub access token (Account Settings > Security > Access Tokens)"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Environment = "Demo"
    Project     = "Neo4j-CDC-Sync"
    ManagedBy   = "Terraform"
  }
}
