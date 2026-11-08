/**
 * Repassa /api/* ao gateway, que roda na máquina local atrás de um Cloudflare Tunnel.
 * Site e API ficam na mesma origem: o cookie de sessão do Spotify funciona e não há CORS.
 * BACKEND_URL é uma variável do projeto no Cloudflare Pages.
 */
export function onRequest({ request, env }) {
  const url = new URL(request.url);
  const target = new URL(url.pathname.replace(/^\/api/, "") + url.search, env.BACKEND_URL);
  // "manual": o redirect do login precisa chegar ao navegador, não ser seguido aqui.
  return fetch(new Request(target, request), { redirect: "manual" });
}
