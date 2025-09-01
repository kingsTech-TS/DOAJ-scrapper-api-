from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import requests
from typing import Optional, List
from urllib.parse import quote, urljoin
from datetime import datetime

app = FastAPI(title="DOAJ Article Search API", version="1.1.0")


class Article(BaseModel):
    Journal: str
    Title: str
    Authors: str
    Year: Optional[int]
    URL: str


def search_doaj(query: str, year_from: Optional[int] = None, year_to: Optional[int] = None, size: int = 20):
    base_url = "https://doaj.org/api/search/articles/"
    results = []

    def fetch_for_query(q_str, max_items):
        page = 1  # DOAJ pages start at 1
        while len(results) < max_items:
            encoded = quote(q_str, safe="")
            full_url = urljoin(base_url, encoded)
            params = {"page": page, "pageSize": min(100, max_items - len(results))}
            try:
                resp = requests.get(full_url, params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                raise HTTPException(status_code=502, detail=f"DOAJ API error: {str(e)}")

            data = resp.json()
            records = data.get("results", [])
            if not records:
                break

            for rec in records:
                bib = rec.get("bibjson", {})
                authors = ", ".join(
                    a.get("name", "") for a in bib.get("author", []) if a.get("name")
                )
                year = int(bib.get("year")) if str(bib.get("year", "")).isdigit() else None
                url = next((l.get("url") for l in bib.get("link", []) if "url" in l), "")

                results.append({
                    "Journal": bib.get("journal", {}).get("title", ""),
                    "Title": bib.get("title", ""),
                    "Authors": authors,
                    "Year": year,
                    "URL": url
                })
                if len(results) >= max_items:
                    break

            page += 1

    # Handle flexible year ranges
    if year_from and not year_to:
        year_to = datetime.now().year
    if year_to and not year_from:
        year_from = 1900

    # If no year filters applied, do broad search
    if not year_from and not year_to:
        qs = f'(bibjson.subject.exact:"{query}" OR bibjson.keywords:"{query}" OR bibjson.title:"{query}")'
        fetch_for_query(qs, size)
        return results

    # Year-by-year descending search
    for year in range(year_to, year_from - 1, -1):
        qs = (
            f'(bibjson.subject.exact:"{query}" OR bibjson.keywords:"{query}" OR bibjson.title:"{query}") '
            f'AND bibjson.year:{year}'
        )
        fetch_for_query(qs, size)
        if len(results) >= size:
            break

    return results


@app.get("/search", response_model=List[Article])
def api_search(
    query: str = Query(..., description="Search topic e.g. Computer Science"),
    year_from: Optional[int] = Query(None, description="Start year"),
    year_to: Optional[int] = Query(None, description="End year"),
    size: int = Query(20, description="Number of results to return (max 1000 recommended)")
):
    return search_doaj(query, year_from, year_to, size)


@app.get("/")
def root():
    return {"message": "Use /search?query=topic&year_from=2021&year_to=2025&size=50"}
