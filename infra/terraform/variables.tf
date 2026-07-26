variable "project_id" {
  description = "GCP project ID for the demo deployment."
  type        = string
  default     = "driven-reef-452414-b5"
}

variable "region" {
  description = "GCP region for regional resources."
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "GCP zone used by VM fallback documentation."
  type        = string
  default     = "asia-southeast1-a"
}

variable "environment" {
  description = "Short environment name used in resource names."
  type        = string
  default     = "demo"
}

variable "api_image" {
  description = "Artifact Registry image URI for the FastAPI service."
  type        = string
  default     = "asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-api@sha256:b4e4dcd3afd7171a29b808afe45fc913d9c8b4a35d8e1b273f14dd725650f0d6"
}

variable "job_image" {
  description = "Artifact Registry image URI for ETL and monitoring jobs."
  type        = string
  default     = "asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-job@sha256:d74322f93c6b0fb33176cfb3208835303a5d960e6edeaefd60cade902a2b03a1"
}

variable "enable_cloud_sql" {
  description = "Create Cloud SQL PostgreSQL resources. Keep false until cost is approved."
  type        = bool
  default     = false
}

variable "cloud_sql_tier" {
  description = "Cloud SQL tier used only when enable_cloud_sql is true."
  type        = string
  default     = "db-f1-micro"
}
