# Desplegar códigos de sala (una vez, 15 min, plan gratis)

Sin esto, el port usa links/IPs/ZeroTier. Con esto, códigos de 6 letras sin IPs.

1. Cuenta gratis en cloudflare.com → Storage & Databases → D1 → Create: `mkport-rooms`.
   Abre su Console, pega `schema.sql`, ejecútalo.
2. Workers & Pages → Create → Worker (Hello World). Edit code: pega `worker.js`, Deploy.
3. Worker → Settings → Bindings → Add → D1: variable `DB`, base `mkport-rooms`. Deploy.
4. Abre la URL del Worker: debe decir `mkport rooms ok`.
5. En cada PC: `config.toml` → `match_url = "https://TU-WORKER.tu-subdominio.workers.dev"`.
6. En el port: Sala online → Crear código / Unirse (código de 6 letras, vale 10 min).

Notas: el Worker solo presenta a los jugadores (IPs/puertos); el juego va directo
entre ellos (hole punching con STUN). Pares tras NAT simétrico estricto no se
alcanzan sin relay TURN (pendiente: `TURN_*` como en Tenkaichi3Decomp).
Límites: 20 salas/hora y 4 abiertas por IP; 30 códigos malos/hora por IP.
