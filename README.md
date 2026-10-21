# Immich for TOS 7

将 [Immich](https://github.com/immich-app/immich) 封装为 TerraMaster TOS 7
应用中心的 Docker 应用。Immich 是一个自托管的照片和视频库，提供时间线、
相册、上传、搜索、人脸识别和 OCR。

> 这是 **非官方社区封装**，与 Immich 项目维护者没有隶属或背书关系。应用 ID
> 为 `le3gold-immich`，版本与上游 `v3.3.4` 对齐。

## 版本和来源

| 项目 | 值 |
|---|---|
| 应用 ID | `le3gold-immich` |
| 应用版本 | `3.3.4` |
| 上游版本 | `v3.3.4` |
| 上游提交 | `69e0cb8606137c4f8dc0e7207a672ff8be39f358` |
| 支持平台 | `x86_64` |
| Web 端口 | `2283` |
| 许可证 | AGPL-3.0 |

完整的第三方说明、镜像来源和封装修改记录见
[`licenses/NOTICE.md`](licenses/NOTICE.md)，隐私政策见
[`PRIVACY.md`](PRIVACY.md)。

## 仓库结构

```
tos-immich/
├── config.ini                    # TOS 应用元数据
├── docker-compose.yml            # 发布用 compose（不含测试端口）
├── docker-compose.test.yml       # 真机测试用，端口 12283，不进入发布包
├── le3gold-immich.lang           # 14 种语言的应用中心文案
├── images/icons/le3gold-immich.svg
├── licenses/
│   ├── LICENSE-AGPL-3.0.txt
│   └── NOTICE.md
├── docs/
│   ├── PACKAGING-NOTES.md        # TOS ACL、测试证据和排障记录
│   └── SUBMISSION.md             # 应用中心提审材料
└── tools/
    ├── build_package.py          # 生成确定性的 le3gold-immich.tar.gz
    ├── verify_package.py         # 独立校验发布包
    └── requirements.txt          # verify_package.py 的依赖
```

发布包 `le3gold-immich.tar.gz` 的根目录**只能有四个文件**：

```
config.ini
le3gold-immich.lang
le3gold-immich.svg
docker-compose.yml
```

不包含 `docker-compose.test.yml`、README、许可证或任何二进制文件。

## 构建和校验

需要 Python 3.8+。构建脚本只用标准库；独立校验脚本需要 PyYAML：

```bash
python -m pip install -r tools/requirements.txt
python tools/build_package.py
python tools/verify_package.py build/le3gold-immich.tar.gz
```

构建会写入：

```text
build/le3gold-immich.tar.gz
build/le3gold-immich.tar.gz.sha256
```

压缩包使用固定的 gzip 时间和 tar 元数据；相同输入重复构建得到相同字节，
便于发布 Release 时校验 SHA-256。构建前会检查 JSON、14 语言节点、compose
规则、图标、LF 行尾和明文密码。

## 运行要求

- TOS 7.0 或更高版本，`x86_64`。
- 已从应用中心安装并启用 **DockerEngine**。
- 主机端口 `2283` 未被占用。如果 NAS 上已有手工安装的 Immich，请先改端口或
  停止旧实例，否则应用中心安装会失败。
- 首次安装需要从 Docker Hub 拉取约 2 GB 镜像。中国大陆网络可能需要为
  DockerEngine 配置代理或镜像站。
- 首次使用人脸识别、OCR 或智能搜索时，需要访问 `hf-mirror.com` 和
  `modelscope.cn` 下载约 1.7 GB 模型。模型缓存在应用数据目录中，后续启动
  不会重复下载。

## 安装后的数据

`docker-compose.yml` 里的数据目录全部使用相对路径（`./library`、
`./postgres`、`./redis`、`./ml-cache`、`./network`）。按 TOS 7 开发指南，
平台会把它们解析到 `<应用数据根>/le3gold-immich/`，即用户安装时选择的卷：

```text
/Volume<N>/DockerAppData/le3gold-immich/
├── library/       # 原始照片和视频
├── postgres/      # PostgreSQL 数据
├── redis/         # Valkey 数据
├── ml-cache/      # 机器学习模型
└── network/
    ├── hosts
    ├── resolv.conf
    └── db-password  # 0600，随机生成，请勿删除
```

`config-init` 容器只负责生成后三个网络/凭据文件。它和 Immich、ML、PostgreSQL、
Valkey 一样以 UID/GID `1000:1000` 运行，不使用 privileged，不使用 host 网络。

数据库密码不在 compose 中明文出现。Immich 通过 `DB_PASSWORD_FILE` 读取，
PostgreSQL 通过 `POSTGRES_PASSWORD_FILE` 读取。升级、备份或迁移时请把
`db-password` 和 `postgres/` 一起保留。

## 导入 NAS 上已有的照片（外部库，不复制文件）

Immich 的**外部库**可以原地索引已有文件夹，照片不会被移动或复制。TOS 的
Docker 应用规范不允许把共享文件夹写进发布包（平台会把绝对路径重写到
`DockerAppData`），所以需要在安装后手工给 `immich-server` 增加一个只读挂载。

以共享文件夹 `/Volume1/Photos` 为例：

```bash
cd /Volume1/@apps/DockerEngine/application/le3gold-immich
sudo sed -e 's|\./|/Volume1/DockerAppData/le3gold-immich/|g' \
  -e 's|DockerAppData/le3gold-immich/library:/data|DockerAppData/le3gold-immich/library:/data\n      - /Volume1/Photos:/mnt/photos:ro|' \
  docker-compose.yml > /tmp/immich-resolved.yml
sudo docker compose -p le3gold-immich -f /tmp/immich-resolved.yml up -d immich-server
```

然后在 Immich 管理后台进入 **外部库 → 创建外部库**，路径填 `/mnt/photos`，
保存后执行扫描。缩略图和索引写入 Immich 自己的数据库与 `library/`，原文件夹
保持只读。

注意事项：

- 容器以 UID 1000 运行，源文件夹必须对 UID 1000 可读。
- 路径必须加 `:ro`，不要让 Immich 写回原文件夹。
- 不要指向 `DockerAppData/le3gold-immich/library`，也不要与上传目录重叠。
- 重装应用会重建容器，需要重新加这个挂载；照片和数据库不受影响。

## 卸载和升级

TOS 的 Docker 应用**不支持应用中心内的原地升级**。需要更换版本时：

1. 在应用中心卸载，卸载时选择保留数据。
2. 安装新版本的 `le3gold-immich.tar.gz`。
3. 新版本继续使用原来的 `DockerAppData/le3gold-immich`。

卸载时如果选择同时删除数据，平台会删除整个
`/Volume<N>/DockerAppData/le3gold-immich`，包括照片和数据库。该操作不可恢复，
请先通过 TOS 备份或快照保护数据。

## 真机验收记录

2026-10-21 在两台 x86_64 TNAS 上完成测试：TOS `7.0.1341`（功能测试，
`docker-compose.test.yml`，端口 `12283`，未触碰该机原有 Immich 实例）和
TOS `7.1.0213`（发布 compose，端口 `2283`，Docker Hub 直连）。

验收结果：

| 项目 | 结果 |
|---|---|
| 5 个容器（init/server/ML/redis/postgres） | 全部 `healthy` |
| `GET /api/server/ping` | `{"res":"pong"}` |
| `GET /api/server/version` | `3.3.4` |
| Web 首页 | HTTP 200 |
| 管理员初始化与登录 | 成功 |
| 上传 JPEG | API 返回 `created` |
| 缩略图 | HTTP 200，`image/webp` |
| 时间线 | 返回 1 个资产桶 |
| PostgreSQL 扩展 | `vector 0.8.7`、`cube`、`earthdistance`、`pg_trgm`、`unaccent`、`uuid-ossp` |
| 机器学习模型下载 | 缓存约 1.7 GB |
| 智能搜索 | `POST /api/search/smart` HTTP 200，返回刚上传的图片 |
| 非 root 容器访问 `/etc/hosts` | 通过应用自有文件覆盖后正常 |
| 数据库密码 | `network/db-password`，`0600`，compose 无明文 |

在 TOS `7.1.0213` 上，发布 compose 的五个容器全部 `healthy`，
`/api/server/ping`、`/api/server/version` 和首页均正常。应用中心能识别
该包并正确显示图标、开发者、类别和版本。

已知平台问题：该固件的应用中心「手动安装」只解析 `.deb`，上传
`.tar.gz` 会报 `does not contain any .deb files`，官方 Docker 模板同样失败。
因此「打开」按钮的桌面入口无法通过正式安装流程验证；直接访问
`http://<NAS>:2283` 正常。详见
[`docs/PACKAGING-NOTES.md`](docs/PACKAGING-NOTES.md)。

测试细节和 TOS ACL 的根因见
[`docs/PACKAGING-NOTES.md`](docs/PACKAGING-NOTES.md)。

## 许可证和商标

Immich 采用 AGPL-3.0。本仓库保留上游许可证文本、版本、提交和对应源码链接；
不添加限制性 EULA。发布包中的镜像由上游项目发布到 Docker Hub。应用图标是
为本封装新绘制的图形，不使用 Immich 官方 logo，也不表示官方背书。

如发现打包或运行问题，请在
<https://github.com/le3gold/tos-immich/issues> 提交。

## 为什么可以上架（AGPL-3.0）

AGPL-3.0 允许再分发和商业分发，前提是遵守许可证。本封装：

- 不修改 Immich 源码，直接使用上游发布到 Docker Hub 的镜像，并固定版本 tag。
- 在仓库中保留 AGPL-3.0 全文、上游版权声明、版本、提交号和源码地址。
- 以公开仓库形式提供本封装自己的 compose、配置和构建脚本；Immich 对应源码
  可直接从上游仓库获取。
- 不使用 Immich 官方 logo，并明确标注为非官方社区封装，避免暗示官方背书。

发布包本身只包含元数据、语言文件、图标和 compose，不包含 Immich 二进制；
镜像由用户安装时从 Docker Hub 拉取。若后续修改 Immich 源码，必须同时公开
修改后的源码。
