#!/usr/bin/env python3
"""Generado por la skill github-artifact-uploader. Regenera el portal de
artifacts a partir del checkout local (usando portal_render.py, en esta
misma carpeta) y lo publica en el repo destino."""
import base64, json, os, sys, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portal_render import extract_app_metadata, render_portal_html

API_ROOT = "https://api.github.com"

FOLDER = "artifacts"
DEST_OWNER = "RafaUMH2110"
DEST_REPO = "IAC"
DEST_PATH = "artifacts/index.html"
DEST_BRANCH = "main"
TITLE = "Herramientas de IA para la Docencia (HIAD)"
SUBTITLE = "Aplicaciones de inteligencia artificial para dise\u00f1o de moda, generaci\u00f3n de contenido y automatizaci\u00f3n de procesos acad\u00e9micos."
EYEBROW = "RafaUMH2110 \u00b7 UMH"
CONTACT_NAME = "Rafael Puerto"
CONTACT_EMAIL = "r.puerto@umh.es"


def api_request(url, token, method="GET", payload=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "artifacts-portal-sync",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"message": body.decode("utf-8", errors="replace")}
        return e.code, parsed


def list_local_apps(folder):
    """Recorre folder buscando .html/.htm con metadatos data-app-title."""
    apps = []
    for root, _, files in os.walk(folder):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            meta = extract_app_metadata(content)
            if meta is None:
                continue
            apps.append((rel, meta))
    return apps


def path_to_url(pages_owner, pages_repo, rel):
    owner_lc = pages_owner.lower()
    base = f"https://{owner_lc}.github.io/{pages_repo}"
    if rel == "index.html":
        return f"{base}/"
    if rel.endswith("/index.html"):
        slug = rel[: -len("/index.html")]
        return f"{base}/{slug}/"
    return f"{base}/{rel}"


def get_existing_sha(owner, repo, path, branch, token):
    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    status, body = api_request(url, token, method="GET")
    if status == 200 and isinstance(body, dict) and "sha" in body:
        return body["sha"]
    if status == 404:
        return None
    raise RuntimeError(f"Error comprobando destino (HTTP {status}): {body.get('message', body)}")


def put_file(owner, repo, path, branch, content_bytes, message, token):
    sha = get_existing_sha(owner, repo, path, branch, token)
    payload = {"message": message, "content": base64.b64encode(content_bytes).decode("ascii"), "branch": branch}
    if sha:
        payload["sha"] = sha
    status, body = api_request(f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}", token, method="PUT", payload=payload)
    if status not in (200, 201):
        raise RuntimeError(f"Fallo al subir el portal (HTTP {status}): {body.get('message', body)}")
    return body


def main():
    token = os.environ.get("DEST_TOKEN")
    if not token:
        print("ERROR: falta la variable de entorno DEST_TOKEN", file=sys.stderr)
        sys.exit(1)

    pages_owner_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in pages_owner_repo:
        print("ERROR: no se pudo determinar GITHUB_REPOSITORY", file=sys.stderr)
        sys.exit(1)
    pages_owner, pages_repo = pages_owner_repo.split("/", 1)

    local_apps = list_local_apps(FOLDER)
    if not local_apps:
        print("No se encontraron apps con metadatos de catálogo; no se actualiza el portal.")
        return

    catalog = []
    for rel, meta in local_apps:
        meta["url"] = path_to_url(pages_owner, pages_repo, rel)
        catalog.append(meta)

    html_out = render_portal_html(
        catalog, TITLE, SUBTITLE, EYEBROW,
        contact_name=CONTACT_NAME, contact_email=CONTACT_EMAIL,
    ).encode("utf-8")

    put_file(DEST_OWNER, DEST_REPO, DEST_PATH, DEST_BRANCH, html_out,
             "Update artifacts portal (auto-sync)", token)
    print(f"Portal actualizado con {len(catalog)} apps -> {DEST_OWNER}/{DEST_REPO}:{DEST_PATH}")


if __name__ == "__main__":
    main()
