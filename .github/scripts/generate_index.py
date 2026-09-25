#!/usr/bin/env python3
"""Generado por la skill github-artifact-uploader. Regenera el índice de
artifacts a partir del checkout local y lo publica en el repo destino."""
import argparse, base64, html, json, os, sys, urllib.request, urllib.error

API_ROOT = "https://api.github.com"


def api_request(url, token, method="GET", payload=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "artifacts-index-sync",
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


def list_local_html(folder):
    items = []
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith((".html", ".htm")):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, folder).replace(os.sep, "/")
                items.append(rel)
    return sorted(items)


def path_to_url_and_label(owner, repo, rel):
    owner_lc = owner.lower()
    base = f"https://{owner_lc}.github.io/{repo}"
    if rel == "index.html":
        return "index", f"{base}/"
    if rel.endswith("/index.html"):
        slug = rel[: -len("/index.html")]
        return slug, f"{base}/{slug}/"
    label = rel.rsplit(".", 1)[0]
    return label, f"{base}/{rel}"


def render_html(title, links):
    items_html = "\n".join(
        f'      <li><a href="{html.escape(url)}">{html.escape(label)}</a></li>'
        for label, url in links
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
    h1 {{ font-size: 1.6rem; }}
    ul {{ line-height: 2; padding-left: 1.2rem; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <ul>
{items_html}
  </ul>
  <p style="margin-top:2rem;color:#666;font-size:0.85rem;">Generado automáticamente al hacer push a artifacts/.</p>
</body>
</html>
"""


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
        raise RuntimeError(f"Fallo al subir el índice (HTTP {status}): {body.get('message', body)}")
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="artifacts")
    parser.add_argument("--dest-owner", default="RafaUMH2110")
    parser.add_argument("--dest-repo", default="IAC")
    parser.add_argument("--dest-path", default="artifacts/index.html")
    parser.add_argument("--dest-branch", default="main")
    parser.add_argument("--title", default='Índice de artifacts de Rafa')
    args = parser.parse_args()

    token = os.environ.get("DEST_TOKEN")
    if not token:
        print("ERROR: falta la variable de entorno DEST_TOKEN", file=sys.stderr)
        sys.exit(1)

    pages_owner_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in pages_owner_repo:
        print("ERROR: no se pudo determinar GITHUB_REPOSITORY", file=sys.stderr)
        sys.exit(1)
    pages_owner, pages_repo = pages_owner_repo.split("/", 1)

    rels = list_local_html(args.folder)
    if not rels:
        print("No se encontraron artifacts HTML; no se actualiza el índice.")
        return

    links = [path_to_url_and_label(pages_owner, pages_repo, r) for r in rels]
    content = render_html(args.title, links).encode("utf-8")

    put_file(args.dest_owner, args.dest_repo, args.dest_path, args.dest_branch, content,
             "Update artifacts index (auto-sync)", token)
    print(f"Índice actualizado con {len(links)} enlaces -> {args.dest_owner}/{args.dest_repo}:{args.dest_path}")


if __name__ == "__main__":
    main()
