const REPO_RAW = "https://raw.githubusercontent.com/jafreck/jafreck/main/assets";

const STYLES = {
  "matrix": "matrix-stats",
  "mdr": "mdr-stats",
  "terminal-v1": "terminal-v1",
  "terminal-v2": "terminal-v2",
  "terminal-v3": "terminal-v3",
  "invaders": "invaders-v2",
};

const STYLE_KEYS = Object.keys(STYLES);

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const theme = url.searchParams.get("theme") === "light" ? "light" : "dark";
    const key = STYLE_KEYS[Math.floor(Math.random() * STYLE_KEYS.length)];
    const prefix = STYLES[key];
    const svgUrl = `${REPO_RAW}/${prefix}-${theme}.svg`;

    const resp = await fetch(svgUrl);
    if (!resp.ok) {
      return new Response("SVG not found", { status: 404 });
    }

    const svg = await resp.text();
    return new Response(svg, {
      headers: {
        "Content-Type": "image/svg+xml",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
      },
    });
  },
};

