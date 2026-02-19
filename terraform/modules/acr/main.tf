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

# Import base images from Docker Hub into ACR to avoid rate limits during builds
# Uses Docker Hub credentials for authenticated pulls (200 pulls/6h vs 100 anonymous)
resource "null_resource" "import_kafka_connect_base" {
  triggers = {
    registry = azurerm_container_registry.acr.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Importing Confluent Kafka Connect base image into ACR..."
      az acr import \
        --name ${azurerm_container_registry.acr.name} \
        --source docker.io/confluentinc/cp-kafka-connect:7.5.0 \
        --image confluentinc/cp-kafka-connect:7.5.0 \
        --username ${var.dockerhub_username} \
        --password ${var.dockerhub_token} \
        --force
      echo "Base image imported successfully"
    EOT
  }

  depends_on = [azurerm_container_registry.acr]
}

resource "null_resource" "import_python_base" {
  triggers = {
    registry = azurerm_container_registry.acr.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Importing Python base image into ACR..."
      az acr import \
        --name ${azurerm_container_registry.acr.name} \
        --source docker.io/library/python:3.11-slim \
        --image python:3.11-slim \
        --username ${var.dockerhub_username} \
        --password ${var.dockerhub_token} \
        --force
      echo "Base image imported successfully"
    EOT
  }

  depends_on = [azurerm_container_registry.acr]
}

# Build and push the Kafka Connect image using Azure ACR Tasks
# This builds the image in Azure, eliminating local Docker daemon dependency
# Base image is pulled from ACR (imported above) to avoid Docker Hub rate limits
resource "null_resource" "build_and_push_image" {
  # Trigger rebuild if Dockerfile changes
  triggers = {
    dockerfile_sha    = filesha256("${path.root}/../kafka-connect/Dockerfile")
    connector_version = var.neo4j_connector_version
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Building Kafka Connect image with Neo4j connector ${var.neo4j_connector_version}..."
      echo "Using Azure ACR Tasks (no local Docker required)..."

      # Build image in Azure (not on local machine)
      # ACR_LOGIN_SERVER points to cached base image, avoiding Docker Hub rate limits
      az acr build \
        --registry ${azurerm_container_registry.acr.name} \
        --image neo4j-kafka-connect:${var.neo4j_connector_version} \
        --platform linux/amd64 \
        --build-arg ACR_LOGIN_SERVER=${azurerm_container_registry.acr.login_server} \
        --build-arg NEO4J_CONNECTOR_VERSION=${var.neo4j_connector_version} \
        ${path.root}/../kafka-connect

      echo "Image successfully built and pushed to ACR"
    EOT
  }

  depends_on = [
    azurerm_container_registry.acr,
    null_resource.import_kafka_connect_base
  ]
}

# Build and push the heartbeat sidecar image
# Lightweight Python container that keeps CDC pipeline connections alive
# Base image is pulled from ACR (imported above) to avoid Docker Hub rate limits
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
      # ACR_LOGIN_SERVER points to cached base image, avoiding Docker Hub rate limits
      az acr build \
        --registry ${azurerm_container_registry.acr.name} \
        --image cdc-heartbeat:latest \
        --platform linux/amd64 \
        --build-arg ACR_LOGIN_SERVER=${azurerm_container_registry.acr.login_server} \
        ${path.root}/../heartbeat
      echo "Heartbeat image built and pushed to ACR"
    EOT
  }

  depends_on = [
    azurerm_container_registry.acr,
    null_resource.import_python_base
  ]
}
