resource "azurerm_eventhub_namespace" "main" {
  name                = var.namespace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = var.sku
  capacity            = var.capacity

  # Note: Kafka API is enabled by default for Standard and Premium SKUs

  tags = var.tags
}

resource "azurerm_eventhub" "topics" {
  for_each = toset(var.topics)

  name                = each.value
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = var.resource_group_name
  partition_count     = var.partition_count
  message_retention   = var.message_retention_days
}

resource "azurerm_eventhub_namespace_authorization_rule" "kafka_connect" {
  name                = "kafka-connect-auth"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = var.resource_group_name

  listen = true
  send   = true
  manage = true
}

resource "azurerm_eventhub_consumer_group" "sink" {
  for_each = toset(var.topics)

  name                = "neo4j-sink-consumer"
  namespace_name      = azurerm_eventhub_namespace.main.name
  eventhub_name       = azurerm_eventhub.topics[each.key].name
  resource_group_name = var.resource_group_name
}
