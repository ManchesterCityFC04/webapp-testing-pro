"""Parse sitemap.xml and robots.txt for route discovery."""
import re
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from typing import Optional

import httpx


async def parse_sitemap(base_url: str, timeout: float = 15.0) -> list[str]:
    """
    Fetch sitemap.xml(s) and extract all <loc> URLs.
    Also reads robots.txt for allowed paths.
    Returns deduplicated list of URLs.
    """
    urls: set[str] = set()
    parsed_base = urlparse(base_url)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # Try sitemap.xml
        sitemap_url = urljoin(base_url, "sitemap.xml")
        try:
            resp = await client.get(sitemap_url)
            if resp.status_code == 200:
                urls.update(_extract_urls_from_xml(resp.text))

            # Handle sitemap-index (multiple sitemaps)
            resp_index = await client.get(urljoin(base_url, "sitemap-index.xml"))
            if resp_index.status_code == 200:
                for idx_url in _extract_urls_from_xml(resp_index.text):
                    sub_resp = await client.get(idx_url)
                    if sub_resp.status_code == 200:
                        urls.update(_extract_urls_from_xml(sub_resp.text))
        except Exception:
            pass  # sitemap not available, fall through

        # Try robots.txt for allowed paths
        try:
            resp = await client.get(urljoin(base_url, "robots.txt"))
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    line = line.strip()
                    if line.lower().startswith("allow:"):
                        path = line.split(":", 1)[1].strip()
                        full_url = urljoin(base_url, path)
                        if urlparse(full_url).netloc == parsed_base.netloc:
                            urls.add(full_url)
                    elif line.lower().startswith("sitemap:"):
                        sm_url = line.split(":", 1)[1].strip()
                        sm_resp = await client.get(sm_url)
                        if sm_resp.status_code == 200:
                            urls.update(_extract_urls_from_xml(sm_resp.text))
        except Exception:
            pass

    return list(urls)


def _extract_urls_from_xml(xml_text: str) -> list[str]:
    """Extract all <loc> URLs from XML text."""
    urls = []
    try:
        root = ET.fromstring(xml_text)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "loc":
                text = elem.text
                if text:
                    urls.append(text.strip())
    except ET.ParseError:
        # Not valid XML, try regex fallback
        urls.extend(re.findall(r"<loc[^>]*>([^<]+)</loc>", xml_text))
    return urls
