resource "azurerm_resource_group" "rg" {
  name     = "pdf-processor-rg"
  location = "UK South"
}

# for Blobs & Function App
resource "azurerm_storage_account" "storage" {
  name                     = "pdfstorage${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

# 3. The Function App (Consumption Plan)
resource "azurerm_service_plan" "plan" {
  name                = "python-consumption-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "Y1" # This is the "Consumption" tier
}

resource "azurerm_linux_function_app" "function_app" {
  name                = "pdf-processor-func-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  service_plan_id            = azurerm_service_plan.plan.id

  site_config {
    application_stack {
      python_version = "3.12"
    }
  }
}

# 4. Azure OpenAI (for Embeddings)
resource "azurerm_cognitive_account" "openai" {
  name                = "pdf-openai-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "OpenAI"
  sku_name            = "S0"
}

# 5. Azure AI Search (Our Vector Database)
resource "azurerm_search_service" "ai_search" {
  name                = "pdf-search-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "standard"
}

# Helper to create unique names
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}