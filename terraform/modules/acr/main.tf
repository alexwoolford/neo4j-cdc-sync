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

  admin_enabled = true  # Required for ACI to pull images

  tags = var.tags
}

# Build and push the Kafka Connect image
# This uses local Docker to build, then pushes to ACR
resource "null_resource" "build_and_push_image" {
  # Trigger rebuild if Dockerfile changes
  triggers = {
    dockerfile_sha = filesha256("${path.root}/../kafka-connect/Dockerfile")
    connector_version = var.neo4j_connector_version
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      cd ${path.root}/../kafka-connect

      # Build the image (linux/amd64 required for Azure Container Instances)
      echo "Building Kafka Connect image with Neo4j connector ${var.neo4j_connector_version}..."
      docker build \
        --platform linux/amd64 \
        --build-arg NEO4J_CONNECTOR_VERSION=${var.neo4j_connector_version} \
        -t neo4j-kafka-connect:${var.neo4j_connector_version} \
        .

      # Tag for ACR
      docker tag neo4j-kafka-connect:${var.neo4j_connector_version} \
        ${azurerm_container_registry.acr.login_server}/neo4j-kafka-connect:${var.neo4j_connector_version}

      # Login to ACR
      echo "Logging into Azure Container Registry..."
      echo '${azurerm_container_registry.acr.admin_password}' | \
        docker login ${azurerm_container_registry.acr.login_server} \
        --username ${azurerm_container_registry.acr.admin_username} \
        --password-stdin

      # Push to ACR
      echo "Pushing image to ACR..."
      docker push ${azurerm_container_registry.acr.login_server}/neo4j-kafka-connect:${var.neo4j_connector_version}

      echo "Image successfully pushed to ACR"
    EOT
  }

  depends_on = [azurerm_container_registry.acr]
}
