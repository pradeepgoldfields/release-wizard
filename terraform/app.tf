locals {
  app_name = "conduit"

  common_labels = {
    "app.kubernetes.io/name"       = local.app_name
    "app.kubernetes.io/instance"   = "${local.app_name}-${var.namespace}"
    "app.kubernetes.io/version"    = var.image_tag
    "app.kubernetes.io/managed-by" = "terraform"
    "app.kubernetes.io/part-of"    = "conduit"
  }

  selector_labels = {
    "app.kubernetes.io/name"     = local.app_name
    "app.kubernetes.io/instance" = "${local.app_name}-${var.namespace}"
  }
}

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------
resource "kubernetes_deployment_v1" "conduit" {
  metadata {
    name      = local.app_name
    namespace = kubernetes_namespace_v1.conduit.metadata[0].name
    labels    = local.common_labels
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = local.selector_labels
    }

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    template {
      metadata {
        labels = local.common_labels
        annotations = {
          # Force pod restart when ConfigMap or Secret changes
          "checksum/config" = sha256(jsonencode(kubernetes_config_map_v1.conduit.data))
          "checksum/secret" = sha256(jsonencode(kubernetes_secret_v1.conduit.data))
        }
      }

      spec {
        security_context {
          run_as_non_root = true
          run_as_user     = 1001
          fs_group        = 1001
        }

        automount_service_account_token = false

        container {
          name  = local.app_name
          image = "${var.image_repo}:${var.image_tag}"

          image_pull_policy = var.image_tag == "latest" ? "Always" : "IfNotPresent"

          port {
            name           = "http"
            container_port = var.port
            protocol       = "TCP"
          }

          # Non-sensitive config from ConfigMap
          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.conduit.metadata[0].name
            }
          }

          # Sensitive config from Secret
          env {
            name = "DATABASE_URL"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.conduit.metadata[0].name
                key  = "DATABASE_URL"
              }
            }
          }
          env {
            name = "SECRET_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.conduit.metadata[0].name
                key  = "SECRET_KEY"
              }
            }
          }
          env {
            name = "JWT_SECRET_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.conduit.metadata[0].name
                key  = "JWT_SECRET_KEY"
              }
            }
          }

          resources {
            requests = {
              cpu    = var.cpu_request
              memory = var.memory_request
            }
            limits = {
              cpu    = var.cpu_limit
              memory = var.memory_limit
            }
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = var.port
            }
            initial_delay_seconds = 10
            period_seconds        = 15
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/readyz"
              port = var.port
            }
            initial_delay_seconds = 5
            period_seconds        = 10
            failure_threshold     = 3
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities {
              drop = ["ALL"]
            }
          }

          # /tmp is needed by gunicorn and Python internals at runtime
          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "tmp"
          empty_dir {}
        }
      }
    }
  }

  lifecycle {
    # Allow external actors (Jenkins rollout) to change replica count
    ignore_changes = [spec[0].replicas]
  }
}

# ---------------------------------------------------------------------------
# Service — ClusterIP
# ---------------------------------------------------------------------------
resource "kubernetes_service_v1" "conduit" {
  metadata {
    name      = local.app_name
    namespace = kubernetes_namespace_v1.conduit.metadata[0].name
    labels    = local.common_labels
  }

  spec {
    type     = "ClusterIP"
    selector = local.selector_labels

    port {
      name        = "http"
      port        = 80
      target_port = var.port
      protocol    = "TCP"
    }
  }
}

# ---------------------------------------------------------------------------
# HorizontalPodAutoscaler
# ---------------------------------------------------------------------------
resource "kubernetes_horizontal_pod_autoscaler_v2" "conduit" {
  metadata {
    name      = local.app_name
    namespace = kubernetes_namespace_v1.conduit.metadata[0].name
    labels    = local.common_labels
  }

  spec {
    min_replicas = var.hpa_min_replicas
    max_replicas = var.hpa_max_replicas

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment_v1.conduit.metadata[0].name
    }

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = var.hpa_cpu_target_pct
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }
  }
}
