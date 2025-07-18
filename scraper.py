import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin

class ShopifyScraper:
    def __init__(self, base_url: str):
        """
        Initializes the scraper with the base URL of the Shopify store.
        """
        # Ensure the base_url has a scheme (http/https)
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url # Default to HTTPS if not specified

        self.base_url = base_url.rstrip('/') # Remove trailing slash for consistent joining
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.homepage_soup = self._fetch_page(self.base_url)

    def _fetch_page(self, url: str):
        """
        Fetches a page and returns its BeautifulSoup object.
        Returns None if fetching fails.
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return BeautifulSoup(response.text, 'html.parser')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _get_text_from_url(self, url: str) -> str:
        """
        Fetches a page and returns its cleaned text content.
        """
        soup = self._fetch_page(url)
        if soup:
            # Remove script, style, and nav elements
            for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header']):
                script_or_style.decompose()
            text = soup.get_text()
            # Break into lines and remove leading/trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a single line
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text
        return "Not found or could not parse."

    def get_product_catalog(self):
        """
        Fetches the entire product catalog using the /products.json endpoint.
        Implements pagination to get all products.
        """
        all_products = []
        page = 1
        while True:
            products_json_url = f"{self.base_url}/products.json?limit=250&page={page}"
            try:
                response = self.session.get(products_json_url, timeout=10)
                response.raise_for_status()
                products_data = response.json()
                products = products_data.get('products', [])
                if not products:
                    break # No more products to fetch
                all_products.extend(products)
                page += 1
            except requests.exceptions.RequestException as e:
                print(f"Error fetching product JSON page {page}: {e}")
                break # Stop if an error occurs
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {products_json_url}: {e}")
                break
        return all_products

    def get_hero_products(self):
        """
        Attempts to identify 'hero' products from the homepage by looking for product links.
        This is heuristic and might not catch all hero products depending on the theme.
        """
        if not self.homepage_soup:
            return []

        hero_products = []
        # Common selectors for product links on homepages
        product_link_selectors = [
            'a[href*="/products/"]',  # Any link containing /products/
            '.product-card__link',    # Common Shopify theme class
            '.grid-view-item__link',  # Another common Shopify theme class
            '.product-item__info a',
            '.grid__item .product-info a'
        ]

        seen_product_handles = set()

        for selector in product_link_selectors:
            for link in self.homepage_soup.select(selector):
                href = link.get('href')
                if href and '/products/' in href:
                    full_url = urljoin(self.base_url, href).split('?')[0] # Remove query params
                    # Extract handle from URL, e.g., /products/product-handle -> product-handle
                    match = re.search(r'/products/([^/?#]+)', full_url)
                    if match:
                        handle = match.group(1)
                        if handle not in seen_product_handles:
                            title_tag = link.find(class_=re.compile(r'product-card__title|product-item__title|product-title|title'))
                            title = title_tag.get_text(strip=True) if title_tag else handle.replace('-', ' ').title()
                            
                            price_tag = link.find(class_=re.compile(r'price-item|product-card__price|product-item__price|price'))
                            price = price_tag.get_text(strip=True) if price_tag else 'N/A'

                            hero_products.append({
                                "title": title,
                                "url": full_url,
                                "handle": handle,
                                "price": price
                            })
                            seen_product_handles.add(handle)
        return hero_products

    def get_page_text(self, paths: list[str]) -> str:
        """
        Fetches and extracts text from a given list of possible page paths.
        Returns the text of the first found page, or "Not found."
        """
        for path in paths:
            url = urljoin(self.base_url, path)
            text = self._get_text_from_url(url)
            if text and text != "Not found or could not parse.":
                return text
        return "Not found."

    def get_faqs(self, paths: list[str]) -> list[dict]:
        """
        Fetches FAQ pages and attempts to parse questions and answers.
        Returns a list of dictionaries with 'question' and 'answer' keys.
        """
        faqs = []
        for path in paths:
            url = urljoin(self.base_url, path)
            soup = self._fetch_page(url)
            if soup:
                # Common patterns for FAQ questions and answers
                # This is highly dependent on the website's HTML structure
                q_and_a_elements = soup.find_all(lambda tag:
                    (tag.name in ['h2', 'h3', 'h4', 'strong', 'b'] and len(tag.get_text(strip=True)) > 5) or
                    (tag.name == 'details' and tag.find('summary')) # For <details><summary>FAQ</summary><p>Answer</p></details>
                )

                for i, elem in enumerate(q_and_a_elements):
                    question = ""
                    answer = ""

                    if elem.name in ['h2', 'h3', 'h4', 'strong', 'b']:
                        question = elem.get_text(strip=True)
                        # Try to find the immediate sibling paragraph(s) or div(s) as answer
                        next_sibling = elem.find_next_sibling()
                        while next_sibling and next_sibling.name in ['p', 'div', 'ul', 'ol', 'span']:
                            answer += next_sibling.get_text(strip=True) + "\n"
                            next_sibling = next_sibling.find_next_sibling()
                        answer = answer.strip()
                    elif elem.name == 'details':
                        summary = elem.find('summary')
                        if summary:
                            question = summary.get_text(strip=True)
                            # Get all content after summary within details tag
                            answer_parts = [str(c) for c in elem.contents if c not in [summary]]
                            answer_soup = BeautifulSoup("".join(answer_parts), 'html.parser')
                            answer = answer_soup.get_text(separator='\n', strip=True)

                    if question and answer:
                        faqs.append({"question": question, "answer": answer})
                    elif question: # If only a question is found, try to get the text of the next element
                        next_text_element = elem.find_next_sibling(re.compile(r'p|div|li'))
                        if next_text_element:
                            answer = next_text_element.get_text(strip=True)
                            if answer:
                                faqs.append({"question": question, "answer": answer})
                
                if faqs: # If FAQs were found on this path, no need to check other paths
                    break
        
        # Deduplicate FAQs based on question
        seen_questions = set()
        unique_faqs = []
        for faq in faqs:
            if faq['question'] not in seen_questions:
                unique_faqs.append(faq)
                seen_questions.add(faq['question'])

        return unique_faqs if unique_faqs else [{"question": "N/A", "answer": "No FAQs found or parsed."}]


    def get_social_media_links(self) -> dict:
        """
        Extracts social media links from the homepage.
        """
        if not self.homepage_soup:
            return {"error": "Homepage not available."}

        social_links = {}
        social_platforms = {
            'facebook': ['facebook.com'],
            'twitter': ['twitter.com', 'x.com'],
            'instagram': ['instagram.com'],
            'pinterest': ['pinterest.com'],
            'youtube': ['youtube.com'],
            'linkedin': ['linkedin.com'],
            'tiktok': ['tiktok.com'],
            'snapchat': ['snapchat.com'],
            'whatsapp': ['wa.me']
        }

        for link_tag in self.homepage_soup.find_all('a', href=True):
            href = link_tag['href'].lower()
            for platform, keywords in social_platforms.items():
                if platform not in social_links: # Only add the first link found for a platform
                    for keyword in keywords:
                        if keyword in href:
                            social_links[platform] = href
                            break
        return social_links if social_links else {"status": "No social media links found."}

    def get_contact_info(self) -> dict:
        """
        Extracts email addresses and phone numbers from the homepage.
        """
        if not self.homepage_soup:
            return {"error": "Homepage not available."}

        text_content = self.homepage_soup.get_text()

        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
        # Simple phone number regex (can be made more complex for international formats)
        # Looks for patterns like (123) 456-7890, 123-456-7890, 1234567890, +91 1234567890
        phone_numbers = re.findall(
            r'(?:(?:\+|0{0,2})91[\s-]?)?(\d{10})|(?:\d{3}[-.\s]?){2}\d{4}', text_content
        )
        
        # Clean up phone numbers to be consistent (e.g., remove spaces/dashes)
        cleaned_phones = []
        for phone in phone_numbers:
            if isinstance(phone, tuple): # Regex returns tuples for groups
                phone = ''.join(filter(None, phone)) # Join non-empty parts of the tuple
            
            # Remove non-digit characters except leading '+'
            cleaned_phone = re.sub(r'[^\d+]', '', phone)
            # Basic validation: must have at least 7 digits (local number) or start with '+'
            if len(cleaned_phone) >= 7 and (cleaned_phone.isdigit() or cleaned_phone.startswith('+')):
                cleaned_phones.append(cleaned_phone)
        
        # Remove duplicates
        emails = list(set(emails))
        cleaned_phones = list(set(cleaned_phones))

        return {
            "emails": emails if emails else ["Not found."],
            "phone_numbers": cleaned_phones if cleaned_phones else ["Not found."]
        }

    def get_important_links(self) -> dict:
        """
        Extracts common important links like Contact Us, Order Tracking, Blog.
        """
        if not self.homepage_soup:
            return {"error": "Homepage not available."}

        important_links = {}
        link_keywords = {
            'contact_us': ['contact', 'support', 'help'],
            'order_tracking': ['track order', 'order status', 'my orders', 'tracking'],
            'blog': ['blog', 'news', 'articles'],
            'shipping_policy': ['shipping policy', 'delivery'],
            'privacy_policy_link': ['privacy policy'],
            'refund_policy_link': ['refund policy', 'return policy', 'returns'],
            'terms_of_service': ['terms of service', 'terms & conditions']
        }

        all_links = self.homepage_soup.find_all('a', href=True)
        for key, keywords in link_keywords.items():
            if key not in important_links:
                for link_tag in all_links:
                    link_text = link_tag.get_text(strip=True).lower()
                    href = link_tag['href'].lower()
                    for keyword in keywords:
                        if keyword in link_text or keyword in href:
                            full_url = urljoin(self.base_url, href)
                            important_links[key] = full_url
                            break # Found for this keyword set, move to next key

        return important_links if important_links else {"status": "No important links found."}

    def run_all(self):
        """Runs all scraping methods and returns a consolidated dictionary."""
        if not self.homepage_soup:
            return {"error": "Could not fetch the store's homepage. Please check the URL."}

        return {
            "product_catalog": self.get_product_catalog(),
            "hero_products": self.get_hero_products(),
            "social_media_links": self.get_social_media_links(),
            "contact_info": self.get_contact_info(),
            "important_links": self.get_important_links(),
            "about_us_text": self.get_page_text(['/pages/about', '/pages/about-us']),
            "privacy_policy": self.get_page_text(['/policies/privacy-policy']),
            "return_policy": self.get_page_text(['/policies/return-policy', '/policies/shipping-policy']),
            "refund_policy": self.get_page_text(['/policies/refund-policy']),
            "faq_page": self.get_faqs(['/pages/faq', '/pages/faqs', '/pages/frequently-asked-questions']),
        }

if __name__ == '__main__':
    # Example Usage for testing the scraper directly
    scraper = ShopifyScraper("https://memy.co.in")
    data = scraper.run_all()
    if not data.get("error"):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data["error"])

    print("\n--- Testing another URL ---")
    scraper2 = ShopifyScraper("https://allbirds.com")
    data2 = scraper2.run_all()
    if not data2.get("error"):
        print(json.dumps(data2, indent=2, ensure_ascii=False))
    else:
        print(data2["error"])