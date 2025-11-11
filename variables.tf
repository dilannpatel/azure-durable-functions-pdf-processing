variable "enable_eventgrid_subscription" {
  description = "Controls if the Event Grid subscription is created. Deploy with 'false', then deploy code, then 'true'."
  type        = bool
  default     = false
}