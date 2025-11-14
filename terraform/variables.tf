# Environment
variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "pdf-processor"
}

variable "location" {
  description = "Azure region for the resources"
  type        = string
  default     = "UK South"
}

# Storage configuration
variable "storage_account_tier" {
  description = "Storage account tier"
  type        = string
  default     = "Standard"
}

variable "storage_replication_type" {
  description = "Storage replication type"
  type        = string
  default     = "LRS"
}

# Container names
variable "pdf_uploads_container_name" {
  description = "Name of the container for uploaded PDFs"
  type        = string
  default     = "pdf-uploads"
}

variable "pdf_results_container_name" {
  description = "Name of the container for processing results"
  type        = string
  default     = "pdf-results"
}

# AI and Search configuration
variable "ai_search_sku" {
  description = "SKU for Azure AI Search service"
  type        = string
  default     = "standard"
}

variable "ai_search_index_name" {
  description = "Name of the AI Search index"
  type        = string
  default     = "pdf-index"
}

variable "openai_model_name" {
  description = "OpenAI embedding model name"
  type        = string
  default     = "text-embedding-ada-002"
}

variable "openai_model_version" {
  description = "OpenAI embedding model version"
  type        = string
  default     = "2"
}

variable "log_retention_days" {
  description = "Log Analytics workspace retention in days"
  type        = number
  default     = 30
}

# Event Grid configuration (IMPORTANT)
variable "enable_eventgrid_subscription" {
  description = "Enable Event Grid subscription. Hacky way but set to false first, deploy app code, then set to true."
  type        = bool
  default     = false
}

# Python runtime version
variable "python_version" {
  description = "Python version for Azure Functions"
  type        = string
  default     = "3.11"
}