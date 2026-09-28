"""Bounded web search and public-page extraction tools."""

from html.parser import HTMLParser
import ipaddress
import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from agent.tools.contracts import ToolResult

_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_MAX_QUERY_CHARS = 500
_MAX_PAGE_BYTES = 1_000_000
_MAX_PAGE_CHARS = 12_000
_MAX_REDIRECTS = 3
_USER_AGENT = "LocalAgent/1.0 (personal assistant; bounded page reader)"


class _TextExtractor(HTMLParser):
    """Extract readable text while excluding scripts, styles, and page chrome."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._title = False
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False
        if tag in {"script", "style", "noscript", "svg"} and self._ignored:
            self._ignored -= 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title_parts.append(data.strip())
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str,
                         headers: object, newurl: str) -> None:
        return None


def search_web(query: str, count: int = 5, country: str = "BR") -> ToolResult:
    """Search public web results through the configured Brave Search API."""
    if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY_CHARS:
        return ToolResult.failure("A busca deve conter entre 1 e 500 caracteres.")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 10:
        return ToolResult.failure("count deve estar entre 1 e 10.")
    if not isinstance(country, str) or len(country) != 2 or not country.isalpha():
        return ToolResult.failure("country deve ser um código de país de duas letras.")
    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        return ToolResult.failure(
            "Busca web desativada. Configure BRAVE_SEARCH_API_KEY no arquivo .env."
        )
    url = f"{_SEARCH_URL}?{urlencode({'q': query.strip(), 'count': count, 'country': country.upper(), 'search_lang': 'pt'})}"
    request = Request(url, headers={"X-Subscription-Token": api_key, "Accept": "application/json"})
    try:
        with build_opener().open(request, timeout=10) as response:
            payload = json.loads(response.read(1_000_000).decode("utf-8"))
        results = payload.get("web", {}).get("results", [])
        formatted = [
            {"title": str(item.get("title", ""))[:300],
             "url": str(item.get("url", ""))[:2000],
             "snippet": str(item.get("description", ""))[:1000]}
            for item in results[:count]
        ]
        return ToolResult.ok(json.dumps({"query": query, "results": formatted}, ensure_ascii=False))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ToolResult.failure("A busca web falhou. Verifique a conexão, a chave e os limites do provedor.")


def _validate_public_url(url: str) -> str | None:
    if len(url) > 2048:
        return "A URL excede o limite de 2048 caracteres."
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return "Informe uma URL pública HTTP ou HTTPS válida, sem credenciais."
        if parsed.port is not None and parsed.port not in {80, 443}:
            return "Somente portas HTTP/HTTPS padrão são permitidas."
        host = parsed.hostname.rstrip(".").casefold()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
            return "URLs locais ou internas não são permitidas."
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = [ipaddress.ip_address(result[4][0]) for result in socket.getaddrinfo(host, None)]
        if not addresses or any(not address.is_global for address in addresses):
            return "A URL precisa apontar somente para endereços públicos."
    except (ValueError, OSError):
        return "Não foi possível validar o endereço da página."
    return None


def read_webpage(url: str) -> ToolResult:
    """Fetch a small public HTML/text page while blocking private-network URLs."""
    if not isinstance(url, str) or not url.strip():
        return ToolResult.failure("Informe a URL da página.")
    current_url = url.strip()
    opener = build_opener(_NoRedirect)
    for redirect_count in range(_MAX_REDIRECTS + 1):
        validation_error = _validate_public_url(current_url)
        if validation_error:
            return ToolResult.failure(validation_error)
        request = Request(current_url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html,text/plain"})
        try:
            response = opener.open(request, timeout=10)
        except HTTPError as error:
            if error.code in {301, 302, 303, 307, 308}:
                location = error.headers.get("Location")
                if not location or redirect_count == _MAX_REDIRECTS:
                    return ToolResult.failure("A página excedeu o limite de redirecionamentos.")
                current_url = urljoin(current_url, location)
                continue
            return ToolResult.failure(f"A página retornou HTTP {error.code}.")
        except (URLError, TimeoutError, OSError):
            return ToolResult.failure("Não foi possível acessar a página. Verifique a URL e a conexão.")
        with response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                return ToolResult.failure("A página não é conteúdo HTML ou texto simples.")
            raw = response.read(_MAX_PAGE_BYTES + 1)
            encoding = response.headers.get_content_charset() or "utf-8"
        if len(raw) > _MAX_PAGE_BYTES:
            return ToolResult.failure("A página excede o limite de 1 MB.")
        try:
            content = raw.decode(encoding, errors="replace")
        except LookupError:
            content = raw.decode("utf-8", errors="replace")
        if content_type in {"text/html", "application/xhtml+xml"}:
            parser = _TextExtractor()
            parser.feed(content)
            title = " ".join(parser.title_parts)[:300]
            text = " ".join(" ".join(parser.parts).split())
        else:
            title, text = current_url, " ".join(content.split())
        return ToolResult.ok(json.dumps({
            "url": current_url, "title": title,
            "content": text[:_MAX_PAGE_CHARS],
            "truncated": len(text) > _MAX_PAGE_CHARS,
            "source_is_untrusted": True,
        }, ensure_ascii=False))
    return ToolResult.failure("A página excedeu o limite de redirecionamentos.")
