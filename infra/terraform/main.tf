locals {
  name_prefix = "credit-mlops-${var.environment}"
  labels = {
    app         = "credit-mlops"
    component   = "property-intelligence"
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "credit-mlops"
  description   = "Container images for the Property Intelligence demo"
  format        = "DOCKER"
  labels        = local.labels

}

resource "google_storage_bucket" "property_snapshots" {
  project                     = var.project_id
  name                        = "${var.project_id}-property-snapshots-${var.environment}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  labels                      = local.labels

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_bigquery_dataset" "property" {
  project                    = var.project_id
  dataset_id                 = "property_intelligence_${var.environment}"
  friendly_name              = "Property Intelligence ${var.environment}"
  description                = "Silver and gold property listing tables for the demo"
  location                   = var.region
  delete_contents_on_destroy = false
  labels                     = local.labels

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "mlflow_tracking_uri" {
  project   = var.project_id
  secret_id = "${local.name_prefix}-mlflow-tracking-uri"
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "run" {
  project      = var.project_id
  account_id   = "credit-mlops-run-${var.environment}"
  display_name = "Credit MLOps Cloud Run ${var.environment}"
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "credit-mlops-scheduler-${var.environment}"
  display_name = "Credit MLOps Scheduler ${var.environment}"
}

resource "google_project_iam_member" "run_roles" {
  for_each = toset([
    "roles/artifactregistry.reader",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_run_v2_service" "api" {
  project  = var.project_id
  name     = "${local.name_prefix}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  labels   = local.labels

  template {
    service_account = google_service_account.run.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8000
      }

      env {
        name  = "PROPERTY_DATA_BUCKET"
        value = google_storage_bucket.property_snapshots.name
      }

      env {
        name  = "BIGQUERY_DATASET"
        value = google_bigquery_dataset.property.dataset_id
      }

      env {
        name = "MLFLOW_TRACKING_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mlflow_tracking_uri.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        startup_cpu_boost = true
      }
    }
  }

  depends_on = [google_project_iam_member.run_roles]
}

resource "google_cloud_run_v2_job" "etl" {
  project  = var.project_id
  name     = "${local.name_prefix}-etl"
  location = var.region
  labels   = local.labels

  template {
    template {
      service_account = google_service_account.run.email
      timeout         = "3600s"
      max_retries     = 1

      containers {
        image   = var.job_image
        command = ["python", "scripts/property_etl.py"]

        env {
          name  = "PROPERTY_DATA_BUCKET"
          value = google_storage_bucket.property_snapshots.name
        }

        env {
          name  = "BIGQUERY_DATASET"
          value = google_bigquery_dataset.property.dataset_id
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }
      }
    }
  }

  depends_on = [google_project_iam_member.run_roles]
}

resource "google_cloud_scheduler_job" "etl_daily" {
  project     = var.project_id
  name        = "${local.name_prefix}-etl-daily"
  description = "Run the Property Intelligence ETL job once per day"
  region      = var.region
  schedule    = "0 3 * * *"
  time_zone   = "Asia/Bangkok"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.etl.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_iam_member.scheduler_run_invoker]
}

resource "google_sql_database_instance" "postgis" {
  count            = var.enable_cloud_sql ? 1 : 0
  project          = var.project_id
  name             = "${local.name_prefix}-postgis"
  region           = var.region
  database_version = "POSTGRES_16"

  settings {
    tier              = var.cloud_sql_tier
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled = false
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = true

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "property" {
  count    = var.enable_cloud_sql ? 1 : 0
  project  = var.project_id
  name     = "property_intelligence"
  instance = google_sql_database_instance.postgis[0].name
}
