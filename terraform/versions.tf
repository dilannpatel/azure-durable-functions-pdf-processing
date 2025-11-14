terraform {
  required_version = "~> 1.5"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.117"
    }
  }

  # Uncomment below to use remote state storage
  # backend "azurerm" {
  #   resource_group_name  = "your-state-rg"
  #   storage_account_name = "your-state-storage"
  #   container_name       = "tfstate"
  #   key                  = "prod.terraform.tfstate"
  # }

}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}