# AI Hedge Fund Simulation

A full-stack AI-powered trading simulation application.

## 🚀 Features
- **AI Strategist (Llama 3.3)**: Scans the market daily for opportunities.
- **AI Trader**: Executes paper trades based on Technical Logic.
- **Live Dashboard**: React-based UI for real-time portfolio tracking.
- **Automation**: GitHub Actions for daily scheduled trading.

## 🛠️ Tech Stack
- **Frontend**: React, Vite, TailwindCSS, Recharts
- **Backend**: Python, Flask, PyMongo, yfinance, Groq API
- **Database**: MongoDB Atlas

## 📦 Installation

1.  Clone the repo
2.  Install dependencies: `pip install -r requirements.txt`
3.  Set up `.env` with `MONGO_URI` and `GROQ_API_KEY`
4.  Run API: `python backend/api.py`
5.  Run Dashboard: `npm run dev`
