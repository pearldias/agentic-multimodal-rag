# Kubernetes Deployment — Stages 1, 2, 3 & 4

This directory contains the Kubernetes manifests for deploying the **Agentic Multimodal RAG** application.
- **Stage 1**: Workload containers, internal DNS routing, and decoupled health probes.
- **Stage 2**: Externalized configuration via ConfigMap and sensitive credential management via Secret.
- **Stage 3**: Persistent stateful storage via PersistentVolume and PersistentVolumeClaim mounted at `/app/data`.
- **Stage 4**: Ingress routing specification (`ingress.yaml`) directing root HTTP traffic to the frontend service.

---

## Architecture & Data Flow

```text
                        ┌────────────────────────────────────────────────────────────────────────┐
                        │                         Namespace: agentic-rag                         │
                        │                                                                        │
   User / Browser       │   ┌────────────────────┐     ┌─────────────────────┐                   │
         │              │   │ ConfigMap          │     │ Secret              │                   │
         ▼              │   │ (backend-config)   │     │ (backend-secrets)   │                   │
   [Port 80/443]        │   └─────────┬──────────┘     └──────────┬──────────┘                   │
┌──────────────────┐    │             │ envFrom                   │ envFrom                      │
│ Ingress (Nginx)  │    │             └──────────────┬────────────┘                              │
│ (ingress.yaml)   │    │                            ▼                                           │
└────────┬─────────┘    │   ┌────────────────────┐   ┌────────────────────────┐                  │
         │ path: /      │   │  frontend Service  │   │      backend Pod       │                  │
         └─────────────>│   │ (NodePort: 30080)  │   │   (FastAPI: port 8000) │                  │
                        │   └─────────┬──────────┘   └───────▲────────┬───────┘                  │
                        │             │                      │        │                          │
                        │             ▼                      │        │ /app/data volumeMount    │
                        │   ┌────────────────────┐   ┌───────┴────┐   ▼                          │
                        │   │   frontend Pod     │   │  backend   │ ┌──────────────────────────┐ │
                        │   │ (Nginx: port 80)   │──>│  Service   │ │ PersistentVolumeClaim    │ │
                        │   └────────────────────┘   │(ClusterIP) │ │ (backend-data-pvc)       │ │
                        │             proxy_pass     └────────────┘ └─────────────┬────────────┘ │
                        │        http://backend:8000                              ▼              │
                        │                                           ┌──────────────────────────┐ │
                        │                                           │ PersistentVolume (Host)  │ │
                        │                                           │ (backend-data-pv: 1Gi)   │ │
                        │                                           └──────────────────────────┘ │
                        └────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions:
1. **Ingress Routing**: `k8s/ingress.yaml` routes root `/` to the existing `frontend` Service on port 80.
   - Frontend Nginx maintains internal proxying for `/api/` (to `http://backend:8000`) and `/health` (to `http://backend:8000/health`).
   - The `backend` Service remains internal `ClusterIP` on port 8000 and is **never** exposed directly to external traffic.
   - The existing `NodePort` on port `30080` remains active as a direct access alternative.
2. **Persistent State Coverage**: Mounts `/app/data` to a dedicated `PersistentVolumeClaim` (`backend-data-pvc`). This preserves all application state across pod restarts:
   - **SQLite Database**: `conversations.db` (conversation history & memory)
   - **ChromaDB**: `chroma/` (vector embeddings and indexed collections)
   - **Notion MCP Tokens**: `data/.notion_auth.json` (OAuth PKCE credentials)
   - **Document Store**: `raw/`, `processed/`, and `metadata/` records
3. **Cluster-Appropriate Storage**: In Docker Desktop Kubernetes, uses `storageClassName: standard` backed by `rancher.io/local-path` with `hostPath` fallback (`k8s/persistent-volume.yaml`).
4. **Separation of Concerns**: Non-sensitive settings reside in `backend-config` ConfigMap. Sensitive credentials (`GOOGLE_API_KEY`, `COHERE_API_KEY`) reside in `backend-secrets` Secret.
5. **Declarative Injection**: The backend deployment injects all values using `envFrom` (`configMapRef` and `secretRef`). Zero hardcoded secrets exist in the deployment specification.
6. **No Plaintext Secrets in Git**: `k8s/secret.yaml` is provided as a placeholder template only (`your-*-key-here`). Actual secrets are created locally in the cluster using `kubectl` from `.env` or `--from-literal`.
7. **Internal DNS Routing**: Frontend Nginx reverse proxies `/api/` and `/health` to `http://backend:8000`. By naming the ClusterIP service `backend`, CoreDNS resolves requests seamlessly across the `agentic-rag` namespace.
8. **Decoupled Probes**: Frontend liveness probe checks `path: /` on port 80 to verify Nginx process health, while readiness probe checks `path: /health` on port 80 (proxied to `backend:8000/health`) to ensure traffic only routes when downstream services are ready.
9. **Reused Docker Images**: Reuses `agentic-rag-backend:latest` and `agentic-rag-frontend:latest` with `imagePullPolicy: IfNotPresent`.

---

## Manifest Files Summary

| File | Resource Kind | Description |
| :--- | :--- | :--- |
| `namespace.yaml` | `Namespace` | Creates the isolated `agentic-rag` namespace for all project workloads. |
| `configmap.yaml` | `ConfigMap` | Contains non-sensitive application settings (`backend-config`) injected into the backend. |
| `secret.yaml` | `Secret` | Template definition for `backend-secrets` with placeholders (never commit real credentials). |
| `persistent-volume.yaml` | `PersistentVolume` | 1Gi `hostPath` persistent volume (`backend-data-pv`) with `DirectoryOrCreate` for local data. |
| `persistent-volume-claim.yaml` | `PersistentVolumeClaim` | 1Gi claim (`backend-data-pvc`) bound to the persistent storage for `/app/data`. |
| `backend-service.yaml` | `Service` | Internal `ClusterIP` service exposing port 8000, routing traffic to backend pods labeled `app: backend`. |
| `backend-deployment.yaml` | `Deployment` | Deploys 1 replica of `agentic-rag-backend:latest` with `envFrom` config/secret, persistent volume mount at `/app/data`, and health probes on `/health`. |
| `frontend-service.yaml` | `Service` | `NodePort` service exposing port 80 externally on node port `30080`, routing traffic to frontend pods labeled `app: frontend`. |
| `frontend-deployment.yaml` | `Deployment` | Deploys 1 replica of `agentic-rag-frontend:latest` on port 80 with liveness on `/` and readiness on `/health`. |
| `ingress.yaml` | `Ingress` | Ingress resource routing path `/` to `frontend:80` using `ingressClassName: nginx`. |

---

## Prerequisites

Ensure Docker images are built locally before deploying:

```bash
# Build both images using Docker Compose
docker compose build

# OR build individually using Docker
docker build -t agentic-rag-backend:latest -f backend/Dockerfile .
docker build -t agentic-rag-frontend:latest ./frontend
```

---

## Stage 4 Ingress Controller Setup

An Ingress resource requires an active Ingress Controller daemon running in the cluster.

### Check if Ingress Controller is Available
```bash
kubectl get ingressclass
```
If this returns `No resources found`, install the official NGINX Ingress Controller for Kind/Docker Desktop:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```

Wait for the ingress controller pod to reach Running status:
```bash
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

---

## How to Create Secrets & Apply Manifests

### Step 1: Create the Dedicated Namespace
```bash
kubectl apply -f k8s/namespace.yaml
```

### Step 2: Apply ConfigMap & Persistent Storage
```bash
# Apply non-sensitive configuration
kubectl apply -f k8s/configmap.yaml

# Apply persistent storage volume and claim
kubectl apply -f k8s/persistent-volume.yaml
kubectl apply -f k8s/persistent-volume-claim.yaml
```

### Step 3: Create the Secret in Kubernetes
Do **not** commit real credentials to `k8s/secret.yaml`. Choose one of the following methods to populate the Secret in your cluster:

#### Option A: Create directly from your local `.env` file (Recommended)
```bash
kubectl create secret generic backend-secrets \
  --from-env-file=.env \
  -n agentic-rag \
  --dry-run=client -o yaml | kubectl apply -f -
```

#### Option B: Create from explicit literals
```bash
kubectl create secret generic backend-secrets \
  --from-literal=GOOGLE_API_KEY="your-actual-gemini-key" \
  --from-literal=COHERE_API_KEY="your-actual-cohere-key" \
  -n agentic-rag
```

#### Option C: Apply a customized local YAML copy (Uncommitted)
```bash
# Edit your local secret.yaml with real keys, then apply:
kubectl apply -f k8s/secret.yaml
```

### Step 4: Deploy Services and Deployments
```bash
# Deploy backend service and deployment (with volume mounted)
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/backend-deployment.yaml

# Deploy frontend service and deployment
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
```

### Step 5: Apply Ingress
```bash
kubectl apply -f k8s/ingress.yaml
```

---

## How to Check Pods, Deployments, Storage & Ingress

### View All Resources in Namespace
```bash
kubectl get all -n agentic-rag
```

### Check Ingress Status
```bash
kubectl get ingress -n agentic-rag
```

### Check Storage Status
```bash
kubectl get pv,pvc -n agentic-rag
```

### Verify Volume Mount and Writability
```bash
kubectl exec -n agentic-rag deployment/backend -- python -c "
from pathlib import Path
d = Path('/app/data')
print('Items:', [p.name for p in d.iterdir()])
f = d / 'test.txt'
f.write_text('ok')
assert f.read_text() == 'ok'
f.unlink()
print('Volume writable: SUCCESS')
"
```

### Check Pod Status & Deployment Rollout
```bash
kubectl get pods -n agentic-rag -o wide
kubectl rollout status deployment/backend -n agentic-rag
kubectl rollout status deployment/frontend -n agentic-rag
```

---

## How to Verify Health & Connectivity

### 1. Ingress Routing (Port 80)
Once the Ingress controller is installed and `k8s/ingress.yaml` is applied:
```bash
# Access application frontend via Ingress
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/

# Access backend health via Ingress through frontend proxy
curl -s http://localhost/health
```

### 2. Frontend Access via NodePort 30080
Direct alternative access:
* **Docker Desktop / Minikube**: `http://localhost:30080` (or `minikube service frontend -n agentic-rag`)
* **Cluster node IP**: `http://<NODE-IP>:30080`

### 3. Backend Health Inside Cluster
```bash
kubectl exec -n agentic-rag deployment/backend -- python -c "import urllib.request; resp = urllib.request.urlopen('http://backend:8000/health'); print(resp.status, resp.read().decode())"
```

### 4. Kubectl Port-Forwarding (Alternative Access)
```bash
# Port-forward frontend to http://localhost:8080
kubectl port-forward svc/frontend 8080:80 -n agentic-rag

# Port-forward backend to http://localhost:8000 (FastAPI docs at /docs)
kubectl port-forward svc/backend 8000:8000 -n agentic-rag
```

---

## How to Remove the Deployment

### Method 1: Delete via Manifest Directory
```bash
kubectl delete -f k8s/
```

### Method 2: Delete Namespace (Removes All Contained Resources)
```bash
kubectl delete namespace agentic-rag
```
