output "artifact_registry_repository" {
  description = "Artifact Registry repository for container images."
  value       = google_artifact_registry_repository.images.name
}

output "property_snapshot_bucket" {
  description = "GCS bucket for property snapshots."
  value       = google_storage_bucket.property_snapshots.name
}

output "bigquery_dataset" {
  description = "BigQuery dataset for property intelligence tables."
  value       = google_bigquery_dataset.property.dataset_id
}

output "cloud_run_api_name" {
  description = "Cloud Run API service name."
  value       = google_cloud_run_v2_service.api.name
}

output "cloud_run_api_uri" {
  description = "Cloud Run API service URI after deployment."
  value       = google_cloud_run_v2_service.api.uri
}

output "cloud_run_etl_job_name" {
  description = "Cloud Run ETL job name."
  value       = google_cloud_run_v2_job.etl.name
}

output "cloud_sql_instance" {
  description = "Cloud SQL instance name when enable_cloud_sql is true."
  value       = var.enable_cloud_sql ? google_sql_database_instance.postgis[0].name : "disabled"
}
