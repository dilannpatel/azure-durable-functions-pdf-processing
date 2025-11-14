output "function_app_name" {
  description = "The name of the deployed Function App"
  value       = azurerm_linux_function_app.function_app.name
}

output "function_app_id" {
  description = "ID of the deployed Azure Function App"
  value       = azurerm_linux_function_app.function_app.id
}

output "resource_group_name" {
  description = "Name of the Resource Group"
  value       = azurerm_resource_group.rg.name
}


output "storage_account_name" {
  description = "Name of the Storage Account"
  value       = azurerm_storage_account.storage.name
}

output "storage_connection_string" {
  description = "Connection string for the main storage account"
  value       = azurerm_storage_account.storage.primary_connection_string
  sensitive   = true
}

output "ai_search_endpoint" {
  description = "Endpoint URL for the Azure AI Search service"
  value       = "https://${azurerm_search_service.ai_search.name}.search.windows.net"
}

output "ai_search_primary_key" {
  description = "Admin API Key for the Azure AI Search service"
  value       = azurerm_search_service.ai_search.primary_key
  sensitive   = true
}

output "openai_endpoint" {
  description = "Endpoint URL for the Azure OpenAI service"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "openai_primary_key" {
  description = "API Key for the Azure OpenAI service"
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
}
