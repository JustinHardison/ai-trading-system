# AI Trading System Dashboard

React-based web dashboard for monitoring and controlling the autonomous AI trading system.

## Features

- Real-time monitoring via WebSocket
- Start/stop trading controls
- Performance metrics and charts
- Open positions display
- Settings configuration
- 24/7 cloud deployment on Netlify

## Local Development

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Start development server:
```bash
npm start
```

4. Build for production:
```bash
npm run build
```

## Environment Variables

- `REACT_APP_API_URL` - Backend API URL (default: http://localhost:8000)
- `REACT_APP_WS_URL` - WebSocket URL (default: ws://localhost:8000)

## Deployment to Netlify

### Option 1: Netlify CLI

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
netlify deploy --prod
```

### Option 2: Git Integration

1. Push to GitHub
2. Connect repository in Netlify dashboard
3. Netlify auto-builds on push

### Option 3: Manual Deploy

```bash
npm run build
netlify deploy --prod --dir=build
```

## Production Configuration

Update `.env` with your VPS details:

```bash
REACT_APP_API_URL=http://YOUR_VPS_IP:8000
REACT_APP_WS_URL=ws://YOUR_VPS_IP:8000
```

For HTTPS (recommended):

```bash
REACT_APP_API_URL=https://YOUR_DOMAIN:8000
REACT_APP_WS_URL=wss://YOUR_DOMAIN:8000
```

## Architecture

```
Netlify CDN (React Dashboard)
    ↓ WebSocket + REST API
VPS (FastAPI Backend + autonomous_trader.py)
    ↓ HTTP Requests
MT5 on VPS (Trade Execution)
```

## Components

- **ControlPanel** - Start/stop buttons and status
- **StatusCard** - Metric display cards
- **PositionsList** - Open positions table
- **PerformanceChart** - Profit chart with recharts
- **Settings** - Configuration modal

## API Endpoints

- `GET /api/status` - Current system status
- `GET /api/settings` - Current settings
- `POST /api/settings` - Update settings
- `POST /api/control` - Start/stop trading
- `GET /api/positions` - Open positions
- `GET /api/metrics` - Performance metrics
- `WebSocket /ws` - Real-time updates
