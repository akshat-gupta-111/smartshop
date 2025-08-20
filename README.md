# SmartShop - AI-Powered E-commerce Platform

A modern e-commerce platform with AI-powered product recommendations, built with Flask and integrated with Google's Gemini AI.

## Features

- 🤖 AI-powered product recommendations
- 🛒 Shopping cart functionality
- 👥 User and retailer roles
- 💬 Interactive chat assistant
- 📱 Responsive design
- 🔗 Image URL support for products
- 👤 Guest user access

## Quick Start (Local Development)

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your API keys
4. Run: `python app.py`

## Deployment on Vercel

### Prerequisites
- Vercel account (https://vercel.com)
- Google Gemini API key (https://makersuite.google.com/app/apikey)

### Steps

1. **Prepare your repository:**
   ```bash
   git add .
   git commit -m "Prepare for Vercel deployment"
   git push origin main
   ```

2. **Deploy to Vercel:**
   - Go to https://vercel.com/dashboard
   - Click "New Project"
   - Import your GitHub repository
   - Vercel will auto-detect it's a Python project

3. **Configure Environment Variables:**
   In your Vercel project dashboard, go to Settings → Environment Variables and add:
   
   ```
   GEMINI_API_KEY=your_actual_gemini_api_key
   SECRET_KEY=generate_a_secure_random_string
   UPI_ID=your_upi_id@bank
   FLASK_ENV=production
   ```

4. **Redeploy:**
   After adding environment variables, trigger a new deployment.

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini AI API key | Yes |
| `SECRET_KEY` | Flask session secret key | Yes |
| `UPI_ID` | UPI ID for payment QR codes | Optional |
| `FLASK_ENV` | Flask environment (production) | Optional |

## Security Features

- ✅ API keys stored as environment variables
- ✅ Secret keys externalized
- ✅ Sensitive data not committed to repository
- ✅ Production-ready configuration

## Demo Accounts

- **Guest User:** username: `guest_user`, password: `guest123`
- **Guest Retailer:** username: `guest_retailer`, password: `guest123`

## Tech Stack

- **Backend:** Flask (Python)
- **AI:** Google Gemini API
- **Frontend:** HTML, CSS (Tailwind), JavaScript
- **Deployment:** Vercel
- **Database:** File-based JSON storage

## License

MIT License
