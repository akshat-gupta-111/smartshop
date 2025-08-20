#!/bin/bash

# Deployment preparation script for SmartShop

echo "🚀 Preparing SmartShop for deployment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual API keys before deploying"
fi

# Check if git repo is initialized
if [ ! -d .git ]; then
    echo "📦 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit"
fi

# Show deployment instructions
echo ""
echo "✅ Ready for deployment!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your actual API keys"
echo "2. Push to GitHub: git push origin main"
echo "3. Deploy on Vercel:"
echo "   - Go to https://vercel.com/dashboard"
echo "   - Import your GitHub repo"
echo "   - Add environment variables from .env"
echo "   - Deploy!"
echo ""
echo "Environment variables needed in Vercel:"
cat .env.example | grep -E "^[A-Z_]+" | sed 's/=.*//' | sed 's/^/   - /'
echo ""
