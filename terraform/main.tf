resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}


resource "azurerm_resource_group" "rg" {
  name     = "${var.project_name}-rg-${var.environment}"
  location = var.location
}

# Storage Account & Containers
resource "azurerm_storage_account" "storage" {
  name                     = "${replace(var.project_name, "-", "")}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = var.storage_account_tier
  account_replication_type = var.storage_replication_type

  depends_on = [azurerm_resource_group.rg]
}

resource "azurerm_storage_container" "pdf_uploads_container" {
  name                  = var.pdf_uploads_container_name
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"

  depends_on = [azurerm_storage_account.storage]
}

resource "azurerm_storage_container" "pdf_results_container" {
  name                  = var.pdf_results_container_name
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"

  depends_on = [azurerm_storage_account.storage]
}



resource "azurerm_cognitive_account" "openai" {
  name                = "${var.project_name}-openai-${random_string.suffix.result}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "OpenAI"
  sku_name            = "S0"

  depends_on = [azurerm_resource_group.rg]
}


resource "azurerm_cognitive_account" "doc_intelligence" {
  name                = "${var.project_name}-docint-${random_string.suffix.result}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "FormRecognizer"
  sku_name            = "S0"

  depends_on = [azurerm_resource_group.rg]
}

resource "azurerm_search_service" "ai_search" {
  name                = "${var.project_name}-search-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = var.ai_search_sku

  depends_on = [azurerm_resource_group.rg]
}

resource "azurerm_cognitive_deployment" "openai_embedding_deployment" {
  name                 = var.openai_model_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }
  scale {
    type = "Standard"
  }
}


resource "azurerm_log_analytics_workspace" "logs" {
  name                = "${var.project_name}-logs-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days

  depends_on = [azurerm_resource_group.rg]
}

resource "azurerm_application_insights" "app_insights" {
  name                = "${var.project_name}-appinsights-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.logs.id

  depends_on = [azurerm_log_analytics_workspace.logs]
}


resource "azurerm_service_plan" "plan" {
  name                = "${var.project_name}-plan-${var.environment}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption plan

  depends_on = [azurerm_resource_group.rg]
}

# Linux Function App
resource "azurerm_linux_function_app" "function_app" {
  name                = "${var.project_name}-func-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  service_plan_id            = azurerm_service_plan.plan.id

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = var.python_version
    }
  }

  app_settings = {
    "AzureWebJobsStorage"        = azurerm_storage_account.storage.primary_connection_string
    "FUNCTIONS_WORKER_RUNTIME"   = "python"
    "FUNCTIONS_EXTENSION_VERSION" = "~4"

    "PDF_UPLOADS_CONTAINER"      = var.pdf_uploads_container_name
    "PDF_RESULTS_CONTAINER"      = var.pdf_results_container_name

    "AI_SEARCH_ENDPOINT"         = "https://${azurerm_search_service.ai_search.name}.search.windows.net"
    "AI_SEARCH_API_KEY"          = azurerm_search_service.ai_search.primary_key
    "AI_SEARCH_INDEX_NAME"       = var.ai_search_index_name

    "OPENAI_ENDPOINT"            = azurerm_cognitive_account.openai.endpoint
    "OPENAI_API_KEY"             = azurerm_cognitive_account.openai.primary_access_key
    "OPENAI_EMBEDDING_MODEL_NAME" = var.openai_model_name

    "APPINSIGHTS_INSTRUMENTATIONKEY" = azurerm_application_insights.app_insights.instrumentation_key
  }

  depends_on = [
    azurerm_storage_account.storage,
    azurerm_service_plan.plan,
    azurerm_search_service.ai_search,
    azurerm_cognitive_account.openai
  ]
}


# IMPORTANT: Deploy with enable_eventgrid_subscription = false first
# Deploy your function app code, then set to true and apply again
resource "azurerm_eventgrid_event_subscription" "pdf_trigger_subscription" {
  count = var.enable_eventgrid_subscription ? 1 : 0

  name  = "${var.project_name}-trigger-sub"
  scope = azurerm_storage_account.storage.id

  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.function_app.id}/functions/event_grid_trigger"
  }

  included_event_types = ["Microsoft.Storage.BlobCreated"]

  subject_filter {
    subject_begins_with = "/blobServices/default/containers/${var.pdf_uploads_container_name}/"
  }

  depends_on = [azurerm_linux_function_app.function_app]
}

























