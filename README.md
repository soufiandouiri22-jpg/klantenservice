# klantenservice.ai

AI-telefonisten voor bedrijven - Een B2B SaaS applicatie voor de Nederlandse markt.

## 🎯 Overzicht

klantenservice.ai levert intelligente AI-telefonisten die inkomende telefoongesprekken aannemen, vloeiend Nederlands spreken, afspraken maken in agenda's, en interne notities achterlaten.

### Kernfuncties

- **AI-Telefonisten**: Configureerbare AI-medewerkers die gesprekken voeren
- **Agenda Integratie**: Google Calendar, Microsoft Outlook, CalDAV
- **Website Kennis (RAG)**: AI leert automatisch van uw website
- **Training**: Gedragsregels en voorbeeldantwoorden configureren
- **Call Logging**: Uitgebreide gesprekshistorie met transcripties
- **Interne Notities**: Automatische notificaties bij terugbelverzoeken

## 🏗️ Architectuur

```
klantenservice/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Config, security, database
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   ├── alembic/            # Database migrations
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/           # Pages (App Router)
│   │   ├── components/    # React components
│   │   └── lib/           # Utilities, API, store
│   └── package.json
└── docker-compose.yml
```

## 🚀 Snel starten

### Vereisten

- Docker & Docker Compose
- Node.js 20+ (voor lokale frontend ontwikkeling)
- Python 3.11+ (voor lokale backend ontwikkeling)

### Met Docker (aanbevolen)

```bash
# Clone de repository
git clone https://github.com/your-org/klantenservice.git
cd klantenservice

# Start alle services
docker-compose up -d

# De applicatie is nu beschikbaar op:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/api/docs
```

### Lokale ontwikkeling

#### Backend

```bash
cd backend

# Maak virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# of: venv\Scripts\activate  # Windows

# Installeer dependencies
pip install -r requirements.txt

# Kopieer environment config
cp .env.example .env
# Pas .env aan met uw instellingen

# Start PostgreSQL en Redis (via Docker)
docker-compose up -d db redis chromadb

# Run database migrations
alembic upgrade head

# Start de server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend

# Installeer dependencies
npm install

# Start de development server
npm run dev
```

## 📦 Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Cache**: Redis
- **Vector DB**: ChromaDB
- **Auth**: JWT tokens
- **Background Jobs**: Celery

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **State**: Zustand
- **Data Fetching**: TanStack Query
- **Forms**: React Hook Form + Zod
- **Animation**: Framer Motion

### Integraties
- **Telefonie**: Twilio
- **Calendar**: Google Calendar API, Microsoft Graph API, CalDAV
- **LLM**: PersonaPlex-7B (self-hosted)

## 🔐 Authenticatie & Autorisatie

### Rollen

| Rol | Rechten |
|-----|---------|
| Owner | Volledige toegang, facturatie, bedrijf verwijderen |
| Admin | Volledige toegang, geen facturatie |
| Manager | AI-medewerkers beheren, logs bekijken |
| Viewer | Alleen lezen |

### API Authenticatie

```bash
# Login
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "password"
}

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}

# Gebruik token in requests
Authorization: Bearer <access_token>
```

## 📱 Abonnementen

| Plan | AI-medewerkers | Prijs |
|------|----------------|-------|
| Starter | 1 | €99/maand |
| Business | 5 | €399/maand |
| Enterprise | 7+ | Op aanvraag |

## 🔒 Privacy & Compliance

- **AVG/GDPR Compliant**
- **EU Hosting**
- **Configureerbare dataretentie**
- **Call recording opt-in**
- **Disclosure bij elk gesprek**

## 📄 API Documentatie

Na het starten van de backend is de API documentatie beschikbaar op:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## 🧪 Testen

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🚢 Deployment

### Production Checklist

- [ ] Set `DEBUG=false`
- [ ] Configureer sterke `SECRET_KEY` en `JWT_SECRET_KEY`
- [ ] Configureer Twilio credentials
- [ ] Configureer OAuth clients (Google, Microsoft)
- [ ] Setup SSL/TLS certificaten
- [ ] Configureer Sentry voor error tracking
- [ ] Setup database backups
- [ ] Configureer rate limiting

## 📞 Support

- Email: support@klantenservice.ai
- Documentatie: https://docs.klantenservice.ai

## 📜 Licentie

Proprietary - © 2024 klantenservice.ai
