const REPO_RAW = "https://raw.githubusercontent.com/jafreck/jafreck/main/assets";

const STYLES = ["matrix", "mdr"];

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const theme = url.searchParams.get("theme") === "light" ? "light" : "dark";
    const style = STYLES[Math.floor(Math.random() * STYLES.length)];
    const svgUrl = `${REPO_RAW}/${style}-stats-${theme}.svg`;

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
