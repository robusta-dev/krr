# KRR Enforcer - Kubernetes Resource Recommendation Mutation Webhook

A mutating webhook server that automatically enforces [KRR (Kubernetes Resource Recommender)](https://github.com/robusta-dev/krr) recommendations by patching pod resource requests and limits in real-time.

## Features

- **Automatic Resource Enforcement**: Applies KRR recommendations to pods during pod creation
- **Flexible Enforcement Modes**: Support for enforce/ignore modes per workload
- **REST API**: Query recommendations via HTTP endpoints

## Enforcement Modes

Enforcement can be configured globally or on a per-workload basis.

### Global Enforcement Mode
The global default mode is configured via the `KRR_MUTATION_MODE_DEFAULT` environment variable:
- `enforce` - Apply recommendations to all pods by default
- `ignore` - Skip enforcement for all pods by default

### Per-Workload Mode
You can override the default mode for specific workloads using the annotation:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    metadata:
      annotations:
        admission.robusta.dev/krr-mutation-mode: enforce  # or "ignore"
```

**Mode Priority**: Pod annotation > Global default

## Webhook Failure Mode

The webhook uses `failurePolicy: Ignore` by default, meaning if the webhook fails, pods are created without resource optimization rather than being blocked.


## Installation with Helm

### Prerequisites
- Helm 3.x
- Prometheus Operator (optional, for metrics collection)
- Robusta UI account - used to store KRR scan results

### Certificate

- Each helm install/upgrade, a new certificate is created and deployed for the admission webhook.
- <B>The certificate is set to expire after 1 year.</b>
- In order to avoid certificate expiration, you must upgrade the enforcer helm release, <b>at least once a year</b>.

### Quick Start

1. **Add the helm repository** (if available):
```bash
helm repo add robusta https://robusta-charts.storage.googleapis.com && helm repo update
```

2. **Add cluster configuration**:

If the enforcer is installed in the same namespace as Robusta, it will automatically detect the Robusta account settings.

If your Robusta UI sink token, is pulled from a secret (as described [here](https://docs.robusta.dev/master/setup-robusta/configuration-secrets.html#pulling-values-from-kubernetes-secrets)), you should add the same environement variable to the `Enforcer` pod as well.

If the `Enforcer` is installed on a different namespace, you can provide your Robusta account credentials using env variables:

Add your robusta credentials and cluster name: (`enforcer-values.yaml`)

```yaml
additionalEnvVars:
  - name: CLUSTER_NAME
    value: my-cluster-name  # should be the same as the robusta installation on this cluster
  - name: ROBUSTA_UI_TOKEN
    value: "MY ROBUSTA UI TOKEN"
#  - name: ROBUSTA_UI_TOKEN  # or pulled from a secret
#    valueFrom:
#      secretKeyRef:
#        name: robusta-secrets
#        key: robustaSinkToken
```

2. **Install with default settings**:
```bash
helm install krr-enforcer robusta/krr-enforcer -f enforcer-values.yaml
```

### Helm values

| Parameter | Description                                                         | Default |
|-----------|---------------------------------------------------------------------|---------|
| `logLevel` | Log level (DEBUG, INFO, WARN, ERROR)                                | `INFO` |
| `certificate` | Base64-encoded custom CA certificate - for self signed certificates | `""` |
| `serviceMonitor.enabled` | Enable Prometheus ServiceMonitor                                    | `true` |
| `resources.requests.cpu` | CPU request for the enforcer pod                                    | `100m` |
| `resources.requests.memory` | Memory request for the enforcer pod                                                     | `256Mi` |


## Running Locally

### Prerequisites
- Python 3.9+
- Access to a Kubernetes cluster
- KRR recommendations data from Robusta UI

### Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set environment variables**:
```bash
export ENFORCER_SSL_KEY_FILE="path/to/tls.key"
export ENFORCER_SSL_CERT_FILE="path/to/tls.crt"
export LOG_LEVEL="DEBUG"
export KRR_MUTATION_MODE_DEFAULT="enforce"
```

3. **Generate TLS certificates**:
```bash
# Generate private key
openssl genrsa -out tls.key 2048

# Generate certificate signing request
openssl req -new -key tls.key -out tls.csr \
  -subj "/CN=krr-enforcer.krr-system.svc"

# Generate self-signed certificate
openssl x509 -req -in tls.csr -signkey tls.key -out tls.crt -days 365
```

4. **Run the server**:
```bash
python enforcer_main.py
```

The server will start on `https://localhost:8443` with the following endpoints:

- `POST /mutate` - Webhook endpoint for Kubernetes admission control
- `GET /health` - Health check endpoint
- `GET /metrics` - Prometheus metrics
- `GET /recommendations/{namespace}/{kind}/{name}` - Query recommendations

### Local Development Tips

- Use `LOG_LEVEL=DEBUG` for detailed request/response logging
- Test webhook locally using tools like `curl` or `httpie`
- Monitor metrics at `https://localhost:8443/metrics`
- Query recommendations: `GET https://localhost:8443/recommendations/default/Deployment/my-app`

### Testing the Webhook

```bash
# Test health endpoint
curl -k https://localhost:8443/health

# Test metrics endpoint
curl -k https://localhost:8443/metrics

# Test recommendations endpoint
curl -k https://localhost:8443/recommendations/default/Deployment/my-app
```

## Metrics

The enforcer exposes Prometheus metrics at `/metrics`:

- `krr_pod_admission_mutations_total` - Total pod mutations (with `mutated` label)
- `krr_replicaset_admissions_total` - Total ReplicaSet admissions (with `operation` label)
- `krr_rs_owners_map_size` - Current size of the ReplicaSet owners map
- `krr_admission_duration_seconds` - Duration of admission operations (with `kind` label)

## API Endpoints

### GET /recommendations/{namespace}/{kind}/{name}

Retrieve recommendations for a specific workload:

```bash
curl -k https://krr-enforcer.krr-system.svc.cluster.local/recommendations/default/Deployment/my-app
```

Response:
```json
{
  "namespace": "default",
  "kind": "Deployment",
  "name": "my-app",
  "containers": {
    "web": {
      "cpu": {
        "request": "100m",
        "limit": "200m"
      },
      "memory": {
        "request": "128Mi",
        "limit": "256Mi"
      }
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **Certificate Errors**: Ensure TLS certificates are properly configured and valid
2. **Permission Denied**: Verify the ServiceAccount has proper RBAC permissions
3. **No Recommendations**: Check that KRR has generated recommendations and they're accessible
4. **Webhook Timeout**: Increase `timeoutSeconds` in MutatingWebhookConfiguration

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
helm upgrade krr-enforcer ./helm/krr-enforcer --set logLevel=DEBUG
```

### Logs

Check enforcer logs:
```bash
kubectl logs -n krr-system deployment/krr-enforcer-krr-enforcer -f
```