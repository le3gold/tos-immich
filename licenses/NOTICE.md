# Third-party notices and packaging changes

This repository packages the open-source project **Immich** for the TerraMaster
TOS 7 App Center. It is an unofficial community package. The Immich name and
logo belong to the Immich project; this package uses an original icon and does
not claim endorsement by the Immich maintainers.

## Upstream

- Project: Immich
- Repository: <https://github.com/immich-app/immich>
- Version: `v3.3.4`
- Commit: `69e0cb8606137c4f8dc0e7207a672ff8be39f358`
- License: GNU Affero General Public License v3.0 (AGPL-3.0)
- License text: [`LICENSE-AGPL-3.0.txt`](LICENSE-AGPL-3.0.txt)
- Corresponding source: <https://github.com/immich-app/immich/tree/v3.3.4>

The package does not modify Immich server or web source code. It runs the
upstream published container images.

## Container images

| Component | Docker Hub image | Upstream license |
|---|---|---|
| Immich server | `docker.io/altran1502/immich-server:v3.3.4` | AGPL-3.0 |
| Immich machine learning | `docker.io/altran1502/immich-machine-learning:v3.3.4` | AGPL-3.0 |
| PostgreSQL + pgvector | `docker.io/pgvector/pgvector:0.8.7-pg14` | PostgreSQL License |
| Valkey | `docker.io/valkey/valkey:9.1.2` | BSD-3-Clause |
| BusyBox | `docker.io/busybox:1.37.0` | GPL-2.0 |

The `altran1502` images are the Docker Hub copies produced by the upstream
Immich release workflow. TOS only accepts Docker Hub images, so the `ghcr.io`
image names used by the upstream `docker-compose.yml` are replaced with their
Docker Hub equivalents.

## Changes introduced by this package

1. The upstream PostgreSQL image that uses VectorChord is replaced with the
   Docker Hub `pgvector/pgvector:0.8.7-pg14` image. Immich is explicitly set to
   `DB_VECTOR_EXTENSION=pgvector`. This keeps the supported pgvector search path
   while satisfying the TOS Docker Hub image rule.
2. A small `config-init` container creates two files owned by UID 1000:
   `hosts` and `resolv.conf`. TOS's volume ACL prevents a non-root container
   from reading Docker's injected `/etc/hosts` and `/etc/resolv.conf`; the files
   are bind-mounted over those paths so Docker's embedded DNS at `127.0.0.11`
   remains available.
3. The same init container generates a random database password on first start
   and stores it in `network/db-password` with mode `0600`. Immich and PostgreSQL
   read it through `DB_PASSWORD_FILE` and `POSTGRES_PASSWORD_FILE`; no password
   is written into the compose file.
4. Machine-learning downloads use the public `hf-mirror.com` endpoint and
   modelscope.cn for model files. Hugging Face Xet is disabled because the mirror
   returns 401 for Xet file reconstruction. This only affects model downloads;
   user media is never sent to either service.
5. The web port is fixed at 2283, the Immich default. TOS data is placed under
   `/Volume*/DockerAppData/le3gold-immich/`.

## Source and redistribution

The complete TOS packaging files, including this notice, the build script and
the test notes, are published at
<https://github.com/le3gold/tos-immich>. The package is distributed under the
AGPL-3.0 terms that apply to Immich. The original Immich copyright notices and
license text are retained.
