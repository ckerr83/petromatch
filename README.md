# PetroMatch - Oil & Gas Job Matching Platform

PetroMatch is a full-stack web application that automatically scrapes oil & gas job boards, matches candidates to positions using AI embeddings, and provides CV tailoring services.

## Features

- **User Authentication**: JWT-based login/signup system
- **CV Upload**: Support for .txt, .pdf, .doc, .docx files
- **Job Board Scraping**: Automated scraping using Playwright and BeautifulSoup
- **AI Matching**: OpenAI embeddings with FAISS for job-CV similarity
- **CV Tailoring**: GPT-4 powered CV customization for specific jobs
- **Email Notifications**: Scheduled email alerts for new matches
- **Modern UI**: Next.js frontend with Tailwind CSS

## Tech Stack

### Backend
- **FastAPI**: Python web framework
- **SQLAlchemy**: ORM with PostgreSQL
- **Alembic**: Database migrations
- **Celery**: Task queue with Redis
- **OpenAI**: Embeddings and GPT-4 API
- **FAISS**: Vector similarity search
- **Playwright**: Web scraping for JavaScript-heavy sites
- **BeautifulSoup**: HTML parsing

### Frontend
- **Next.js**: React framework
- **Tailwind CSS**: Styling
- **React Hook Form**: Form handling
- **Axios**: HTTP client
- **React Hot Toast**: Notifications

### Infrastructure
- **PostgreSQL**: Database
- **Redis**: Cache and message broker
- **Docker**: Containerization
- **Docker Compose**: Multi-service orchestration

## Project Structure

```
petromatch/
├── backend/
│   ├── app/
│   │   ├── core/          # Configuration, database, security
│   │   ├── models/        # SQLAlchemy models
│   │   ├── routers/       # API endpoints
│   │   ├── services/      # Business logic
│   │   └── workers/       # Celery tasks
│   ├── alembic/           # Database migrations
│   ├── requirements.txt
│   └── seed_data.py
├── frontend/
│   ├── components/        # React components
│   ├── pages/            # Next.js pages
│   ├── hooks/            # Custom hooks
│   ├── types/            # TypeScript types
│   └── utils/            # Utilities
├── docker/               # Dockerfiles
├── docker-compose.yml
└── README.md
```

## Setup Instructions

### Prerequisites
- Docker and Docker Compose
- OpenAI API key
- (Optional) SendGrid API key for email notifications

### Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   - `OPENAI_API_KEY`: Required for AI matching and CV tailoring
   - `SENDGRID_API_KEY`: Optional for email notifications
   - `SECRET_KEY`: Generate a secure random key

### Running with Docker (Recommended)

1. Build and start all services:
   ```bash
   docker-compose up --build
   ```

2. The application will be available at:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

3. Seed the database with sample job boards:
   ```bash
   docker-compose exec backend python seed_data.py
   ```

### Running Locally (Development)

#### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```bash
   playwright install
   ```

4. Start PostgreSQL and Redis (using Docker):
   ```bash
   docker run -d --name postgres -p 5432:5432 -e POSTGRES_DB=petromatch -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=password postgres:15
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Seed sample data:
   ```bash
   python seed_data.py
   ```

7. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

8. Start Celery worker (in a new terminal):
   ```bash
   celery -A app.workers.celery_app worker --loglevel=info
   ```

9. Start Celery beat (in a new terminal):
   ```bash
   celery -A app.workers.celery_app beat --loglevel=info
   ```

#### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

## API Endpoints

### Authentication
- `POST /auth/signup` - User registration
- `POST /auth/login` - User login (returns JWT token)

### CV Management
- `POST /user/cv` - Upload CV file
- `GET /user/cv` - Get CV metadata
- `GET /user/cv/content` - Get CV text content

### Job Boards
- `GET /jobs/boards` - List available job boards

### Job Scraping
- `POST /jobs/scrape` - Start scraping job boards
- `GET /jobs/status/{task_id}` - Check scraping status
- `GET /jobs/results/{task_id}` - Get scraped job listings

### AI Matching
- `POST /jobs/match` - Start AI matching process
- `GET /jobs/matches/{task_id}` - Get job matches with scores

### CV Tailoring
- `POST /jobs/cv/tailor` - Generate tailored CV for specific job

### Email Notifications
- `POST /notifications/email` - Setup email notification schedule
- `GET /notifications/email` - Get current notification settings
- `DELETE /notifications/email` - Delete notification settings

## Job Board Configuration

Job boards are configured using JSON selectors. Example:

```json
{
  "use_playwright": true,
  "jobs_page_url": "https://www.rigzone.com/jobs",
  "job_container": ".job-listing",
  "title_selector": ".job-title a",
  "company_selector": ".company-name",
  "location_selector": ".job-location",
  "url_selector": ".job-title a",
  "description_selector": ".job-description"
}
```

For sites requiring authentication:
```json
{
  "use_playwright": true,
  "login": {
    "username_selector": "#username",
    "password_selector": "#password",
    "submit_selector": "#login-button",
    "username": "your-username",
    "password": "your-password"
  }
}
```

## Usage Guide

1. **Sign up** for a new account or **login** to existing account
2. **Upload your CV** in the dashboard
3. **Select job boards** you want to scrape
4. **Start a job scan** to scrape current openings
5. **Run AI matching** to find jobs that match your profile
6. **Tailor your CV** for specific positions
7. **Set up email notifications** to get notified of new matches

## Cron Schedule Examples

For email notifications, use standard cron expressions:
- `0 9 * * *` - Daily at 9 AM
- `0 9 * * 1` - Every Monday at 9 AM
- `0 9 * * 1,3,5` - Mon, Wed, Fri at 9 AM
- `0 9,17 * * *` - Daily at 9 AM and 5 PM

## Troubleshooting

### Common Issues

1. **Database connection failed**: Ensure PostgreSQL is running and credentials are correct
2. **Celery tasks not running**: Check Redis connection and ensure Celery worker is started
3. **Scraping failed**: Some job boards may have anti-bot measures; consider using different selectors
4. **AI matching not working**: Verify OpenAI API key is valid and has credits

### Logs

- Backend logs: `docker-compose logs backend`
- Celery worker logs: `docker-compose logs celery-worker`
- Frontend logs: `docker-compose logs frontend`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue in the GitHub repository.