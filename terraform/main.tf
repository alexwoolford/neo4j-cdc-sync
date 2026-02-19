# Azure Resource Group
resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-rg"
  location = var.azure_region

  tags = var.tags
}

# Master Neo4j Aura Instance (Authoritative Graph with CDC enabled)
module "aura_master" {
  source = "./modules/aura-instance"

  name           = "${var.project_name}-master"
  memory_gb      = var.aura_instance_memory_gb
  region         = var.azure_region  # Co-locate Aura with Azure resources
  cloud_provider = "azure"
  tenant_id      = var.aura_tenant_id

  # Enable CDC on master to capture change events
  enable_cdc          = true
  cdc_enrichment_mode = "FULL"
}

# Subscriber Neo4j Aura Instance (Replica Graph - CDC not needed)
module "aura_subscriber" {
  source = "./modules/aura-instance"

  name           = "${var.project_name}-subscriber"
  memory_gb      = var.aura_instance_memory_gb
  region         = var.azure_region  # Co-locate Aura with Azure resources
  cloud_provider = "azure"
  tenant_id      = var.aura_tenant_id

  # Subscriber doesn't need CDC - it only receives changes via sink connector
  enable_cdc = false
}

# Azure Event Hubs for CDC
module "event_hubs" {
  source = "./modules/event-hubs"

  namespace_name         = "${var.project_name}-eh"
  location               = azurerm_resource_group.main.location
  resource_group_name    = azurerm_resource_group.main.name
  sku                    = var.event_hubs_sku
  capacity               = var.event_hubs_capacity
  topics                 = var.cdc_topics
  # Single partition ensures strict ordering: nodes arrive before relationships
  partition_count        = 1
  message_retention_days = 7

  tags = var.tags
}

# Azure Container Registry for Kafka Connect image
module "acr" {
  source = "./modules/acr"

  registry_name           = replace("${var.project_name}acr", "-", "")  # ACR names must be alphanumeric
  resource_group_name     = azurerm_resource_group.main.name
  location                = azurerm_resource_group.main.location
  sku                     = "Basic"
  neo4j_connector_version = var.neo4j_connector_version
  dockerhub_username      = var.dockerhub_username
  dockerhub_token         = var.dockerhub_token

  tags = var.tags
}

# Azure Container Instance running Kafka Connect
module "kafka_connect_aci" {
  source = "./modules/aci"

  container_name              = "${var.project_name}-kafka-connect"
  resource_group_name         = azurerm_resource_group.main.name
  location                    = azurerm_resource_group.main.location
  image_name                  = module.acr.image_name
  heartbeat_image_name        = module.acr.heartbeat_image_name
  acr_login_server            = module.acr.acr_login_server
  acr_admin_username          = module.acr.acr_admin_username
  acr_admin_password          = module.acr.acr_admin_password
  cpu_cores                   = 1
  memory_gb                   = 1.5
  event_hubs_fqdn             = module.event_hubs.event_hubs_fqdn
  event_hubs_connection_string = module.event_hubs.kafka_connect_connection_string
  master_neo4j_uri            = module.aura_master.connection_url
  master_neo4j_password       = module.aura_master.password
  subscriber_neo4j_uri        = module.aura_subscriber.connection_url
  subscriber_neo4j_password   = module.aura_subscriber.password

  tags = var.tags

  depends_on = [
    module.aura_master,
    module.aura_subscriber,
    module.event_hubs,
    module.acr
  ]
}
