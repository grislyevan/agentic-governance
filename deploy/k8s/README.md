# Kubernetes Deployment

Apply manifests in this order:

1. `namespace.yml`
2. `secret.yml` (edit placeholders first)
3. `configmap.yml`
4. `postgres-statefulset.yml`
5. `deployment.yml` (update image to your registry)
6. `service.yml`
7. `ingress.yml` (update host, requires cert-manager for TLS)

Replace placeholders in `secret.yml` before applying. The ingress uses cert-manager; install it if needed.
