import os
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin
from openai import OpenAI
import csv


global headers


def extract_links(url):
    """
    Fetches all unique, absolute URLs and their associated texts from the specified webpage within a specific section.

    Args:
        url (str): The URL of the webpage to scrape.
        begin_word (str): The exact case-sensitive beginning keyword to locate the section.
        end_word (str): The exact case-sensitive ending keyword to locate the section.

    Returns:
        list of tuples: A list of tuples where each tuple contains (URL, Link Text).
    """


    try:
        # Send an HTTP GET request to the URL with custom headers
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")  # e.g., 403 Forbidden
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')



    # Find all <a> tags within the section
    a_tags = soup.find_all('a')

    links = []
    for tag in a_tags:
        href = tag.get('href')
        link_text = tag.get_text(strip=True)
        if href:
            # Convert relative URLs to absolute URLs
            absolute_url = urljoin(url, href)
            # Optionally, filter out URLs that are not HTTP/HTTPS
            if absolute_url.startswith(('http://', 'https://')):
                links.append((absolute_url, link_text))

    # Remove duplicates by converting the list to a set, then back to a list
    unique_links = list(set(links))

    # Apply URL filters
    filtered_urls = [
        (link, text) for (link, text) in unique_links
        if link.startswith("https://www.sec.gov/comments/") and
           not (
               link.endswith(".htm#main-content") or
               link.endswith(".htm#meetings") or
               link.endswith("htm#comments")
           )
    ]

    return filtered_urls

def save_links_to_file(links, filename):
    """
    Saves the list of links and their associated texts to a CSV file.

    Args:
        links (list of tuples): The list of (URL, Link Text) tuples to save.
        filename (str): The name of the file to save the URLs and texts in.
    """
    try:
        with open(filename, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            # Write the header
            writer.writerow(['URL', 'Link Text'])
            # Write the link data
            for link, text in links:
                writer.writerow([link, text])
        print(f"Successfully saved {len(links)} links to '{filename}'.")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

#specify rules to scrape comments for
rule = 's70715'

target_url = "https://www.sec.gov/comments/s7-07-15/{}.htm".format(rule)

extracted_links = extract_links(target_url)




def get_file_extension(url, response):
    """
    Determines the file extension based on the URL or the response's Content-Type header.
    Supports PDF and HTML files.
    """
    # Attempt to extract extension from URL
    path = urlsplit(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in ['.pdf', '.htm', '.html']:
        return ext if ext != '.htm' else '.html'  # Normalize to .html

    # Fallback: Determine from Content-Type header



    content_type = response.headers.get('Content-Type', '').lower()
    if 'application/pdf' in content_type:
        return '.pdf'
    elif 'text/html' in content_type:
        return '.html'
    else:
        return ''


def sanitize_filename(filename, max_length=100):
    """
    Removes or replaces characters that are invalid in filenames.
    Limits the filename length to max_length characters.
    Appends a unique hash to avoid conflicts.
    """
    # Define valid characters
    valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    # Remove invalid characters
    sanitized = ''.join(c for c in filename if c in valid_chars)

    # Truncate the filename if it exceeds max_length - length of hash
    hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:6]  # 6-character hash
    if len(sanitized) > (max_length - 7):  # 6 for hash, 1 for underscore
        sanitized = sanitized[:max_length - 7].rstrip() + "_"

    sanitized = f"{sanitized}{hash_suffix}"

    return sanitized or "default_filename"


def download_file(name, url):
    """
    Downloads a file from a URL and saves it with the specified name and correct extension.
    Handles PDF and HTML files.
    """
    try:
        # Initiate the GET request
        with requests.get(url, stream=True, timeout=15, headers = headers) as response:
            response.raise_for_status()  # Raise an error for bad status codes

            # Determine the file extension
            ext = get_file_extension(url, response)
            if not ext:
                print(f"⚠️  Warning: Could not determine the file extension for '{name}'. Skipping download.")
                return

            # Sanitize the filename
            safe_name = sanitize_filename(name)


            # Get total size in bytes for progress bar
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                print(f"⚠️  Warning: Cannot determine the size of '{name}'. Downloading without progress bar.")
                total_size = None  # tqdm will handle it

            # Download the file with a progress bar
            with open(safe_name, 'wb') as file, tqdm(
                total=total_size, unit='iB', unit_scale=True,
                desc=f"Downloading {safe_name}{ext}", leave=False
            ) as progress_bar:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:  # Filter out keep-alive chunks
                        file.write(chunk)
                        progress_bar.update(len(chunk))


    except requests.exceptions.HTTPError as http_err:
        print(f"❌  HTTP error occurred for '{name}': {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        print(f"❌  Connection error occurred for '{name}': {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        print(f"❌  Timeout error occurred for '{name}': {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"❌  An error occurred for '{name}': {req_err}")
    except Exception as e:
        print(f"❌  An unexpected error occurred for '{name}': {e}")



# Iterate through each tuple in extracted_links
for index, (url, name) in enumerate(extracted_links, start=1):
    if not url or not name:
        print(f"⚠️  Skipping entry {index}: Missing 'Link' or 'Name'.")
        continue

    download_file(name, url)

print("All downloads completed.")
