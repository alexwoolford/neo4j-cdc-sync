# Azure Container Registry for Kafka Connect image
# This stores our custom neo4j-kafka-connect image

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

resource "azurerm_container_registry" "acr" {
  name                = var.registry_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku

  # Required for ACI image_registry_credential and local docker push in null_resource.
  # For production: set to false and use managed identity for ACI pull + az acr build for image push.
  admin_enabled = var.admin_enabled

  dynamic "georeplications" {
    for_each = var.sku == "Premium" ? var.georeplication_locations : []
    content {
      location                = georeplications.value
      zone_redundancy_enabled = false
    }
  }

  tags = var.tags
}

# Build and push the Kafka Connect image using Azure ACR Tasks
# This builds the image in Azure, eliminating local Docker daemon dependency
resource "null_resource" "build_and_push_image" {
  # Trigger rebuild if Dockerfile changes
  triggers = {
    dockerfile_sha = filesha256("${path.root}/../kafka-connect/Dockerfile")
    connector_version = var.neo4j_connector_version
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Building Kafka Connect image with Neo4j connector ${var.neo4j_connector_version}..."
      echo "Using Azure ACR Tasks (no local Docker required)..."

      # Build image in Azure (not on local machine)
      az acr build \
        --registry ${azurerm_container_registry.acr.name} \
        --image neo4j-kafka-connect:${var.neo4j_connector_version} \
        --platform linux/amd64 \
        --build-arg NEO4J_CONNECTOR_VERSION=${var.neo4j_connector_version} \
        ${path.root}/../kafka-connect

      echo "Image successfully built and pushed to ACR"
    EOT
  }

  depends_on = [azurerm_container_registry.acr]
}

# Build and push the heartbeat sidecar image
# Lightweight Python container that keeps CDC pipeline connections alive
resource "null_resource" "build_and_push_heartbeat" {
  triggers = {
    dockerfile_sha = filesha256("${path.root}/../heartbeat/Dockerfile")
    script_sha     = filesha256("${path.root}/../heartbeat/heartbeat.py")
    requirements   = filesha256("${path.root}/../heartbeat/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Building heartbeat sidecar image..."
      az acr build \
        --registry ${azurerm_container_registry.acr.name} \
        --image cdc-heartbeat:latest \
        --platform linux/amd64 \
        ${path.root}/../heartbeat
      echo "Heartbeat image built and pushed to ACR"
    EOT
  }

  depends_on = [azurerm_container_registry.acr]
}
