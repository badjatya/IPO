"""Small stdlib HTTP client with a cookie jar, browser headers and retries."""

import gzip
import http.cookiejar
import time
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)


class Client:
    def __init__(self, timeout=20, retries=2):
        self.timeout = timeout
        self.retries = retries
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def get(self, url, referer=None, accept="*/*"):
        headers = {
            "User-Agent": UA,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
        }
        if referer:
            headers["Referer"] = referer
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=self.timeout) as resp:
                    body = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        body = gzip.decompress(body)
                    return body
            except urllib.error.HTTPError as e:
                # Some sites set cookies on a 403 page; callers can still proceed.
                last_err = e
                if e.code in (401, 403, 404):
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
            time.sleep(1.5 * (attempt + 1))
        raise last_err

    def get_text(self, url, **kw):
        return self.get(url, **kw).decode("utf-8", errors="replace")
