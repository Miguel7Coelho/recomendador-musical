/**
 * Repassa /api/* ao gateway, que roda na VM atrás de um Cloudflare Tunnel.
 * Site e API ficam na mesma origem: o cookie de sessão do Spotify funciona e não há CORS.
 * BACKEND_URL e PROXY_SECRET são variáveis do projeto no Cloudflare Pages. O segredo prova ao
 * gateway que o pedido veio daqui, e só então ele confia no IP do visitante informado.
 */
export function onRequest({ request, env }) {
  const url = new URL(request.url);
  const target = new URL(url.pathname.replace(/^\/api/, "") + url.search, env.BACKEND_URL);
  const headers = new Headers(request.headers);
  headers.set("X-Proxy-Secret", env.PROXY_SECRET ?? "");
  headers.set("X-Client-IP", request.headers.get("CF-Connecting-IP") ?? "");
  // "manual": o redirect do login precisa chegar ao navegador, não ser seguido aqui.
  return fetch(new Request(target, new Request(request, { headers })), { redirect: "manual" });
}
