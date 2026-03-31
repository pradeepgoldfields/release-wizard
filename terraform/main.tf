terraform {
  required_version = ">= 1.6"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }

  # Uncomment and configure a remote backend for team use:
  # backend "s3" {
  #   bucket = "my-tf-state"
  #   key    = "conduit/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "kubernetes" {
  # Option A — use the active kubeconfig context (local / CI with KUBECONFIG set)
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context

  # Option B — supply cluster credentials directly (comment out Option A above)
  # host                   = var.cluster_host
  # cluster_ca_certificate = base64decode(var.cluster_ca_cert_b64)
  # token                  = var.cluster_token
}

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------
resource "kubernetes_namespace_v1" "conduit" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = "conduit"
    }
  }
}
