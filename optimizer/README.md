# Presidio Optimizer

AI-driven PII detection configuration optimizer built around [Microsoft Presidio](https://microsoft.github.io/presidio/). Upload documents, analyze PII entities, provide feedback on false positives/negatives, and let Claude AI automatically optimize the detection configuration.

Designed specifically for **Swedish PII detection** with support for personnummer, samordningsnummer, organisationsnummer, and Swedish phone numbers.

## Features

- **Document Upload** — Supports DOCX, XLSX, PDF, and TXT files
- **PII Analysis** — Detects entities using Presidio with Swedish and English NER models
- **Interactive Feedback** — Mark false positives by clicking entities, tag false negatives by selecting text
- **AI Optimization** — Claude analyzes feedback patterns and suggests configuration changes (thresholds, recognizers, entity toggles)
- **Version Tracking** — Every optimization creates a new versioned configuration
- **Session Management** — Named persistent sessions for iterative refinement across multiple rounds
- **Report Generation** — Downloadable Markdown reports with session history and optimization reasoning
- **Config Export** — Export optimized configurations as JSON or YAML

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│  Nginx (frontend │────▶│  FastAPI backend  │
│  + reverse proxy)│     │  (Presidio +      │
│  Port 8081       │     │   Claude API)     │
└─────────────────┘     │  Port 8000        │
                         └──────────────────┘
                                  │
                         ┌────────▼────────┐
                         │  File-based DB   │
                         │  (db/sessions/)  │
                         └─────────────────┘
```

- **Frontend**: Vanilla HTML/CSS/JavaScript with a glassmorphism dark theme
- **Backend**: Python 3.11, FastAPI, Microsoft Presidio, spaCy (sv + en models)
- **LLM**: Claude API (Anthropic) for intelligent configuration optimization
- **Storage**: File-based JSON — no external database required

## Swedish PII Entities

| Entity | Description |
|--------|-------------|
| SWEDISH_PERSONNUMMER | Swedish personal identity numbers (with Luhn validation) |
| SWEDISH_SAMORDNINGSNUMMER | Coordination numbers (day 61–91) |
| SWEDISH_ORGANISATIONSNUMMER | Organization numbers |
| SWEDISH_PHONE_NUMBER | Swedish phone patterns (+46, 07X, 0XX) |

Plus all standard Presidio entities: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, CREDIT_CARD, IBAN_CODE, IP_ADDRESS, URL, etc.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An Anthropic API key

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/thomaswennersten/presidio-verktyg.git
   cd presidio-verktyg/optimizer
   ```

2. Create your environment file:
   ```bash
   cp .env.example .env
   # Edit .env and add your Anthropic API key
   ```

3. Start the application:
   ```bash
   docker-compose up -d --build
   ```

4. Access the application:
   - Frontend: `http://localhost:8081`
   - API: via frontend på `/api/`

### Usage

1. **Create a session** — Give it a descriptive name
2. **Upload a document** — Drag & drop or click to upload (DOCX, XLSX, PDF, TXT)
3. **Run analysis** — Presidio scans the document for PII entities
4. **Review results** — Entities are highlighted in the text with color-coded categories
5. **Provide feedback** — Click entities to mark false positives, select text to tag false negatives
6. **Optimize** — Claude analyzes your feedback and generates an improved configuration
7. **Iterate** — Re-analyze with the new config and repeat until satisfied
8. **Export** — Download the optimized configuration as JSON or YAML

## Project Structure

```
optimizer/
├── docker-compose.yml          # Standalone Docker orchestration
├── Dockerfile                  # Python 3.11 + spaCy models
├── nginx.conf                  # Reverse proxy configuration
├── .env.example                # Environment variable template
├── backend/
│   ├── main.py                 # FastAPI application & endpoints
│   ├── presidio_service.py     # Presidio analyzer engine
│   ├── config_manager.py       # Versioned config persistence
│   ├── session_store.py        # File-based session storage
│   ├── document_processor.py   # Multi-format text extraction
│   ├── feedback_processor.py   # Feedback normalization & aggregation
│   ├── llm_optimizer.py        # Claude API integration
│   ├── custom_recognizer_factory.py  # Dynamic recognizer creation
│   ├── swedish_recognizers.py  # Swedish-specific PII recognizers
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── index.html              # Main SPA page
│   ├── css/styles.css          # Dark glassmorphism theme
│   └── js/
│       ├── app.js              # Main application controller
│       ├── api-client.js       # REST API client
│       ├── text-annotator.js   # Interactive text highlighting
│       ├── file-upload.js      # Drag & drop file handling
│       ├── config-panel.js     # Configuration viewer & export
│       ├── iteration-history.js # Version timeline
│       └── session-manager.js  # Session CRUD
└── db/                         # Persistent file-based storage
    └── sessions/               # Per-session data (gitignored)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create a new session |
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{id}` | Get session details |
| DELETE | `/api/sessions/{id}` | Delete a session |
| POST | `/api/sessions/{id}/upload` | Upload a document |
| POST | `/api/sessions/{id}/analyze` | Run PII analysis |
| POST | `/api/sessions/{id}/feedback` | Submit feedback |
| POST | `/api/sessions/{id}/optimize` | Trigger AI optimization |
| GET | `/api/sessions/{id}/config` | Get current configuration |
| GET | `/api/sessions/{id}/config/export` | Export config (JSON/YAML) |
| GET | `/api/sessions/{id}/report` | Download analysis report |

## License

MIT
