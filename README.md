# Shopify Web Scraper

A FastAPI-powered backend with a simple HTML + JS interface to scrape product, policy, and metadata from any public Shopify store URL.  
It extracts data like products, hero items, policies, contact info, and social links using a single API call.

---

## Features

- Shopify-specific scraping logic
- Extracts:
  - Product lists and hero products
  - Privacy, return, and refund policies
  - Contact information and FAQs
  - Social media links and important URLs
- FastAPI-based REST API
- Swagger UI for API documentation
- Simple frontend interface using HTML + JS
- JSON API response format

---

## Tech Stack

### Backend
- Python 3.10
- FastAPI
- Uvicorn
- BeautifulSoup
- Requests
- Swagger UI (auto-generated API docs)

### Frontend
- HTML + CSS
- JavaScript (using Fetch API)

### Development Tools
- venv (virtual environment)
- pip (Python package manager)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/shopify-scraper.git
cd shopify-scraper

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload
