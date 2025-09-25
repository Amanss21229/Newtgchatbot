# Telegram Anonymous Chatbot

## Overview
An anonymous chatting Telegram bot that connects users for private conversations. The bot features user profile management, VIP system with Telegram Stars payments, admin controls, and comprehensive logging. Users can set up profiles with gender, country, and age preferences, then get matched with other users for anonymous conversations.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework
- **Python Telegram Bot Library**: Uses python-telegram-bot v21.5 for handling Telegram API interactions
- **Asynchronous Architecture**: Built with asyncio for concurrent message handling and user interactions
- **Error Handling**: Comprehensive error handling with user notifications and logging

### Database Layer
- **Multi-Database Support**: Flexible database connection with fallback mechanism
- **Primary**: PostgreSQL with psycopg2 for production environments
- **Fallback**: SQLite for development or when PostgreSQL is unavailable
- **Connection Strategy**: Attempts DATABASE_URL first, then Replit PostgreSQL defaults, finally SQLite
- **Auto-commit**: Enabled for immediate transaction persistence

### Application Structure
- **Modular Design**: Separated concerns with dedicated modules for bot logic, database operations, and main entry point
- **Handler-Based Architecture**: Uses command handlers, message handlers, and callback query handlers for different user interactions
- **State Management**: Database-driven user state tracking for chat sessions and profile management

### Deployment Architecture
- **Dual Service Setup**: Flask web server alongside Telegram bot for platform compatibility
- **Uptime Monitoring**: Flask endpoint provides health check for deployment platforms
- **Threading**: Separate threads for web server and bot operations
- **Environment Configuration**: dotenv for local development with environment variable fallbacks

### User Management System
- **Profile System**: Gender, country, age, and VIP status tracking
- **Anonymous Matching**: Algorithm for pairing users based on preferences
- **Session Management**: Chat state tracking with start/end capabilities
- **Terms & Conditions**: Mandatory agreement system before bot usage

### Administrative Features
- **Multi-Admin Support**: Hierarchical admin system with role management
- **Broadcasting**: Mass message distribution to all users
- **User Moderation**: Blocking/unblocking capabilities with database persistence
- **Statistics**: User metrics and bot usage analytics
- **Force Join**: Mandatory group membership enforcement

### Payment Integration
- **Telegram Stars**: Native Telegram payment system for VIP subscriptions
- **Referral System**: User referral tracking with rewards
- **VIP Features**: Premium user tier with enhanced functionality

## External Dependencies

### Core Dependencies
- **python-telegram-bot**: Telegram Bot API wrapper for Python
- **psycopg2-binary**: PostgreSQL database adapter
- **python-dotenv**: Environment variable management
- **flask**: Web framework for uptime monitoring

### Database Systems
- **PostgreSQL**: Primary database for production (via DATABASE_URL or Replit defaults)
- **SQLite**: Fallback database for development environments

### Platform Services
- **Telegram Bot API**: Core bot functionality and message handling
- **Telegram Stars**: Payment processing for VIP subscriptions
- **Replit PostgreSQL**: Default database service on Replit platform

### Environment Variables
- **BOT_TOKEN**: Telegram bot authentication token (REQUIRED - must be set by user)
- **DATABASE_URL**: PostgreSQL connection string (configured by Replit)
- **PG* Variables**: PostgreSQL connection parameters (configured by Replit: PGHOST, PGDATABASE, PGUSER, PGPASSWORD, PGPORT)
- **PORT**: Flask web server port for deployment platforms (defaults to 5000)

## Setup Status
- ✅ Dependencies installed (python-telegram-bot, flask, psycopg2-binary, etc.)
- ✅ PostgreSQL database configured with Replit's built-in service
- ⚠️ BOT_TOKEN required: User must add their Telegram bot token to Secrets
- ✅ Flask server configured for port 5000 with proper host binding (0.0.0.0)
- ✅ Multi-database fallback system (PostgreSQL → SQLite)
- ✅ Deployment configuration set up (VM deployment target)
- ✅ Database connection tested and working
- ✅ Ready for production deployment once BOT_TOKEN is provided

## Next Steps
To start using the bot:
1. Create a Telegram bot via @BotFather on Telegram
2. Add the BOT_TOKEN to your Replit Secrets
3. The bot will automatically start and connect to the database
4. Use the health check endpoint at your Replit URL to verify the Flask server is running

## Features Ready
- Anonymous user matching system
- VIP subscription with Telegram Stars
- Admin controls and user management  
- Profile system with preferences
- Force join group functionality
- Database-driven chat sessions
- Referral system