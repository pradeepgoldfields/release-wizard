{{/*
Expand the name of the chart.
*/}}
{{- define "conduit.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncate at 63 chars because DNS names may not be longer.
*/}}
{{- define "conduit.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label — name + version.
*/}}
{{- define "conduit.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "conduit.labels" -}}
helm.sh/chart: {{ include "conduit.chart" . }}
{{ include "conduit.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: conduit
{{- end }}

{{/*
Selector labels — used by Deployment.spec.selector and Service.spec.selector.
These must remain stable across upgrades (never change them after first install).
*/}}
{{- define "conduit.selectorLabels" -}}
app.kubernetes.io/name: {{ include "conduit.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "conduit.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "conduit.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Namespace — respects namespaceOverride.
*/}}
{{- define "conduit.namespace" -}}
{{- default .Release.Namespace .Values.namespaceOverride }}
{{- end }}

{{/*
Name of the Secret that holds sensitive env vars.
When existingSecret is set the chart-managed secret is skipped.
*/}}
{{- define "conduit.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "conduit.fullname" . }}
{{- end }}
{{- end }}
