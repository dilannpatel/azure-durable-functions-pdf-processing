resource "azurerm_resource_group" "rg" {
  name     = "pdf-processor-rg"
  location = "UK South"
}

resource "azurerm_storage_account" "storage" {
  name                     = "pdfstorage${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "pdf_uploads_container" {
  name                  = "pdf-uploads"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "pdf_results_container" {
  name                  = "pdf-results"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

resource "azurerm_cognitive_account" "openai" {
  name                = "pdf-openai-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "OpenAI"
  sku_name            = "S0"
}

# resource "azurerm_cognitive_deployment" "openai_completion_deployment" {
#   name                 = "gpt-35-turbo" # This is a good, cheap model for summaries
#   cognitive_account_id = azurerm_cognitive_account.openai.id

#   model {
#     format  = "OpenAI"
#     name    = "gpt-35-turbo"
#     version = "0125"
#   }

#   scale {
#     type = "Standard"
#   }
# }

# resource "azurerm_role_assignment" "doc_intel_role" {
#   # This is your Function App's Managed Identity
#   principal_id         = azurerm_linux_function_app.function_app.identity[0].principal_id
#   scope                = azurerm_cognitive_account.doc_intelligence.id
#   role_definition_name = "Cognitive Services User"

#   # Explicitly tell this resource to wait until the
#   # Function App and Doc Intel service are created.
#   depends_on = [
#     azurerm_linux_function_app.function_app,
#     azurerm_cognitive_account.doc_intelligence
#   ]
# }


resource "azurerm_cognitive_account" "doc_intelligence" {
  name                = "doc-intel-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "FormRecognizer" # This is the internal name for Document Intelligence
  sku_name            = "S0"
}


# This deploys the actual "text-embedding-ada-002" model
# inside your OpenAI service.
resource "azurerm_cognitive_deployment" "openai_embedding_deployment" {
  name                 = "text-embedding-ada-002"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-ada-002"
    version = "2"
  }

  scale {
    type = "Standard"
  }
}

resource "azurerm_search_service" "ai_search" {
  name                = "pdf-search-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "standard"
}

resource "azurerm_application_insights" "app_insights" {
  name                = "appi-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
}

resource "azurerm_service_plan" "plan" {
  name                = "python-consumption-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "Y1"
}

resource "azurerm_linux_function_app" "function_app" {
  name                = "pdf-processor-func-${random_string.suffix.result}"
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
      python_version = "3.11" 
    }
  }

  app_settings = {
    "AzureWebJobsStorage"             = azurerm_storage_account.storage.primary_connection_string
    "FUNCTIONS_WORKER_RUNTIME"        = "python"
    "AI_SEARCH_ENDPOINT"              = "https://${azurerm_search_service.ai_search.name}.search.windows.net"
    "AI_SEARCH_API_KEY"               = azurerm_search_service.ai_search.primary_key
    "AI_SEARCH_INDEX_NAME"            = "pdf-index"
    "OPENAI_ENDPOINT"                 = azurerm_cognitive_account.openai.endpoint
    "OPENAI_API_KEY"                  = azurerm_cognitive_account.openai.primary_access_key
    "OPENAI_EMBEDDING_MODEL_NAME"     = "text-embedding-ada-002"
    "APPINSIGHTS_INSTRUMENTATIONKEY" = azurerm_application_insights.app_insights.instrumentation_key
    # "DOC_INTEL_ENDPOINT"              = azurerm_cognitive_account.doc_intelligence.endpoint
    # "OPENAI_COMPLETION_MODEL_NAME"  = azurerm_cognitive_deployment.openai_completion_deployment.name
    
  }
}

resource "azurerm_eventgrid_event_subscription" "pdf_trigger_subscription" {
  count = var.enable_eventgrid_subscription ? 1 : 0

  name  = "pdf-trigger-sub"
  scope = azurerm_storage_account.storage.id 

  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.function_app.id}/functions/event_grid_trigger"
  }

  included_event_types = ["Microsoft.Storage.BlobCreated"]
  
  subject_filter {
    subject_begins_with = "/blobServices/default/containers/pdf-uploads/"
  }
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}