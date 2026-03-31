variable "namespace" {
  description = "Kubernetes namespace to deploy into."
  type        = string
  default     = "conduit"
}

variable "image_repo" {
  description = "Container image repository (e.g. registry.example.com/conduit)."
  type        = string
}

variable "image_tag" {
  description = "Container image tag to deploy."
  type        = string
  default     = "latest"
}

variable "replicas" {
  description = "Initial replica count for the Deployment."
  type        = number
  default     = 2
}

variable "hpa_min_replicas" {
  description = "Minimum replicas managed by the HorizontalPodAutoscaler."
  type        = number
  default     = 2
}

variable "hpa_max_replicas" {
  description = "Maximum replicas managed by the HorizontalPodAutoscaler."
  type        = number
  default     = 10
}

variable "hpa_cpu_target_pct" {
  description = "Target average CPU utilisation (%) for the HPA."
  type        = number
  default     = 70
}

# ---- resource requests / limits ----------------------------------------
variable "cpu_request" {
  description = "CPU resource request."
  type        = string
  default     = "100m"
}

variable "cpu_limit" {
  description = "CPU resource limit."
  type        = string
  default     = "500m"
}

variable "memory_request" {
  description = "Memory resource request."
  type        = string
  default     = "128Mi"
}

variable "memory_limit" {
  description = "Memory resource limit."
  type        = string
  default     = "512Mi"
}

# ---- application config -------------------------------------------------
variable "port" {
  description = "Port the application listens on inside the container."
  type        = number
  default     = 8080
}

variable "log_level" {
  description = "Application log level (DEBUG | INFO | WARNING | ERROR)."
  type        = string
  default     = "INFO"
}

variable "flask_env" {
  description = "Flask environment (production | development)."
  type        = string
  default     = "production"
}

# ---- secrets (supplied via -var or a .tfvars file, never committed) -----
variable "database_url" {
  description = "SQLAlchemy DATABASE_URL (e.g. postgresql+psycopg2://user:pass@host/db)."
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Flask SECRET_KEY — used for session signing. Must be random and unique per env."
  type        = string
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "JWT_SECRET_KEY used to sign tokens."
  type        = string
  sensitive   = true
}

# ---- ingress ------------------------------------------------------------
variable "ingress_host" {
  description = "Hostname for the Ingress rule (e.g. conduit.example.com)."
  type        = string
  default     = "conduit.example.com"
}

variable "ingress_class_name" {
  description = "Ingress class name (e.g. nginx, traefik)."
  type        = string
  default     = "nginx"
}

variable "ingress_tls_secret" {
  description = "Name of the TLS Secret for the Ingress. Leave empty to disable TLS."
  type        = string
  default     = "conduit-tls"
}

# ---- kubeconfig (for provider auth) ------------------------------------
variable "kubeconfig_path" {
  description = "Path to a kubeconfig file. Defaults to ~/.kube/config."
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "kubeconfig context to use. Defaults to the current-context."
  type        = string
  default     = ""
}
