from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
from typing import Optional, List

app = FastAPI(title="DOAJ Article Search API", version="1.0.0")


class Article(BaseModel):
    Journal: str
    Title: str
    Authors: str
    Year: int
    URL: str


def search_doaj(query: str, year_from: Optional[int] = None, year_to: Optional[int] = None, size: int = 20):
    """
    Search DOAJ API for articles by exact subject/title/keywords.
    Ensures results are collected year by year in descending order.
    """
    base_url = "https://doaj.org/api/v2/search/articles/"
    results = []

    # If no year range is provided, fetch normally
    if not year_from or not year_to:
        query_str = f'(bibjson.subject.exact:"{query}" OR bibjson.keywords:"{query}" OR bibjson.title:"{query}")'
        url = base_url + query_str
        params = {"pageSize": size}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        for record in data.get("results", []):
            bibjson = record.get("bibjson", {})

            results.append({
                "Journal": bibjson.get("journal", {}).get("title", ""),
                "Title": bibjson.get("title", ""),
                "Authors": ", ".join([a.get("name", "") for a in bibjson.get("author", [])]),
                "Year": int(bibjson.get("year", 0)) if str(bibjson.get("year", "")).isdigit() else 0,
                "URL": bibjson.get("link", [{}])[0].get("url", "")
            })

        return results

    # --- Year-by-year loop ---
    for year in range(year_to, year_from - 1, -1):  # descending order
        page = 1
        while len(results) < size:
            query_str = (
                f'(bibjson.subject.exact:"{query}" OR '
                f'bibjson.keywords:"{query}" OR '
                f'bibjson.title:"{query}") AND bibjson.year:{year}'
            )

            url = base_url + query_str
            params = {"pageSize": min(100, size - len(results)), "page": page}

            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
            except Exception:
                break

            records = data.get("results", [])
            if not records:
                break  # no more results for this year

            for record in records:
                bibjson = record.get("bibjson", {})

                results.append({
                    "Journal": bibjson.get("journal", {}).get("title", ""),
                    "Title": bibjson.get("title", ""),
                    "Authors": ", ".join([a.get("name", "") for a in bibjson.get("author", [])]),
                    "Year": int(bibjson.get("year", 0)) if str(bibjson.get("year", "")).isdigit() else 0,
                    "URL": bibjson.get("link", [{}])[0].get("url", "")
                })

                if len(results) >= size:
                    break  # reached target count

            page += 1

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
    return {
        "message": "Welcome to DOAJ Article Search API! Use /search?query=topic&year_from=2021&year_to=2025"
    }
