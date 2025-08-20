import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Use environment variables for sensitive data
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'your-default-key-here')

# Models (you can adjust if Google updates names)
GEMINI_RECOMMEND_MODEL = "gemini-2.0-flash"
GEMINI_FAQ_MODEL = "gemini-2.0-flash"

UPI_ID = os.environ.get('UPI_ID', 'upiid@example@bank')
