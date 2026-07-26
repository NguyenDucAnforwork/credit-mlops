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
  default     = "asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-api@sha256:ea8eee11bcb7e79210c90406c76441c91d5b6d07b96625a2a912ba7405665c38"
}

variable "job_image" {
  description = "Artifact Registry image URI for ETL and monitoring jobs."
  type        = string
  default     = "asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-job@sha256:e5ca3820cd41e98d5de0e66fef006b097dff694c05212251a29953332526a8be"
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
