from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from scraper import ShopifyScraper
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
import csv
from io import StringIO
import re

app = FastAPI(
    title="Shopify Store Scraper API",
    description="An API to scrape public data from a Shopify store URL.",
    version="1.0.0"
)

# Pydantic model for input validation
class StoreRequest(BaseModel):
    url: HttpUrl

# --- CSV Conversion Helper (unchanged) ---
def clean_text_for_csv(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('\n', ' ').replace('\r', '')
    return text

def flatten_data_for_csv(scraped_data: dict, base_url: str) -> list[dict]:
    flat_records = []

    if scraped_data.get("product_catalog"):
        for product in scraped_data["product_catalog"]:
            price = product.get("variants", [{}])[0].get("price")
            price_str = str(price) if price is not None else "N/A"

            flat_records.append({
                "Category": "Product",
                "Subcategory": "Catalog",
                "Title": clean_text_for_csv(product.get("title")),
                "Handle": product.get("handle"),
                "Product_Type": clean_text_for_csv(product.get("product_type")),
                "Vendor": clean_text_for_csv(product.get("vendor")),
                "Price": price_str,
                "Published_At": product.get("published_at"),
                "Tags": clean_text_for_csv(", ".join(product.get("tags", []))),
                "Product_URL": f"{base_url}/products/{product.get('handle')}"
            })

    if scraped_data.get("hero_products"):
        for hero_product in scraped_data["hero_products"]:
            hero_price_str = str(hero_product.get("price")) if hero_product.get("price") else "N/A"
            
            flat_records.append({
                "Category": "Product",
                "Subcategory": "Hero",
                "Title": clean_text_for_csv(hero_product.get("title")),
                "Handle": hero_product.get("handle", "N/A"),
                "Product_URL": hero_product.get("url"),
                "Price": hero_price_str,
                "Product_Type": "", "Vendor": "", "Published_At": "", "Tags": ""
            })

    if scraped_data.get("social_media_links"):
        if isinstance(scraped_data["social_media_links"], dict):
            for platform, url in scraped_data["social_media_links"].items():
                if url and url != "status":
                    flat_records.append({
                        "Category": "Social Media",
                        "Platform": platform.capitalize(),
                        "URL": url,
                        "Title": "", "Handle": "", "Product_Type": "", "Vendor": "",
                        "Price": "", "Published_At": "", "Tags": "", "Product_URL": ""
                    })
        elif isinstance(scraped_data["social_media_links"], str) and "No social media links found." in scraped_data["social_media_links"]:
            flat_records.append({
                "Category": "Social Media",
                "Status": "No social media links found."
            })

    contact_info = scraped_data.get("contact_info", {})
    emails = contact_info.get("emails", [])
    phone_numbers = contact_info.get("phone_numbers", [])

    if isinstance(emails, list) and emails and emails[0] != "Not found.":
        for email in emails:
            flat_records.append({
                "Category": "Contact Info",
                "Type": "Email",
                "Value": email,
                "Title": "", "Handle": "", "Product_Type": "", "Vendor": "",
                "Price": "", "Published_At": "", "Tags": "", "Product_URL": ""
            })
    if isinstance(phone_numbers, list) and phone_numbers and phone_numbers[0] != "Not found.":
        for phone in phone_numbers:
            flat_records.append({
                "Category": "Contact Info",
                "Type": "Phone Number",
                "Value": phone,
                "Title": "", "Handle": "", "Product_Type": "", "Vendor": "",
                "Price": "", "Published_At": "", "Tags": "", "Product_URL": ""
            })
    if (not emails or emails[0] == "Not found.") and (not phone_numbers or phone_numbers[0] == "Not found."):
         flat_records.append({
                "Category": "Contact Info",
                "Status": "No contact info found."
            })


    text_fields = {
        "Privacy Policy": scraped_data.get("privacy_policy"),
        "Return Policy": scraped_data.get("return_policy"),
        "Refund Policy": scraped_data.get("refund_policy"),
        "About Us Text": scraped_data.get("about_us_text")
    }
    for field_name, text_content in text_fields.items():
        cleaned_content = clean_text_for_csv(text_content)
        if cleaned_content and cleaned_content != "Not found." and cleaned_content != "Not found or could not parse.":
            flat_records.append({
                "Category": "Text Content",
                "Section": field_name,
                "Content": cleaned_content,
                "Title": "", "Handle": "", "Product_Type": "", "Vendor": "",
                "Price": "", "Published_At": "", "Tags": "", "Product_URL": ""
            })
        elif field_name == "About Us Text":
             flat_records.append({
                "Category": "Text Content",
                "Section": field_name,
                "Content": "Not found."
            })


    faq_data = scraped_data.get("faq_page")
    if isinstance(faq_data, list) and faq_data and faq_data[0].get("answer") != "No FAQs found or parsed.":
        for faq in faq_data:
            flat_records.append({
                "Category": "FAQ",
                "Question": clean_text_for_csv(faq.get("question")),
                "Answer": clean_text_for_csv(faq.get("answer")),
                "Title": "", "Handle": "", "Product_Type": "", "Vendor": "",
                "Price": "", "Published_At": "", "Tags": "", "Product_URL": ""
            })
    else:
        flat_records.append({
            "Category": "FAQ",
            "Status": "No FAQs found or parsed."
        })

    if scraped_data.get("important_links"):
        if isinstance(scraped_data["important_links"], dict):
            for key, url in scraped_data["important_links"].items():
                if url and url != "status":
                    flat_records.append({
                        "Category": "Important Link",
                        "Label": key.replace('_', ' ').title(),
                        "URL": url,
                        "Title": "", "Handle": "", "Product_Type": "", "Vendor": "",
                        "Price": "", "Published_At": "", "Tags": "", "Product_URL": ""
                    })
        elif isinstance(scraped_data["important_links"], str) and "No important links found." in scraped_data["important_links"]:
            flat_records.append({
                "Category": "Important Link",
                "Status": "No important links found."
            })

    return flat_records

# --- API Endpoints (unchanged) ---

@app.post("/scrape/", summary="Scrape a Shopify Store and return JSON data")
async def scrape_store_json(request: StoreRequest):
    try:
        scraper = ShopifyScraper(str(request.url))
        data = scraper.run_all()

        if data.get("error"):
            raise HTTPException(status_code=400, detail=data["error"])
        
        return JSONResponse(content=data)

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during scraping: {str(e)}")


@app.post("/scrape-csv/", summary="Scrape a Shopify Store and download as CSV")
async def scrape_store_csv(request: StoreRequest):
    try:
        scraper = ShopifyScraper(str(request.url))
        data = scraper.run_all()

        if data.get("error"):
            raise HTTPException(status_code=400, detail=data["error"])

        flat_data = flatten_data_for_csv(data, str(request.url))

        if not flat_data:
            raise HTTPException(status_code=204, detail="No extractable data found to convert to CSV.")

        output = StringIO()
        
        fieldnames = set()
        for record in flat_data:
            fieldnames.update(record.keys())
        
        preferred_order = ["Category", "Subcategory", "Title", "Handle", "URL", "Product_URL", "Platform", "Type", "Value", "Question", "Answer", "Section", "Content", "Label", "Name", "Product_Type", "Vendor", "Price", "Published_At", "Tags", "Status"]
        sorted_fieldnames = sorted(list(fieldnames), key=lambda x: preferred_order.index(x) if x in preferred_order else len(preferred_order))


        writer = csv.DictWriter(output, fieldnames=sorted_fieldnames, extrasaction='ignore', restval='')
        writer.writeheader()
        writer.writerows(flat_data)

        output.seek(0)

        headers = {
            "Content-Disposition": f"attachment; filename={request.url.host.replace('.', '_')}_shopify_data.csv"
        }
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- Updated HTML Interface for Black & Gradient Mix with Animation ---
@app.get("/", summary="Web Interface for Shopify Scraper", response_class=HTMLResponse)
async def read_root_with_form():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Shopify Scraper Pro</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-color: #6a11cb; /* Your gradient start */
                --secondary-color: #2575fc; /* Your gradient end */
                --text-color-light: #f0f0f0; /* For text on dark backgrounds */
                --text-color-dark: #333; /* For text on light backgrounds */
                --bg-gradient-start: #1a1a1a; /* Darker gradient start */
                --bg-gradient-end: #333333; /* Darker gradient end */
                --card-bg: rgba(0, 0, 0, 0.7); /* Semi-transparent black card */
                --input-bg: #3a3a3a; /* Darker input background */
                --input-text: #f0f0f0;
                --input-border: #555;
                --button-bg-json: linear-gradient(45deg, #28a745, #3cb056); /* Gradient for JSON button */
                --button-hover-json: linear-gradient(45deg, #218838, #309947);
                --button-bg-csv: linear-gradient(45deg, #007bff, #0056b3); /* Gradient for CSV button */
                --button-hover-csv: linear-gradient(45deg, #0056b3, #004085);
                --error-color: #ff6b6b; /* Brighter error for dark background */
                --success-color: #66bb6a; /* Brighter success for dark background */
                --response-bg: #2a2a2a; /* Dark background for response container */
                --response-text: #e0e0e0;
            }

            body {
                font-family: 'Poppins', sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                /* Animated gradient properties */
                background: linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end), var(--primary-color), var(--secondary-color));
                background-size: 400% 400%; /* Make the background larger than the viewport */
                animation: gradientAnimation 20s ease infinite alternate; /* Apply animation */
                color: var(--text-color-light);
                line-height: 1.6;
                overflow: hidden; /* Hide scrollbars that might appear due to large background */
            }

            /* Keyframes for the gradient animation */
            @keyframes gradientAnimation {
                0% {
                    background-position: 0% 50%;
                }
                50% {
                    background-position: 100% 50%;
                }
                100% {
                    background-position: 0% 50%;
                }
            }

            .container {
                background: var(--card-bg);
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
                padding: 40px;
                max-width: 700px;
                width: 90%;
                text-align: center;
                animation: fadeIn 0.8s ease-out;
                border: 1px solid rgba(255, 255, 255, 0.1);
                position: relative; /* Needed for z-index */
                z-index: 1; /* Ensure container is above background animation */
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            h1 {
                font-size: 2.5em;
                color: var(--primary-color);
                margin-bottom: 10px;
                font-weight: 700;
                text-shadow: 2px 2px 5px rgba(0,0,0,0.3);
            }

            p {
                font-size: 1.1em;
                color: var(--text-color-light);
                margin-bottom: 30px;
            }

            form {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }

            label {
                font-size: 1.1em;
                font-weight: 600;
                color: var(--secondary-color);
                text-align: left;
                margin-bottom: 5px;
            }

            input[type="url"] {
                padding: 12px 15px;
                border: 1px solid var(--input-border);
                border-radius: 8px;
                font-size: 1em;
                width: 100%;
                box-sizing: border-box;
                background-color: var(--input-bg);
                color: var(--input-text);
                transition: border-color 0.3s ease, box-shadow 0.3s ease;
            }

            input[type="url"]:focus {
                border-color: var(--secondary-color);
                box-shadow: 0 0 0 3px rgba(37, 117, 252, 0.3);
                outline: none;
            }

            .button-group {
                display: flex;
                gap: 15px;
                justify-content: center;
                margin-top: 10px;
                flex-wrap: wrap;
            }

            button {
                padding: 12px 25px;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.3s ease, transform 0.2s ease;
                flex-grow: 1;
                max-width: 250px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            }

            #scrapeJsonBtn {
                background: var(--button-bg-json);
            }

            #scrapeJsonBtn:hover {
                background: var(--button-hover-json);
                transform: translateY(-2px);
            }

            #downloadCsvBtn {
                background: var(--button-bg-csv);
            }

            #downloadCsvBtn:hover {
                background: var(--button-hover-csv);
                transform: translateY(-2px);
            }

            #response-container {
                margin-top: 40px;
                background-color: var(--response-bg);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                padding: 20px;
                text-align: left;
                max-height: 400px;
                overflow-y: auto;
                box-shadow: inset 0 2px 5px rgba(0, 0, 0, 0.1);
            }

            pre {
                white-space: pre-wrap;
                word-wrap: break-word;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 0.9em;
                color: var(--response-text);
                margin: 0;
            }

            .message {
                margin-top: 15px;
                font-size: 1em;
                font-weight: 600;
            }

            .error {
                color: var(--error-color);
            }

            .success {
                color: var(--success-color);
            }

            /* Responsive adjustments */
            @media (max-width: 768px) {
                .container {
                    padding: 30px 20px;
                }
                h1 {
                    font-size: 2em;
                }
                p {
                    font-size: 1em;
                }
                .button-group {
                    flex-direction: column;
                }
                button {
                    max-width: 100%;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Shopify Scraper Pro</h1>
            <p>Unlock insights from any Shopify store effortlessly. Get product catalogs, social links, policies, and more!</p>
            <form id="scrapeForm">
                <label for="storeUrl">Shopify Store URL:</label>
                <input type="url" id="storeUrl" name="url" placeholder="e.g., https://memy.co.in" required>
                <div class="button-group">
                    <button type="submit" id="scrapeJsonBtn">Scrape & View JSON</button>
                    <button type="submit" id="downloadCsvBtn">Scrape & Download CSV</button>
                </div>
            </form>
            <div id="response-container">
                <pre id="response-json"></pre>
                <div id="response-message" class="message"></div>
            </div>
        </div>

        <script>
            document.getElementById('scrapeForm').addEventListener('submit', async function(event) {
                event.preventDefault(); // Prevent default form submission

                const urlInput = document.getElementById('storeUrl');
                const storeUrl = urlInput.value;
                const responseJsonDiv = document.getElementById('response-json');
                const responseMessageDiv = document.getElementById('response-message');
                const submitter = event.submitter; // Get the button that was clicked

                responseJsonDiv.textContent = 'Scraping... Please wait.';
                responseMessageDiv.className = 'message';
                responseMessageDiv.textContent = ''; // Clear previous message

                try {
                    let endpoint = '/scrape/';
                    let headers = { 'Content-Type': 'application/json' };
                    let response;

                    if (submitter.id === 'downloadCsvBtn') {
                        endpoint = '/scrape-csv/';
                        
                        response = await fetch(endpoint, {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify({ url: storeUrl })
                        });

                        if (response.ok) {
                            if (response.status === 204) {
                                responseJsonDiv.textContent = '';
                                responseMessageDiv.className = 'message error';
                                responseMessageDiv.textContent = 'No extractable data found for CSV.';
                            } else {
                                const blob = await response.blob();
                                const contentDisposition = response.headers.get('Content-Disposition');
                                let filename = 'shopify_data.csv';
                                if (contentDisposition) {
                                    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                                    if (filenameMatch && filenameMatch[1]) {
                                        filename = filenameMatch[1];
                                    }
                                }
                                const downloadUrl = window.URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = downloadUrl;
                                a.download = filename;
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                window.URL.revokeObjectURL(downloadUrl);
                                responseJsonDiv.textContent = '';
                                responseMessageDiv.className = 'message success';
                                responseMessageDiv.textContent = 'CSV file downloaded successfully!';
                            }
                        } else {
                            const errorData = await response.json();
                            responseJsonDiv.textContent = JSON.stringify(errorData, null, 2);
                            responseMessageDiv.className = 'message error';
                            responseMessageDiv.textContent = `Error: ${errorData.detail || 'Failed to download CSV.'}`;
                        }

                    } else { // 'scrapeJsonBtn' was clicked
                        response = await fetch(endpoint, {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify({ url: storeUrl })
                        });

                        const data = await response.json();

                        if (response.ok) {
                            responseJsonDiv.textContent = JSON.stringify(data, null, 2);
                            responseMessageDiv.className = 'message success';
                            responseMessageDiv.textContent = 'Data scraped successfully!';
                        } else {
                            responseJsonDiv.textContent = JSON.stringify(data, null, 2);
                            responseMessageDiv.className = 'message error';
                            responseMessageDiv.textContent = `Error: ${data.detail || 'Scraping failed.'}`;
                        }
                    }

                } catch (error) {
                    responseJsonDiv.textContent = '';
                    responseMessageDiv.className = 'message error';
                    responseMessageDiv.textContent = `An unexpected network error occurred: ${error.message}`;
                    console.error('Fetch error:', error);
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)