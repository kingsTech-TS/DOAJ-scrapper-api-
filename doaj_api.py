from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
import pandas as pd
from typing import Optional, List

app = FastAPI(title="DOAJ Article Search API", version="1.0.0")


class Article(BaseModel):
    Journal: str
    Title: str
    Authors: str
    Year: str
    URL: str


def search_doaj(query: str, year_from: Optional[int] = None, year_to: Optional[int] = None, size: int = 20):
    """
    Search DOAJ API for articles by exact subject/title/keywords and optional year filter
    """
    base_url = "https://doaj.org/api/v2/search/articles/"

    # --- Enhanced query ---
    query_str = f'(bibjson.subject.exact:"{query}" OR bibjson.keywords:"{query}" OR bibjson.title:"{query}")'

    # Add year filter
    if year_from and year_to:
        query_str += f" AND bibjson.year:[{year_from} TO {year_to}]"

    url = base_url + query_str
    params = {"pageSize": size}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return []

    results = []
    for record in data.get("results", []):
        bibjson = record.get("bibjson", {})

        # Article title
        title = bibjson.get("title", "")

        # Authors
        authors = ", ".join([a.get("name", "") for a in bibjson.get("author", [])])

        # Year
        year = bibjson.get("year", "")

        # Journal name
        journal = bibjson.get("journal", {}).get("title", "")

        # Article URL (or DOI if available)
        links = bibjson.get("link", [])
        url_link = links[0].get("url") if links else ""

        results.append({
            "Journal": journal,
            "Title": title,
            "Authors": authors,
            "Year": year,
            "URL": url_link
        })

    return results


@app.get("/search", response_model=List[Article])
def api_search(
    query: str = Query(..., description="Search topic (e.g., African Studies, Computer Science)"),
    year_from: Optional[int] = Query(None, description="Start year (e.g., 2021)"),
    year_to: Optional[int] = Query(None, description="End year (e.g., 2025)"),
    size: int = Query(20, description="Number of articles to fetch")
):
    """
    REST API endpoint to search DOAJ for articles.
    """
    articles = search_doaj(query, year_from, year_to, size)
    return articles


@app.get("/")
def root():
    return {"message": "Welcome to DOAJ Article Search API! Use /search?query=topic&year_from=2021&year_to=2025"}
