#!/usr/bin/env python3
"""
Generic extractor – terminalde sorular sorar, istenen veriyi (tablolar, linkler,
paragraflar veya özel CSS seçici) JSON/CSV olarak kaydeder.
"""

import time
from pathlib import Path
from typing import List
import pandas as pd
from bs4 import BeautifulSoup
import requests
import sys
import json
from io import StringIO


# ---------- HTML GETTERS ----------
def fetch_static_html(url: str) -> str:
    r = requests.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (generic-extractor 1.0)"})
    r.raise_for_status()
    return r.text


def fetch_dynamic_html(url: str, wait: int = 8) -> str:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service(
        ChromeDriverManager().install()), options=opts)
    driver.get(url)
    time.sleep(wait)
    html = driver.page_source
    driver.quit()
    return html


# ---------- EXTRACTORS ----------
def safe_read_html(html: str) -> list[pd.DataFrame]:
    try:
        from lxml import etree  # noqa: F401
    except ImportError:
        try:
            import html5lib  # noqa: F401
        except ImportError:
            raise ImportError(
                "read_html için lxml veya html5lib gerekir; "
                "`pip install lxml html5lib` komutunu çalıştır."
            )
    return pd.read_html(StringIO(html))


def extract_tables(html: str) -> List[pd.DataFrame]:
    return safe_read_html(html)


def choose_tables(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        print("❌  Sayfada tablo bulunamadı.")
        sys.exit(1)

    print(f"\n➡️  {len(dfs)} tablo bulundu:")
    for i, df in enumerate(dfs):
        print(f"\nTable #{i}\n-----------\n{df.head(2).to_string(index=False)}"
              f"\n...({df.shape[0]} satır, {df.shape[1]} sütun)")

    sel = input("\nKaydedilecek tablo(lar) (virgülle #, 'all', boş=ilk): ").strip()
    if not sel:
        return pd.concat([dfs[0]], ignore_index=True)
    if sel.lower() == "all":
        return pd.concat(dfs, ignore_index=True)
    idxs = [int(x) for x in sel.split(",") if x.strip().isdigit()]
    return pd.concat([dfs[i] for i in idxs if i < len(dfs)], ignore_index=True)


def extract_links(soup: BeautifulSoup) -> pd.DataFrame:
    data = [{"text": a.get_text(strip=True), "href": a.get("href")} for a in soup.find_all("a")]
    return pd.DataFrame(data)


def extract_paragraphs(soup: BeautifulSoup) -> pd.DataFrame:
    data = [{"paragraph": p.get_text(" ", strip=True)} for p in soup.find_all("p")]
    return pd.DataFrame(data)


def extract_by_css(soup: BeautifulSoup, selector: str) -> pd.DataFrame:
    elems = soup.select(selector)
    data = [{"selector": selector, "text": e.get_text(" ", strip=True)} for e in elems]
    return pd.DataFrame(data)


# ---------- SAVE ----------
def save_df(df: pd.DataFrame, fmt: str, base_name: str):
    base = Path(base_name).stem
    fn = Path(f"{base}.{fmt}")
    if fmt == "csv":
        df.to_csv(fn, index=False)
    else:
        df.to_json(fn, orient="records", force_ascii=False, indent=2)
    print(f"✅  Kaydedildi → {fn.resolve()}")


# ---------- MAIN FLOW ----------
def main():
    url = input("🌐  Lütfen ekstrak yapılacak web sitesi URL'ini girin: ").strip()
    what = input(
        "📌  Siteden neyi çıkarayım?\n"
        "    [1] Tablo(lar)\n"
        "    [2] Linkler\n"
        "    [3] Paragraf metinleri\n"
        "    [4] Özel CSS seçici\n"
        "Seçiminiz (1-4): ").strip()

    js = input("🖥️  Sayfa JavaScript ile render ediliyor mu? [E/h] ").strip().lower() == "e"
    html = fetch_dynamic_html(url) if js else fetch_static_html(url)
    soup = BeautifulSoup(html, "lxml")

    if what == "1":
        df = choose_tables(extract_tables(html))
    elif what == "2":
        df = extract_links(soup)
    elif what == "3":
        df = extract_paragraphs(soup)
    elif what == "4":
        selector = input("CSS seçiciyi girin (örn. div.article p): ").strip()
        df = extract_by_css(soup, selector)
    else:
        print("❌  Geçersiz seçim.")
        sys.exit(1)

    fmt = input("💾  Çıktı formatı (csv/json) [csv]: ").strip().lower() or "csv"
    name = input("Dosya adı (uzantısız) [extracted]: ").strip() or "extracted"
    save_df(df, fmt, name)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔️  Kullanıcı iptal etti.")
    except Exception as exc:
        print("🚨  Hata:", exc)