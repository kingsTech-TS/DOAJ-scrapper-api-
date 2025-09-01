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
    base_url = "https://doaj.org/api/v2/search/articles"  # ✅ fixed (no trailing /)
    results = []

    # --- No year filter (simple case) ---
    if not year_from or not year_to:
        query_str = f'(bibjson.subject.exact:"{query}" OR bibjson.keywords:"{query}" OR bibjson.title:"{query}")'
        params = {"q": query_str, "pageSize": size, "page": 1}

        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print("Error fetching DOAJ:", e)
            return []

        for record in data.get("results", []):
            bibjson = record.get("bibjson", {})

            results.append({
                "Journal": bibjson.get("journal", {}).get("title", ""),
                "Title": bibjson.get("title", ""),
                "Authors": ", ".join([a.get("name", "") for a in bibjson.get("author", []) if a.get("name")]),
                "Year": int(bibjson.get("year", 0)) if str(bibjson.get("year", "")).isdigit() else 0,
                "URL": bibjson.get("link", [{}])[0].get("url", "")
            })

        return results

    # --- Year-by-year loop (descending) ---
    for year in range(year_to, year_from - 1, -1):
        page = 1
        while len(results) < size:
            query_str = (
                f'(bibjson.subject.exact:"{query}" OR '
                f'bibjson.keywords:"{query}" OR '
                f'bibjson.title:"{query}") AND bibjson.year:{year}'
            )

            params = {"q": query_str, "pageSize": min(100, size - len(results)), "page": page}

            try:
                response = requests.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                print(f"Error fetching DOAJ for year {year}, page {page}:", e)
                break

            records = data.get("results", [])
            if not records:
                break  # no more results for this year

            for record in records:
                bibjson = record.get("bibjson", {})

                results.append({
                    "Journal": bibjson.get("journal", {}).get("title", ""),
                    "Title": bibjson.get("title", ""),
                    "Authors": ", ".join([a.get("name", "") for a in bibjson.get("author", []) if a.get("name")]),
                    "Year": int(bibjson.get("year", 0)) if str(bibjson.get("year", "")).isdigit() else 0,
                    "URL": bibjson.get("link", [{}])[0].get("url", "")
                })

                if len(results) >= size:
                    break  # stop once we reach the target

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
