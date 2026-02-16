variable "namespace_name" {
  description = "Name of the Event Hubs namespace"
  type        = string
}

variable "location" {
  description = "Azure region for Event Hubs"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the Azure resource group"
  type        = string
}

variable "sku" {
  description = "Event Hubs namespace SKU (Basic, Standard, or Premium)"
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "SKU must be Basic, Standard, or Premium"
  }
}

variable "capacity" {
  description = "Throughput units for Event Hubs namespace (1-20 for Standard)"
  type        = number
  default     = 1

  validation {
    condition     = var.capacity >= 1 && var.capacity <= 20
    error_message = "Capacity must be between 1 and 20"
  }
}

variable "topics" {
  description = "List of Event Hub topics to create"
  type        = list(string)
  default     = ["neo4j-cdc-node", "neo4j-cdc-relationship"]
}

variable "partition_count" {
  description = "Number of partitions for each Event Hub. Use 1 for CDC to ensure strict ordering."
  type        = number
  default     = 1

  validation {
    condition     = var.partition_count >= 1 && var.partition_count <= 32
    error_message = "Partition count must be between 1 and 32"
  }
}

variable "message_retention_days" {
  description = "Message retention in days (1-7 for Standard)"
  type        = number
  default     = 7

  validation {
    condition     = var.message_retention_days >= 1 && var.message_retention_days <= 7
    error_message = "Message retention must be between 1 and 7 days for Standard SKU"
  }
}

variable "tags" {
  description = "Tags to apply to Event Hubs resources"
  type        = map(string)
  default     = {}
}
