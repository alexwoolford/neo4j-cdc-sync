# Azure Container Instance for Kafka Connect
# Runs Kafka Connect 24/7 in Azure

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

resource "azurerm_container_group" "kafka_connect" {
  name                = var.container_name
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  restart_policy      = "Always"  # Auto-restart on failure

  # Container running Kafka Connect
  container {
    name   = "kafka-connect"
    image  = var.image_name
    cpu    = var.cpu_cores
    memory = var.memory_gb

    # Kafka Connect REST API port
    ports {
      port     = 8083
      protocol = "TCP"
    }

    # Environment variables for Kafka Connect configuration
    environment_variables = {
      CONNECT_BOOTSTRAP_SERVERS                    = "${var.event_hubs_fqdn}:9093"
      CONNECT_REST_PORT                            = "8083"
      CONNECT_GROUP_ID                             = "neo4j-cdc-connect-group"
      CONNECT_CONFIG_STORAGE_TOPIC                 = "connect-configs"
      CONNECT_OFFSET_STORAGE_TOPIC                 = "connect-offsets"
      CONNECT_STATUS_STORAGE_TOPIC                 = "connect-status"
      CONNECT_CONFIG_STORAGE_REPLICATION_FACTOR    = "1"
      CONNECT_OFFSET_STORAGE_REPLICATION_FACTOR    = "1"
      CONNECT_STATUS_STORAGE_REPLICATION_FACTOR    = "1"

      CONNECT_SECURITY_PROTOCOL                    = "SASL_SSL"
      CONNECT_SASL_MECHANISM                       = "PLAIN"

      CONNECT_PRODUCER_BOOTSTRAP_SERVERS           = "${var.event_hubs_fqdn}:9093"
      CONNECT_PRODUCER_SECURITY_PROTOCOL           = "SASL_SSL"
      CONNECT_PRODUCER_SASL_MECHANISM              = "PLAIN"
      CONNECT_PRODUCER_REQUEST_TIMEOUT_MS          = "30000"
      CONNECT_PRODUCER_MAX_BLOCK_MS                = "30000"

      CONNECT_CONSUMER_BOOTSTRAP_SERVERS           = "${var.event_hubs_fqdn}:9093"
      CONNECT_CONSUMER_SECURITY_PROTOCOL           = "SASL_SSL"
      CONNECT_CONSUMER_SASL_MECHANISM              = "PLAIN"
      CONNECT_CONSUMER_REQUEST_TIMEOUT_MS          = "30000"
      CONNECT_CONSUMER_SESSION_TIMEOUT_MS          = "30000"
      CONNECT_CONSUMER_HEARTBEAT_INTERVAL_MS       = "10000"
      CONNECT_CONSUMER_GROUP_ID                    = "neo4j-cdc-consumer"

      CONNECT_KEY_CONVERTER                        = "org.apache.kafka.connect.json.JsonConverter"
      CONNECT_VALUE_CONVERTER                      = "org.apache.kafka.connect.json.JsonConverter"
      CONNECT_KEY_CONVERTER_SCHEMAS_ENABLE         = "false"
      CONNECT_VALUE_CONVERTER_SCHEMAS_ENABLE       = "false"

      CONNECT_INTERNAL_KEY_CONVERTER               = "org.apache.kafka.connect.json.JsonConverter"
      CONNECT_INTERNAL_VALUE_CONVERTER             = "org.apache.kafka.connect.json.JsonConverter"
      CONNECT_INTERNAL_KEY_CONVERTER_SCHEMAS_ENABLE = "false"
      CONNECT_INTERNAL_VALUE_CONVERTER_SCHEMAS_ENABLE = "false"

      CONNECT_REST_ADVERTISED_HOST_NAME            = var.container_name
      CONNECT_PLUGIN_PATH                          = "/usr/share/java,/usr/share/confluent-hub-components,/etc/kafka-connect/jars"
      CONNECT_LOG4J_ROOT_LOGLEVEL                  = "INFO"
      CONNECT_LOG4J_LOGGERS                        = "org.neo4j.connectors.kafka=INFO,org.apache.kafka.connect=INFO"
      CUB_CLASSPATH                                = "/usr/share/java/confluent-common/*:/usr/share/java/kafka/*:/usr/share/java/cp-base-new/*"
    }

    # Sensitive environment variables (JAAS configs with Event Hubs connection string)
    secure_environment_variables = {
      CONNECT_SASL_JAAS_CONFIG = "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"$ConnectionString\" password=\"${var.event_hubs_connection_string}\";"
      CONNECT_PRODUCER_SASL_JAAS_CONFIG = "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"$ConnectionString\" password=\"${var.event_hubs_connection_string}\";"
      CONNECT_CONSUMER_SASL_JAAS_CONFIG = "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"$ConnectionString\" password=\"${var.event_hubs_connection_string}\";"
    }

    # Liveness probe - ensures container is restarted if unhealthy
    liveness_probe {
      http_get {
        path   = "/"
        port   = 8083
        scheme = "Http"
      }
      initial_delay_seconds = 60
      period_seconds        = 30
      failure_threshold     = 3
      timeout_seconds       = 10
    }

    # Readiness probe - ensures traffic only goes to healthy container
    readiness_probe {
      http_get {
        path   = "/"
        port   = 8083
        scheme = "Http"
      }
      initial_delay_seconds = 30
      period_seconds        = 10
      failure_threshold     = 3
      timeout_seconds       = 10
    }
  }

  # Pull image from ACR using credentials
  image_registry_credential {
    server   = var.acr_login_server
    username = var.acr_admin_username
    password = var.acr_admin_password
  }

  # Public IP for access (alternative: use VNet integration)
  ip_address_type = "Public"

  tags = var.tags
}

# Deploy Neo4j CDC connectors via Python script
# Uses PUT for idempotent deployment, verifies tasks reach RUNNING state
resource "null_resource" "deploy_connectors" {
  # Trigger redeployment if credentials or URIs change
  triggers = {
    master_uri     = var.master_neo4j_uri
    subscriber_uri = var.subscriber_neo4j_uri
    eventhubs_fqdn = var.event_hubs_fqdn
    container_ip   = azurerm_container_group.kafka_connect.ip_address
  }

  provisioner "local-exec" {
    command = "python3 ${path.module}/../../scripts/configure_connectors.py"

    # Pass secrets via environment variables (never written to disk)
    environment = {
      CONNECT_URL               = "http://${azurerm_container_group.kafka_connect.ip_address}:8083"
      MASTER_NEO4J_URI          = var.master_neo4j_uri
      MASTER_NEO4J_PASSWORD     = var.master_neo4j_password
      SUBSCRIBER_NEO4J_URI      = var.subscriber_neo4j_uri
      SUBSCRIBER_NEO4J_PASSWORD = var.subscriber_neo4j_password
    }
  }

  depends_on = [azurerm_container_group.kafka_connect]
}
