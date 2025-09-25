# Furama StayToken - Setup Guide

## Quick Start

### 1. Environment Setup

```bash
# Copy environment template
cp env.example .env

# Edit .env with your configuration
# Update database credentials, secret key, etc.
```

### 2. Database Setup

```bash
# Create database
createdb furama_staytoken

# Run migrations
python manage.py migrate
```

### 3. Settings Configuration

```bash
# Copy settings template
cp furama_staytoken/settings_template.py furama_staytoken/settings.py

# Edit settings.py with your configuration
# Update database settings, allowed hosts, etc.
```

### 4. Run Development Server

```bash
python manage.py runserver
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `your-secret-key-here` |
| `DEBUG` | Debug mode | `True` |
| `DB_NAME` | Database name | `furama_staytoken` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `your-password` |
| `ST_CHAIN_ID` | Blockchain chain ID | `1` (Ethereum mainnet) |
| `DISABLE_CSRF` | Disable CSRF for dev | `False` |

## Important Files

- `.env` - Environment variables (DO NOT COMMIT)
- `furama_staytoken/settings.py` - Django settings (DO NOT COMMIT)
- `env.example` - Environment template (COMMIT)
- `furama_staytoken/settings_template.py` - Settings template (COMMIT)

## Security Notes

- Never commit `.env` or `settings.py` files
- Use strong secret keys in production
- Set `DEBUG=False` in production
- Configure proper `ALLOWED_HOSTS` for production
