import requests
import os

def get_extraction_instructions(query, model="llama3"):
    """
    Uses Ollama local LLM to convert user query to extraction instructions.
    Ollama must be running locally (default: http://localhost:11434)
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": f"Convert this query to extraction instructions for a web scraper: {query}\nRespond with a JSON object specifying data types (emails, images, tables, etc.) and selectors if needed."
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get("response", "")
    else:
        return f"Error: {response.status_code}"

# Example usage
if __name__ == "__main__":
    query = "Get all emails and images from the gallery section"
    print(get_extraction_instructions(query))
