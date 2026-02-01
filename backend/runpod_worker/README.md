# PersonaPlex-7B RunPod Worker

Deze folder bevat de RunPod Serverless worker voor het PersonaPlex-7B spraak-naar-spraak model.

## Vereisten

- Docker geïnstalleerd
- RunPod account met API key
- Docker Hub account (of andere container registry)

## Deployment Stappen

### 1. Build de Docker image

```bash
cd backend/runpod_worker
docker build --platform linux/amd64 -t yourusername/klantenservice-personaplex:latest .
```

### 2. Push naar Docker Hub

```bash
docker login
docker push yourusername/klantenservice-personaplex:latest
```

### 3. Maak een RunPod Endpoint

1. Ga naar [RunPod Console](https://www.runpod.io/console/serverless)
2. Klik op **"New Endpoint"**
3. Selecteer **"Import from Docker Registry"**
4. Vul in:
   - **Container Image**: `docker.io/yourusername/klantenservice-personaplex:latest`
   - **Container Disk**: 20 GB (voor model cache)
5. Klik **"Next"**
6. Configureer:
   - **Endpoint Type**: Queue
   - **GPU Configuration**: Selecteer **24 GB** of hoger (A100/H100 aanbevolen)
   - **Max Workers**: Start met 1, verhoog bij meer traffic
   - **Idle Timeout**: 60 seconden (houdt model geladen)
7. Voeg **Environment Variables** toe:
   - `HUGGINGFACE_TOKEN`: Je Hugging Face token
8. Klik **"Deploy Endpoint"**

### 4. Kopieer de Endpoint ID

Na deployment zie je je endpoint ID (bijv. `abc123xyz`).

### 5. Update de Backend .env

Voeg de endpoint ID toe aan je backend `.env`:

```env
RUNPOD_ENDPOINT_ID=abc123xyz
```

### 6. Herstart de Backend

```bash
./start-backend
```

## Testen

Test de endpoint via de RunPod console:

```json
{
  "input": {
    "action": "init",
    "session_id": "test-123"
  }
}
```

## Kosten

- **RunPod A100 40GB**: ~$0.001-0.002 per seconde
- **Idle Timeout**: Na 60s zonder requests wordt de worker gestopt
- **Cold Start**: ~30-60 seconden (model laden)

## Troubleshooting

### Model laadt niet
- Check of `HUGGINGFACE_TOKEN` correct is ingesteld
- PersonaPlex vereist akkoord met de licentie op Hugging Face

### Timeout errors
- Verhoog de timeout in de backend service
- Check of de GPU voldoende VRAM heeft (24GB+ nodig)

### Geen audio response
- Check de RunPod logs via de console
- Verifieer dat de audio correct base64 encoded is
