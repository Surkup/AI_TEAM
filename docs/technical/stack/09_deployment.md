# Deployment: Docker Compose → Kubernetes


---

# ⚠️ ЧЕРНОВИК — ТРЕБУЕТ ПРОВЕРКИ ⚠️

**Этот документ НЕ является финальным решением!**

Требуется детальный анализ, критика и проверка перед принятием решений.

---
## Решение

**Эволюция:**
- **MVP**: Docker Compose (локально + простой VPS)
- **Production**: Kubernetes (scalability + resilience)

---

## Docker Compose для MVP

### Почему Docker Compose?

**1. Простота**
```yaml
# docker-compose.yml
version: '3.8'

services:
  # API
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/ai_team
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  # Orchestrator
  orchestrator:
    build: ./orchestrator
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/ai_team
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  # Agents (Writer, Critic, Editor)
  agent-writer:
    build: ./agents
    command: python -m agents.writer
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  agent-critic:
    build: ./agents
    command: python -m agents.critic
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  # PostgreSQL
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=ai_team
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres-data:/var/lib/postgresql/data

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # MinIO
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=admin
      - MINIO_ROOT_PASSWORD=password
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

volumes:
  postgres-data:
  minio-data:
```

**2. Одна команда для запуска**
```bash
docker-compose up -d
```

**3. Идеально для:**
- Локальная разработка
- Первые пользователи
- Simple VPS deployment

---

## Kubernetes для Production

### Когда мигрировать?

**Триггеры:**
- 1000+ одновременных задач
- Нужна auto-scaling
- Multi-region deployment
- High availability требования

---

### Kubernetes структура

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 3  # 3 экземпляра API
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: ai-team/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
# k8s/orchestrator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
spec:
  replicas: 2  # 2 orchestrator для resilience
  # ... similar structure
```

---

## Итоговое решение

**Docker Compose → Kubernetes:**

**MVP (0-6 мес):**
- ✅ Docker Compose
- ✅ Быстрый старт
- ✅ Простота

**Production (6+ мес):**
- ✅ Kubernetes
- ✅ Auto-scaling
- ✅ High availability

---

**Статус:** 📝 ЧЕРНОВИК (требует проверки и утверждения)
**Последнее обновление:** 2025-12-13
