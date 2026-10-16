/* MK Port matchmaking — códigos de sala de 6 letras (estilo Tenkaichi3Decomp).
 * Solo presenta a los dos jugadores (intercambia direcciones); ningún dato del
 * juego pasa por aquí. Despliegue: Cloudflare Worker + D1 (ver schema.sql,
 * binding variable `DB`). Versión de red exigida: NET_VERSION = 2.
 * Límites: 20 salas/hora y 4 abiertas por IP; 30 códigos malos/hora por IP.
 */
const NET_VERSION = 2;
const ROOM_TTL = 600;
const CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; // sin 0/O/1/I/L
const ROOM_HOURLY = 20, ROOM_OPEN_MAX = 4, BADCODE_HOURLY = 30;

function code6(rand) {
  const b = new Uint8Array(6);
  rand.getRandomValues(b);
  return [...b].map((x) => CODE_ALPHABET[x % CODE_ALPHABET.length]).join("");
}
function secret(rand) {
  const b = new Uint8Array(16);
  rand.getRandomValues(b);
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}
const now = () => Math.floor(Date.now() / 1000);
const json = (o, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });
const err = (e, status = 400) => json({ error: e }, status);

async function prune(db) {
  await db.prepare("DELETE FROM rooms WHERE made < ?1").bind(now() - ROOM_TTL).run();
  await db.prepare("DELETE FROM used WHERE ts < ?1").bind(now() - 3600).run();
}
async function countUsed(db, ip, what) {
  const r = await db.prepare("SELECT COUNT(*) c FROM used WHERE ip=?1 AND what=?2 AND ts>?3")
    .bind(ip, what, now() - 3600).first();
  return r ? r.c : 0;
}
async function markUsed(db, ip, what) {
  await db.prepare("INSERT INTO used(ip,what,ts) VALUES(?1,?2,?3)").bind(ip, what, now()).run();
}
function cleanAddrs(a) {
  if (!Array.isArray(a)) return [];
  const out = [];
  for (const x of a.slice(0, 8)) {
    if (typeof x === "string" && /^[0-9a-fA-F.:]{3,50}:\d{1,5}$/.test(x) && !out.includes(x)) out.push(x);
  }
  return out;
}

export default {
  async fetch(request, env) {
    if (request.method === "GET")
      return new Response("mkport rooms ok\n", { headers: { "content-type": "text/plain" } });
    const url = new URL(request.url);
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    let body = {};
    try { body = await request.json(); } catch { return err("json"); }
    const db = env.DB;
    await prune(db);

    if (url.pathname === "/v1/host") {
      if (body.v !== NET_VERSION) return err("version");
      if ((await countUsed(db, ip, "room")) >= ROOM_HOURLY) return err("limit");
      const open = await db.prepare("SELECT COUNT(*) c FROM rooms WHERE ip=?1").bind(ip).first();
      if (open && open.c >= ROOM_OPEN_MAX) return err("open");
      const addrs = cleanAddrs(body.addrs);
      if (!addrs.length) return err("addrs");
      const c = code6(crypto), hk = secret(crypto);
      await db.prepare(
        "INSERT INTO rooms(code,made,version,ip,host_key,host_name,host_addrs) VALUES(?1,?2,?3,?4,?5,?6,?7)")
        .bind(c, now(), NET_VERSION, ip, hk, String(body.name || "?").slice(0, 16), JSON.stringify(addrs)).run();
      await markUsed(db, ip, "room");
      return json({ code: c, key: hk, you: ip });
    }

    if (url.pathname === "/v1/join") {
      if (body.v !== NET_VERSION) return err("version");
      const code = String(body.code || "").toUpperCase().trim();
      const room = await db.prepare("SELECT * FROM rooms WHERE code=?1").bind(code).first();
      if (!room) {
        if ((await countUsed(db, ip, "badcode")) >= BADCODE_HOURLY) return err("limit");
        await markUsed(db, ip, "badcode");
        return err("no-room", 404);
      }
      if (room.join_key) return err("full", 409);
      const addrs = cleanAddrs(body.addrs);
      if (!addrs.length) return err("addrs");
      const jk = secret(crypto);
      await db.prepare("UPDATE rooms SET join_key=?1, join_name=?2, join_addrs=?3 WHERE code=?4")
        .bind(jk, String(body.name || "?").slice(0, 16), JSON.stringify(addrs), code).run();
      return json({
        key: jk, you: ip,
        peer: { name: room.host_name, addrs: JSON.parse(room.host_addrs) },
      });
    }

    if (url.pathname === "/v1/poll") {
      const room = await db.prepare("SELECT * FROM rooms WHERE code=?1").bind(String(body.code || "").toUpperCase()).first();
      if (!room) return err("no-room", 404);
      if (body.key === room.host_key && room.join_addrs)
        return json({ peer: { name: room.join_name, addrs: JSON.parse(room.join_addrs) } });
      if (body.key === room.join_key)
        return json({ peer: { name: room.host_name, addrs: JSON.parse(room.host_addrs) }, mission: "lobby" });
      return json({ peer: null });
    }

    if (url.pathname === "/v1/leave") {
      await db.prepare("DELETE FROM rooms WHERE code=?1 AND (host_key=?2 OR join_key=?2)")
        .bind(String(body.code || "").toUpperCase(), String(body.key || "")).run();
      return json({ ok: true });
    }
    return err("path", 404);
  },
};
