# ---------------------------------------------------------------------------
# Ingress
# ---------------------------------------------------------------------------
resource "kubernetes_ingress_v1" "conduit" {
  metadata {
    name      = local.app_name
    namespace = kubernetes_namespace_v1.conduit.metadata[0].name
    labels    = local.common_labels
    annotations = {
      "kubernetes.io/ingress.class"                = var.ingress_class_name
      "nginx.ingress.kubernetes.io/proxy-body-size" = "10m"
    }
  }

  spec {
    ingress_class_name = var.ingress_class_name

    dynamic "tls" {
      for_each = var.ingress_tls_secret != "" ? [1] : []
      content {
        hosts       = [var.ingress_host]
        secret_name = var.ingress_tls_secret
      }
    }

    rule {
      host = var.ingress_host
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.conduit.metadata[0].name
              port {
                name = "http"
              }
            }
          }
        }
      }
    }
  }
}
