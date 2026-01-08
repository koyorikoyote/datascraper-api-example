Cloned Example of automated web data scraper and ERP system (Backend)


FastAPI backend providing unified activity management, company/contact tracking, authentication, and third-party integrations (Google, HubSpot)

**Key Features:**

- **Unified Activity System** - Centralized tracking of memos, calls, emails, and tasks across all company interactions
- **Docker Containerization** - Full Docker Compose setup with containers `sales_assistant_api` and `sales_assistant_mysql` for development and production
- **Authentication & Authorization** - JWT-based auth with OAuth2PasswordRequestForm, refresh tokens stored in HTTP-only cookies, role-based access control
- **Third-party Integrations** - Google APIs (OAuth, Ads, Search), OpenAI integration, and Selenium Service web scraping capabilities
- **Database Management** - MySQL 8.0 with SQLAlchemy ORM, Alembic migrations, automated seeding via `scripts/seed_db.py`
- **API Routing** - FastAPI routers with `/api` prefix configuration, comprehensive error handling and CORS setup
- **Multi-language Support** - Full English/Japanese localization with react-i18next
- **Real-time Updates** - Live activity feeds and notifications with automatic token refresh

**Architecture:**

```
React 19 Frontend (web) ↔ FastAPI Backend (api) ↔ MySQL Database (Docker)
```

**Development Environment:**

- **Windows Development** - Optimized for Windows with PowerShell scripts, Docker Desktop integration
- **Cross-Platform Compatibility** - Original Linux development adapted for Windows development workflow
- **Authentication Issues** - Common problems include Alembic migration sync, double `/api` prefix, MySQL permissions

**Target Users:** Sales representatives and managers handling company relationships and activities