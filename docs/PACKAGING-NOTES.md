# Immich for TOS 7 - packaging and test notes

## Test targets

- Functional test: `10.18.8.214`, TOS `7.0.1341`
- Packaging and App Center test: `10.18.8.181`, TOS `7.1.0213`
- Kernel: `6.12.63+`
- Docker Engine: `29.4.0`, API `1.54`
- Docker Compose: `v5.1.2`
- Architecture: `x86_64`
- Test project: `/Volume1/docker/immich-test`
- Test data: `/Volume1/DockerAppData/le3gold-immich-test`
- Test web port: `12283`

The 214 test instance is isolated from the pre-existing manual Immich v3.1.0
instance on port 2283 and `/Volume1/Photos`. The 181 host runs the production
compose on port 2283, because that host is the App Center test target.

## TOS ACL blocker and the non-root fix

With `user: "1000:1000"`, the upstream Immich server repeatedly exited with:

```text
Error: getaddrinfo EAI_AGAIN database
```

The files inside the container looked normal:

```text
-rw-r--r-- 1 root root 172 /etc/hosts
-rw-r--r-- 1 root root 353 /etc/resolv.conf
```

but UID 1000 could not read either file:

```text
$ docker run --rm -u 1000:1000 --entrypoint sh immich-server:v3.3.4 -c 'cat /etc/hosts'
cat: /etc/hosts: Permission denied
```

The same command as root succeeded. `getfacl` showed ordinary `0644` mode bits;
the denial comes from TOS's `tmacl` layer on `/Volume1`, not from Docker's file
mode or DNS configuration. This is the same platform behavior documented for
the CAD package: tmacl is deny-by-default and does not fall back to POSIX mode
bits.

Bind mounts of application data worked only after the host directory was owned
by UID 1000. The platform's Docker installer performs this ownership step for
mounted paths during installation. For manual testing the directories were
created and chowned explicitly.

The package therefore does not rely on reading Docker's injected files. A
`config-init` service running as UID 1000 writes:

```text
/Volume*/DockerAppData/le3gold-immich/network/hosts
/Volume*/DockerAppData/le3gold-immich/network/resolv.conf
```

The host file contains `localhost`; the resolver contains only Docker's embedded
DNS:

```text
nameserver 127.0.0.11
options ndots:0
```

All application containers bind-mount those files over `/etc/hosts` and
`/etc/resolv.conf`. `127.0.0.11` resolves both Compose service names and
external domains through the Docker daemon's configured upstream DNS. This was
verified inside a UID 1000 container:

```text
database         -> 172.21.0.x
huggingface.co   -> resolves through Docker DNS
www.modelscope.cn -> resolves through Docker DNS
```

An earlier attempt used fixed IPs on a dedicated `172.31.254.0/24` network. It
made internal connections work but could not resolve external model hosts, and
it introduced a needless subnet-conflict risk. It was discarded.

## Database credential

The original draft had `DB_PASSWORD=...` and `POSTGRES_PASSWORD=...` in the
compose file, which violates the TOS review rule against hardcoded credentials.
`config-init` now generates a random 40-character password on first start:

```sh
head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40
```

It is written to `network/db-password` with mode `0600` and mounted read-only
into Immich and PostgreSQL:

```yaml
- DB_PASSWORD_FILE=/run/secrets/db-password
- POSTGRES_PASSWORD_FILE=/run/secrets/db-password
```

The file is generated only if it does not already contain data, so restarting
the containers does not rotate the password. It must be kept together with the
PostgreSQL data directory. A fresh test database was used to verify that both
the `_FILE` mechanisms work.

## Images

TOS accepts Docker Hub images only. The upstream `ghcr.io` names are replaced
with the Docker Hub copies produced by the upstream release workflow:

| Role | Image |
|---|---|
| Server | `docker.io/altran1502/immich-server:v3.3.4` |
| Machine learning | `docker.io/altran1502/immich-machine-learning:v3.3.4` |
| Database | `docker.io/pgvector/pgvector:0.8.7-pg14` |
| Queue/cache | `docker.io/valkey/valkey:9.1.2` |
| Init helper | `docker.io/busybox:1.37.0` |

The test NAS could not reach Docker Hub directly. Test images were pulled
through a mirror and retagged locally; the published compose file still refers
to the Docker Hub names above. The production NAS must be able to pull those
names, or DockerEngine must be configured with a registry mirror/proxy.

`pgvector` replaces the upstream VectorChord-based PostgreSQL image. Immich is
configured with `DB_VECTOR_EXTENSION=pgvector`. After upload, the test database
contained:

```text
vector 0.8.7
cube 1.5
earthdistance 1.1
pg_trgm 1.6
unaccent 1.1
uuid-ossp 1.1
```

Smart search returned the uploaded asset, so the pgvector search path is
working.

## Machine-learning downloads

The first attempt failed because UID 1000 could not read `/etc/resolv.conf`;
the ML container returned HTTP 500 for every request. After the readable
resolver was mounted, model downloads started.

On the test network, `huggingface.co` timed out, `www.modelscope.cn` and
`hf-mirror.com` were reachable. The ML container is therefore configured with:

```text
HF_ENDPOINT=https://hf-mirror.com
HF_HUB_DISABLE_XET=1
HF_HUB_DISABLE_TELEMETRY=1
```

Without `HF_HUB_DISABLE_XET=1`, the mirror returned:

```text
RuntimeError: Task error: File reconstruction error:
CAS Client Error: HTTP status client error (401 Unauthorized)
```

After disabling Xet and clearing the incomplete CLIP/face cache, the ML cache
grew to about 1.7 GB and `POST /api/search/smart` returned HTTP 200 with the
uploaded asset. OCR models were downloaded from `www.modelscope.cn`; CLIP and
face models were downloaded through the Hugging Face mirror.

## Startup ordering

The first version started the server before the ML healthcheck was ready,
which produced:

```text
Unable to run job handler: Machine learning repository not been setup
```

The server now declares `depends_on` on `immich-machine-learning` with
`condition: service_healthy`, in addition to PostgreSQL and Redis. After a
forced server recreate, the log showed the ML repository healthy before
`Immich Server is listening`, and a new upload completed without ML errors.

## End-to-end checks

Commands used on the NAS (test port 12283):

```bash
curl -fsS http://127.0.0.1:12283/api/server/ping
curl -fsS http://127.0.0.1:12283/api/server/version
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:12283/
```

Results:

```text
{"res":"pong"}
{"major":3,"minor":3,"patch":4,"prerelease":null}
200
```

Admin sign-up and login returned `201 Created`. A 640x480 JPEG was uploaded
through `POST /api/assets`; the response was `{"status":"created"}`. After the
thumbnail job ran, `/api/assets/<id>/thumbnail?size=thumbnail` returned
`image/webp`, and `/api/timeline/buckets?size=MONTH` returned one bucket.

The smart search test used a third 900x650 JPEG and returned it for the query
`white rectangle` with HTTP 200.

## TOS 7.1.0213 / 181 verification

Docker Hub became reachable from `10.18.8.181` after a proxy was configured on
that NAS. All five pinned images were pulled directly from Docker Hub:

```text
docker.io/altran1502/immich-server:v3.3.4
docker.io/altran1502/immich-machine-learning:v3.3.4
docker.io/pgvector/pgvector:0.8.7-pg14
docker.io/valkey/valkey:9.1.2
docker.io/busybox:1.37.0
```

The release compose was run with the platform's documented host-path
resolution applied (`./library` -> `/Volume1/DockerAppData/le3gold-immich/library`,
and the same for the other mounts). Result:

```text
le3gold-immich            Up (healthy)   # server, container_name == app id
le3gold-immich-init       Up (healthy)
le3gold-immich-ml         Up (healthy)
le3gold-immich-postgres   Up (healthy)
le3gold-immich-redis      Up (healthy)

GET /api/server/ping      {"res":"pong"}
GET /api/server/version   3.3.4
GET /                     200 text/html
network/db-password       40 bytes, mode 0600
```

The first start after recreating the server container took about four and a
half minutes: the server healthcheck has a 180-second start period and the
machine-learning container has to initialise before it. This is expected and
is why the App Center may show the app as starting for several minutes.

### App Center registration on 181

The package was unpacked into
`/Volume1/@apps/DockerEngine/application/le3gold-immich` and the App Center
listed it as installed and enabled. The detail page showed the right icon,
developer, publisher, category and version, and
`GET /v2/app/check_access/le3gold-immich` returned `data:true`.

The "open" button in the App Center detail page did not open a browser tab. The
front end first calls `check_access` and then looks the app up in
`GET /v2/desktop/apps`; that response does not contain `le3gold-immich`, so the
handler returns without calling `window.open`. Posting the app to
`/v2/desktop/shortcuts` returned `item not found`. This is consistent with the
manual copy having bypassed the platform installer, which normally registers
the desktop entry. It is not reproducible through the supported install path
on 7.1.0213 because that path is currently broken (next section). Direct access
to `http://<nas>:2283` works, and a properly installed package is expected to
be registered by the installer.

### TOS 7.1.0213 manual install defect

Uploading `le3gold-immich.tar.gz` through App Center -> manual install fails
with:

```text
Parse package error. error=archive "/Volume1/@cache/upload/le3gold-immich.tar.gz" does not contain any .deb files
```

The same error occurs with the official Docker application template from the
TOS 7 development guide, so the upload channel on this firmware build only
accepts `.deb` archives. The Docker package format itself is correct: it
contains exactly the four files the guide specifies, and the compose file runs
as documented above. This needs to be raised with TerraMaster during review;
the manual-install channel is not evidence against the package.

### Category enum and icon path

The 7.1 App Center uses the misspelled enum `Phtography_Video` (one `o`). The
official TerraPhotos package uses the same spelling. `config.ini` uses that
value so the app appears under "摄影录像" instead of "其它".

For a manual copy the icon must also be placed at
`/usr/www/images/icons/<appid>.svg`; the normal installer does this. The
release archive only contains `<appid>.svg` at its root, as required by the
package specification.

## Known limitations

- The package is pinned to Immich 3.3.4. Docker applications cannot be upgraded
  in place through the TOS App Center; uninstall and reinstall while retaining
  application data.
- Model downloads require external network access. The mirror is public but is
  not operated by this package. A disconnected NAS can still use the core
  timeline and upload features, but ML features will fail until models are
  cached.
- The host port 2283 is the Immich default. A NAS that already runs a manual
  Immich instance on 2283 must change or stop that instance before installing
  this app.
- The App Center "open" button could not be validated end to end because the
  only supported install channel on 7.1.0213 rejects `.tar.gz` packages. See
  the section above.
