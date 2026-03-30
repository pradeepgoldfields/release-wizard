# ---------------------------------------------------------------------------
# ConfigMap — non-sensitive runtime configuration
# ---------------------------------------------------------------------------
resource "kubernetes_config_map_v1" "release_wizard" {
  metadata {
    name      = "release-wizard-config"
    namespace = kubernetes_namespace_v1.release_wizard.metadata[0].name
    labels    = local.common_labels
  }

  data = {
    PORT      = tostring(var.port)
    HOST      = "0.0.0.0"
    LOG_LEVEL = var.log_level
    FLASK_ENV = var.flask_env
  }
}

# ---------------------------------------------------------------------------
# Secret — sensitive runtime configuration
# ---------------------------------------------------------------------------
resource "kubernetes_secret_v1" "release_wizard" {
  metadata {
    name      = "release-wizard-secret"
    namespace = kubernetes_namespace_v1.release_wizard.metadata[0].name
    labels    = local.common_labels
  }

  type = "Opaque"

  data = {
    DATABASE_URL   = var.database_url
    SECRET_KEY     = var.secret_key
    JWT_SECRET_KEY = var.jwt_secret_key
  }
}
