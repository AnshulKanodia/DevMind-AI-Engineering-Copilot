# DevMind — Production Deployment & Operations Playbook

This playbook covers deployment procedures, environment configurations, and maintenance runbooks for DevMind across Vercel, Docker Compose, Kubernetes, and AWS ECS.

---

## 1. Quickstart with Docker Compose

Run the entire platform locally with MongoDB and Redis:

```bash
# 1. Clone repository and initialize configuration
git clone https://github.com/AnshulKanodia/DevMind-AI-Engineering-Copilot.git
cd DevMind-AI-Engineering-Copilot
cp .env.example .env

# 2. Launch containerized services
docker-compose up -d

# 3. Verify container health
docker-compose ps
curl http://localhost:8000/health
```

---

## 2. Vercel Serverless Frontend Deployment

The Next.js 14 frontend is pre-configured for automated zero-downtime deployment on Vercel:

1. Import the repository in [Vercel Dashboard](https://vercel.com/).
2. Set root directory to `frontend` (or rely on monorepo detection with root `package.json`).
3. Configure Environment Variables in Project Settings:
   - `BACKEND_INTERNAL_URL`: (Optional) Internal cluster endpoint for proxying.
   - `NEXT_PUBLIC_APP_URL`: `https://your-domain.vercel.app`
4. Deploy. The standalone output mode bundles all SSR, static assets, and SSE serverless edge functions automatically.

---

## 3. Production Kubernetes Deployment (Kustomize)

Deploy the multi-tier containerized stack to a Kubernetes cluster (EKS, GKE, AKS, or bare-metal):

```bash
# 1. Create devmind namespace and base configuration
kubectl apply -k deploy/k8s

# 2. Verify pod rollouts
kubectl rollout status deployment/devmind-backend -n devmind
kubectl rollout status deployment/devmind-frontend -n devmind

# 3. Inspect running pods and security contexts
kubectl get pods -n devmind -o wide
```

### Security Verifications
- **Non-Root Check**: `kubectl exec -it <pod-name> -n devmind -- id` must report `uid=10001(appuser) gid=10001(appuser)`.
- **Capability Check**: Containers execute with all Linux capabilities dropped (`drop: ["ALL"]`).

---

## 4. AWS ECS Fargate Deployment

Deploy using the provided ECS Task Definition ([`deploy/ecs/task-definition.json`](../deploy/ecs/task-definition.json)):

```bash
# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://deploy/ecs/task-definition.json

# Update ECS Service
aws ecs update-service \
  --cluster devmind-production-cluster \
  --service devmind-copilot-service \
  --task-definition devmind-copilot-production \
  --force-new-deployment
```

---

## 5. Secret Rotation & Operations Runbook

### Rotating JWT & Fernet Encryption Keys
1. Generate new 32-byte hex string:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update the Kubernetes Secret or AWS Secrets Manager:
   ```bash
   kubectl create secret generic devmind-secrets -n devmind \
     --from-literal=SECRET_KEY="<new-key>" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
3. Trigger a rolling restart:
   ```bash
   kubectl rollout restart deployment/devmind-backend -n devmind
   ```

### Rollback Procedure
If a regression occurs in production:
```bash
kubectl rollout undo deployment/devmind-backend -n devmind
kubectl rollout undo deployment/devmind-frontend -n devmind
```
