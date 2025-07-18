# Shopify-Web-Scraper

A **FastAPI-powered backend** that scrapes product, policy, and metadata from any public Shopify store URL. 

---

##  Features

-  FastAPI-based REST API
-  Extracts structured data from unstructured HTML
-  Shopify-specific selectors
-  JSON API response format
-  Auto-generated Swagger documentation

---

##  Tech Stack

| Component     | Tool                     |
|---------------|--------------------------|
| Language      | Python 3.10              |
| Framework     | FastAPI                  |
| Scraping      | BeautifulSoup + Requests |
| Packaging     | `venv`, `pip`            |
| Docs          | Swagger UI               |

---

##  Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/shopify-scraper.git
cd shopify-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate       # For Linux/Mac
# OR
venv\Scripts\activate          # For Windows

# Install required packages
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload
