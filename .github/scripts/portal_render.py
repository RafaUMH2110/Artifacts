"""
Lógica compartida para el portal de artifacts de IAC.

Este archivo se usa de dos formas:
  1. Importado localmente por generate_portal.py (vía la API de GitHub).
  2. Copiado tal cual a .github/scripts/portal_render.py en el repo ORIGEN,
     donde lo importa el script de CI que corre en cada push (ver
     setup_cross_repo_sync.py).

Por eso no depende de nada más que la librería estándar de Python.
"""

import datetime
import html
import json
import re


# Catálogo de categorías conocidas: slug -> (etiqueta legible, icono de Lucide).
# Si aparece un slug nuevo que no esté aquí, se genera una etiqueta a partir
# del propio slug y se usa un icono genérico ("tag"), para que el sistema no
# se rompa cuando se añadan categorías nuevas en el futuro.
CATEGORY_INFO = {
    "ia": {"label": "Inteligencia Artificial", "icon": "brain-circuit"},
    "diseno-creatividad": {"label": "Diseño y creatividad", "icon": "palette"},
    "generacion-contenido": {"label": "Generación de contenido", "icon": "sparkles"},
    "docencia": {"label": "Docencia", "icon": "graduation-cap"},
    "automatizacion": {"label": "Automatización", "icon": "cog"},
    "evaluacion": {"label": "Evaluación", "icon": "clipboard-check"},
    "investigacion": {"label": "Investigación", "icon": "microscope"},
    "analisis-datos": {"label": "Análisis de datos", "icon": "bar-chart-3"},
    "programacion": {"label": "Programación", "icon": "code"},
    "productividad": {"label": "Productividad", "icon": "wrench"},
}


def category_info(slug):
    if slug in CATEGORY_INFO:
        return CATEGORY_INFO[slug]
    label = slug.replace("-", " ").replace("_", " ").strip().title() or slug
    return {"label": label, "icon": "tag"}


def extract_app_metadata(html_text):
    """
    Busca la etiqueta <body ...> y extrae sus atributos data-app-title,
    data-app-description, data-categories, data-tags y data-client-only.
    Devuelve None si el archivo no tiene data-app-title (se ignora: no todo
    HTML en la carpeta tiene por qué ser una app catalogada).
    """
    m = re.search(r"<body\b([^>]*)>", html_text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    attrs_blob = m.group(1)

    def get_attr(name):
        am = re.search(rf'{name}\s*=\s*"([^"]*)"', attrs_blob)
        return am.group(1) if am else None

    title = get_attr("data-app-title")
    if not title:
        return None

    description = get_attr("data-app-description") or ""
    categories = [c.strip() for c in (get_attr("data-categories") or "").split(",") if c.strip()]
    tags = [t.strip() for t in (get_attr("data-tags") or "").split(",") if t.strip()]
    client_only = (get_attr("data-client-only") or "").strip().lower() == "true"

    return {
        "title": title,
        "description": description,
        "categories": categories,
        "tags": tags,
        "client_only": client_only,
    }


PORTAL_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<script src="https://unpkg.com/lucide@latest"></script>
<style>
  :root {
    --blue-900:#0b2545; --blue-800:#123a6b; --blue-700:#1656a3; --blue-600:#1d6fd1;
    --blue-500:#3b82f6; --blue-100:#e5f0fd; --blue-50:#f4f9ff;
    --ink:#0f172a; --muted:#5b6b82; --border:#dde7f5; --card-bg:#ffffff;
    --bg:#f6f9fc; --radius:16px; --shadow:0 4px 22px rgba(15,45,90,0.07);
  }
  * { box-sizing: border-box; }
  body { margin:0; font-family: "Segoe UI", system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--ink); }
  .header { background: linear-gradient(135deg, var(--blue-900), var(--blue-700)); color:#fff; padding: 56px 24px 92px; }
  .header-inner { max-width: 1100px; margin: 0 auto; text-align: center; }
  .eyebrow { font-size: .85rem; letter-spacing:.03em; opacity:.85; margin-bottom: 14px; }
  .header h1 { font-size: 2.1rem; margin: 0 0 14px; font-weight: 700; }
  .header p.lede { max-width: 640px; margin: 0 auto 32px; opacity:.92; line-height:1.6; }
  .stats { display:flex; gap: 44px; flex-wrap:wrap; justify-content: center; }
  .stat-num { font-size: 2rem; font-weight: 700; }
  .stat-label { font-size:.82rem; opacity:.82; }
  .container { max-width: 1100px; margin: -60px auto 60px; padding: 0 24px; }
  .searchbar { background:#fff; border:1px solid var(--border); border-radius: 14px; box-shadow: var(--shadow); padding: 6px 6px 6px 18px; display:flex; align-items:center; gap:10px; }
  .searchbar input { flex:1; border:none; outline:none; font-size:1rem; padding: 12px 0; color: var(--ink); background: transparent; }
  .searchbar svg { color: var(--muted); flex-shrink:0; }
  .categories { display:flex; flex-wrap:wrap; gap: 10px; margin: 28px 0 8px; }
  .category-btn { display:flex; align-items:center; gap:8px; padding: 9px 16px; border-radius: 999px; border:1px solid var(--border); background:#fff; cursor:pointer; font-size:.9rem; color: var(--ink); transition: all .15s ease; }
  .category-btn:hover { border-color: var(--blue-500); color: var(--blue-700); }
  .category-btn.active { background: var(--blue-700); color:#fff; border-color: var(--blue-700); }
  .category-btn .count { background: rgba(15,45,90,.07); border-radius: 999px; padding: 1px 8px; font-size:.76rem; }
  .category-btn.active .count { background: rgba(255,255,255,.25); }
  .category-btn svg { width:16px; height:16px; }
  .results-line { color: var(--muted); font-size:.88rem; margin: 18px 0 14px; }
  .grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 20px; }
  .card { background: var(--card-bg); border:1px solid var(--border); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); display:flex; flex-direction:column; gap: 12px; transition: transform .15s ease, box-shadow .15s ease; }
  .card:hover { transform: translateY(-3px); box-shadow: 0 12px 32px rgba(15,45,90,.12); }
  .card-top { display:flex; align-items:center; gap:12px; }
  .card-icon { width:40px; height:40px; border-radius:10px; background: var(--blue-100); display:flex; align-items:center; justify-content:center; color: var(--blue-700); flex-shrink:0; }
  .card-icon svg { width:20px; height:20px; }
  .card h3 { margin:0; font-size:1.08rem; }
  .card p.desc { margin:0; color: var(--muted); font-size:.9rem; line-height:1.55; flex:1; }
  .badges { display:flex; flex-wrap:wrap; gap:6px; }
  .badge { font-size:.72rem; padding:3px 10px; border-radius:999px; background: var(--blue-50); color: var(--blue-700); border:1px solid var(--border); }
  .card a.open { margin-top:auto; text-decoration:none; background: var(--blue-700); color:#fff; text-align:center; padding: 11px; border-radius: 10px; font-size:.9rem; font-weight:600; transition: background .15s ease; }
  .card a.open:hover { background: var(--blue-800); }
  .empty-state { text-align:center; color: var(--muted); padding: 70px 0; }
  footer { text-align:center; color: var(--muted); font-size:.82rem; padding: 20px 24px 48px; }
  @media (max-width:640px) {
    .header { padding: 44px 18px 80px; }
    .header h1 { font-size: 1.6rem; }
    .stats { gap: 26px; }
    .container { margin-top: -50px; }
  }
</style>
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <div class="eyebrow">__EYEBROW__</div>
      <h1>__TITLE__</h1>
      <p class="lede">__SUBTITLE__</p>
      <div class="stats">
        <div><div class="stat-num">__STAT_TOTAL__</div><div class="stat-label">Herramientas</div></div>
        <div><div class="stat-num">__STAT_CATEGORIES__</div><div class="stat-label">Categorías</div></div>
        <div><div class="stat-num">__STAT_PCT__</div><div class="stat-label">__STAT_PCT_LABEL__</div></div>
      </div>
    </div>
  </header>

  <div class="container">
    <div class="searchbar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
      <input id="search" type="text" placeholder="Buscar por nombre, descripción, categoría o etiqueta...">
    </div>

    <div id="categories" class="categories"></div>
    <div id="results-line" class="results-line"></div>
    <div id="grid" class="grid"></div>
    <div id="empty" class="empty-state" style="display:none;">No se encontraron aplicaciones con ese criterio.</div>
  </div>

  <footer>
    Generado automáticamente a partir de las aplicaciones publicadas.<br>
    __CONTACT_NAME__ (<a href="mailto:__CONTACT_EMAIL__">__CONTACT_EMAIL__</a>) · Última actualización: __LAST_UPDATED__
  </footer>

<script id="catalog-data" type="application/json">__CATALOG_JSON__</script>
<script id="category-meta" type="application/json">__CATEGORY_META_JSON__</script>
<script>
  const CATALOG = JSON.parse(document.getElementById('catalog-data').textContent);
  const CATEGORY_META = JSON.parse(document.getElementById('category-meta').textContent);

  let activeCategory = 'all';
  let query = '';

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function matches(app) {
    const inCategory = activeCategory === 'all' || app.categories.includes(activeCategory);
    if (!inCategory) return false;
    if (!query) return true;
    const haystack = [
      app.title, app.description,
      ...app.categories.map(c => (CATEGORY_META[c] || {}).label || c),
      ...app.tags,
    ].join(' ').toLowerCase();
    return haystack.includes(query);
  }

  function renderCategories() {
    const counts = {};
    CATALOG.forEach(app => app.categories.forEach(c => { counts[c] = (counts[c] || 0) + 1; }));
    const slugs = Object.keys(counts).sort((a, b) =>
      ((CATEGORY_META[a] || {}).label || a).localeCompare((CATEGORY_META[b] || {}).label || b)
    );

    const allBtn = `<button class="category-btn ${activeCategory === 'all' ? 'active' : ''}" data-cat="all">
        <i data-lucide="layout-grid"></i> Todas <span class="count">${CATALOG.length}</span>
      </button>`;

    const buttons = slugs.map(slug => {
      const meta = CATEGORY_META[slug] || { label: slug, icon: 'tag' };
      const active = activeCategory === slug ? 'active' : '';
      return `<button class="category-btn ${active}" data-cat="${slug}">
          <i data-lucide="${meta.icon}"></i> ${escapeHtml(meta.label)} <span class="count">${counts[slug]}</span>
        </button>`;
    }).join('');

    document.getElementById('categories').innerHTML = allBtn + buttons;
    document.querySelectorAll('.category-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        activeCategory = btn.dataset.cat;
        renderAll();
      });
    });
  }

  function renderGrid() {
    const filtered = CATALOG.filter(matches);
    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    const resultsLine = document.getElementById('results-line');

    resultsLine.textContent = filtered.length === CATALOG.length
      ? `${CATALOG.length} herramienta${CATALOG.length === 1 ? '' : 's'} disponible${CATALOG.length === 1 ? '' : 's'}`
      : `${filtered.length} resultado${filtered.length === 1 ? '' : 's'}`;

    if (filtered.length === 0) {
      grid.style.display = 'none';
      empty.style.display = 'block';
      return;
    }
    grid.style.display = 'grid';
    empty.style.display = 'none';

    grid.innerHTML = filtered.map(app => {
      const primaryCat = app.categories[0];
      const meta = CATEGORY_META[primaryCat] || { label: primaryCat, icon: 'sparkles' };
      const badges = app.categories.map(c => {
        const m = CATEGORY_META[c] || { label: c };
        return `<span class="badge">${escapeHtml(m.label)}</span>`;
      }).join('');
      return `<div class="card">
          <div class="card-top">
            <div class="card-icon"><i data-lucide="${meta.icon}"></i></div>
            <h3>${escapeHtml(app.title)}</h3>
          </div>
          <p class="desc">${escapeHtml(app.description)}</p>
          <div class="badges">${badges}</div>
          <a class="open" href="${app.url}" target="_blank" rel="noopener">Abrir aplicación</a>
        </div>`;
    }).join('');
  }

  function renderAll() {
    renderCategories();
    renderGrid();
    if (window.lucide) lucide.createIcons();
  }

  document.getElementById('search').addEventListener('input', (e) => {
    query = e.target.value.trim().toLowerCase();
    renderAll();
  });

  renderAll();
</script>
</body>
</html>
"""


_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_es(dt):
    return f"{dt.day} de {_MESES_ES[dt.month - 1]} de {dt.year}"


def render_portal_html(catalog, title, subtitle, eyebrow, contact_name="", contact_email=""):
    """
    catalog: lista de dicts {title, description, categories, tags, client_only, url}
    Devuelve el HTML completo del portal como string.
    """
    total = len(catalog)
    all_categories = sorted({c for app in catalog for c in app["categories"]})
    category_meta = {slug: category_info(slug) for slug in all_categories}

    client_only_count = sum(1 for app in catalog if app.get("client_only"))
    if total > 0 and client_only_count == total:
        stat_pct = "100%"
        stat_pct_label = "En el navegador"
    elif total > 0:
        stat_pct = f"{round(100 * client_only_count / total)}%"
        stat_pct_label = "En el navegador"
    else:
        stat_pct = "0"
        stat_pct_label = "Herramientas sin backend"

    out = PORTAL_TEMPLATE
    out = out.replace("__TITLE__", html.escape(title))
    out = out.replace("__SUBTITLE__", html.escape(subtitle))
    out = out.replace("__EYEBROW__", html.escape(eyebrow))
    out = out.replace("__STAT_TOTAL__", str(total))
    out = out.replace("__STAT_CATEGORIES__", str(len(all_categories)))
    out = out.replace("__STAT_PCT_LABEL__", stat_pct_label)
    out = out.replace("__STAT_PCT__", stat_pct)
    out = out.replace("__CATALOG_JSON__", json.dumps(catalog, ensure_ascii=False))
    out = out.replace("__CATEGORY_META_JSON__", json.dumps(category_meta, ensure_ascii=False))
    out = out.replace("__CONTACT_NAME__", html.escape(contact_name))
    out = out.replace("__CONTACT_EMAIL__", html.escape(contact_email))
    out = out.replace("__LAST_UPDATED__", _fecha_es(datetime.datetime.now(datetime.timezone.utc)))
    return out
