variable "name" {
  description = "Name of the Aura instance"
  type        = string
}

variable "memory_gb" {
  description = "Memory in GB (e.g., 2, 4, 8)"
  type        = number
  default     = 8
}

variable "region" {
  description = "Cloud region (e.g., azure-eastus)"
  type        = string
}

variable "cloud_provider" {
  description = "Cloud provider (azure, gcp, aws)"
  type        = string
  default     = "azure"
}

variable "tenant_id" {
  description = "Aura tenant ID"
  type        = string
}

variable "enable_cdc" {
  description = "Enable Change Data Capture (requires business-critical tier)"
  type        = bool
  default     = false
}

variable "cdc_enrichment_mode" {
  description = "CDC enrichment mode: OFF, DIFF, or FULL (only used if enable_cdc is true)"
  type        = string
  default     = "FULL"
  validation {
    condition     = contains(["OFF", "DIFF", "FULL"], var.cdc_enrichment_mode)
    error_message = "cdc_enrichment_mode must be OFF, DIFF, or FULL"
  }
}
