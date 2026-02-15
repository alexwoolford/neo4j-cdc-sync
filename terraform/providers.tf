terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    neo4jaura = {
      source  = "neo4j-labs/neo4jaura"
      version = "0.0.2-beta"
    }
  }
}

provider "azurerm" {
  features {}
  # Uses credentials from: az login
  # Or set ARM_SUBSCRIPTION_ID environment variable
}

provider "neo4jaura" {
  client_id     = var.aura_client_id
  client_secret = var.aura_client_secret
}
