output "namespace" {
  description = "Kubernetes namespace the app is deployed into."
  value       = kubernetes_namespace_v1.release_wizard.metadata[0].name
}

output "deployment_name" {
  description = "Name of the Kubernetes Deployment."
  value       = kubernetes_deployment_v1.release_wizard.metadata[0].name
}

output "service_name" {
  description = "Name of the Kubernetes Service."
  value       = kubernetes_service_v1.release_wizard.metadata[0].name
}

output "service_cluster_ip" {
  description = "ClusterIP assigned to the Service."
  value       = kubernetes_service_v1.release_wizard.spec[0].cluster_ip
}

output "ingress_host" {
  description = "Hostname configured on the Ingress."
  value       = var.ingress_host
}

output "app_url" {
  description = "URL to access the application (requires DNS or /etc/hosts entry)."
  value       = var.ingress_tls_secret != "" ? "https://${var.ingress_host}" : "http://${var.ingress_host}"
}

output "image" {
  description = "Full image reference that was deployed."
  value       = "${var.image_repo}:${var.image_tag}"
}
