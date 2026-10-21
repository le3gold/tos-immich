# 提审材料 / App Center submission

## 基本信息

| 项目 | 值 |
|---|---|
| 应用名称 | Immich 相册 |
| 应用 ID | `le3gold-immich` |
| 版本 | `3.3.4` |
| 应用类型 | Docker |
| 平台 | `x86_64` |
| 最低 TOS | `TOS7.0` |
| Web 端口 | `2283` |
| 分类 | `Phtography_Video`（7.1 实际枚举，显示为“摄影录像”） |
| 依赖 | `DockerEngine` |
| 开发者 / 发布人 | `lee3gold` |
| 源码仓库 | <https://github.com/le3gold/tos-immich> |
| 发布包 | <https://github.com/le3gold/tos-immich/releases/download/v3.3.4/le3gold-immich.tar.gz> |
| SHA-256 | `ddc38ef82b48ccd316f018ab62445970987fb553c53eba5a1272f1f7c07b85af` |
| 隐私政策 | <https://github.com/le3gold/tos-immich/blob/main/PRIVACY.md> |
| 支持地址 | <https://github.com/le3gold/tos-immich/issues> |

## 应用说明

Immich 是自托管的照片和视频库，提供时间线、相册、上传、缩略图、搜索、
人脸识别和 OCR。所有照片、视频、账号和数据库都保存在用户自己的 TNAS 上。

本应用是非官方社区封装，与 Immich 项目维护者没有隶属或背书关系。应用图标
为本封装新绘制的图形，不使用 Immich 官方 logo。

## 发布包内容

`le3gold-immich.tar.gz` 根目录只有规范要求的四个文件：

```text
config.ini
le3gold-immich.lang
le3gold-immich.svg
docker-compose.yml
```

不包含可执行文件、安装脚本、共享文件夹声明或二进制。构建脚本和独立校验
脚本位于仓库 `tools/`，重复构建得到相同的 SHA-256。

## 镜像

全部来自 Docker Hub，固定版本 tag，不使用 `:latest`：

| 用途 | 镜像 |
|---|---|
| Immich Server | `docker.io/altran1502/immich-server:v3.3.4` |
| Immich Machine Learning | `docker.io/altran1502/immich-machine-learning:v3.3.4` |
| PostgreSQL + pgvector | `docker.io/pgvector/pgvector:0.8.7-pg14` |
| Valkey | `docker.io/valkey/valkey:9.1.2` |
| 初始化助手 | `docker.io/busybox:1.37.0` |

`altran1502` 是 Immich 上游作者发布 Docker Hub 镜像的命名空间，镜像由上游
release 流程生成；上游文档中的 `ghcr.io/immich-app/*` 名称因 TOS 只接受
Docker Hub 而替换为对应的 Docker Hub 名称。

## 规则对照

| 要求 | 实现 |
|---|---|
| Compose 3.8+ | 使用 Compose Spec，`docker compose config -q` 通过 |
| 仅 Docker Hub 镜像、固定 tag | 见上表，全部固定版本 |
| 非 root | 五个服务均 `user: "1000:1000"` |
| 禁止 privileged / host 网络 | 均未使用，全部设置 `no-new-privileges:true` |
| 每个服务有 healthcheck | 五个服务均有 |
| 数据持久化 | 相对路径 `./library`、`./postgres`、`./redis`、`./ml-cache`、`./network`，由平台解析到 `/Volume<N>/DockerAppData/le3gold-immich/` |
| 不写 `/Volume*` | compose 中没有任何 `/Volume` 路径 |
| 不使用共享文件夹 | 未声明 `share_folders`，未调用 `ter_share_add` |
| 时区 | 每个服务 `TZ=Asia/Shanghai` |
| 无明文凭据 | 首次启动随机生成 40 字符数据库密码，`0600`，通过 `*_PASSWORD_FILE` 读取 |
| x-app-meta | `port: 2283`，`protocol: http` |

## 测试结果

测试机 1：TOS `7.0.1341`，Docker `29.4.0`，Compose `v5.1.2`，x86_64。
使用隔离的测试 compose（端口 `12283`，目录带 `-test`）完成完整功能测试：

- 五个容器全部 `healthy`；ping、版本、首页正常。
- 管理员初始化、登录、上传 JPEG、缩略图、时间线、智能搜索全部通过。
- PostgreSQL 使用 pgvector，扩展和向量检索正常；模型缓存约 1.7 GB。

测试机 2：TOS `7.1.0213`，Docker `29.4.0`，x86_64，Docker Hub 直连。
使用**发布 compose**（端口 `2283`）：

- 五个镜像全部从 Docker Hub 拉取成功。
- 五个容器全部 `healthy`；`/api/server/ping` 返回 `{"res":"pong"}`，
  版本为 `3.3.4`，首页 HTTP 200。
- 应用中心识别为已安装、已启用，详情页图标、开发者、类别、版本正确，
  `check_access` 返回 `true`。

详细记录见 [`PACKAGING-NOTES.md`](PACKAGING-NOTES.md)。

## 需要平台确认的问题

1. **TOS 7.1.0213 手动安装只接受 `.deb`**：上传本包报
   `Parse package error ... does not contain any .deb files`，使用官方 Docker
   模板同样失败。请通过正式 Docker 应用安装流程验证，或确认该固件的上传
   通道是否需要单独开关。
2. **桌面入口未注册**：手工把包装入
   `/Volume1/@apps/DockerEngine/application/le3gold-immich` 后，应用中心详情页
   的“打开”按钮不会弹窗，因为 `/v2/desktop/apps` 不包含该应用。该现象与
   绕过安装器手工部署一致，请以正式安装流程的结果为准。
3. **分类枚举拼写**：7.1 使用 `Phtography_Video`，官方 TerraPhotos 也使用
   该拼写，本包已按实际枚举填写。

## 许可证

Immich 采用 AGPL-3.0。本包不修改 Immich 源码，直接运行上游发布到 Docker Hub
的镜像；仓库保留 AGPL-3.0 全文、上游版权声明、版本、提交号和源码地址：

- 上游源码：<https://github.com/immich-app/immich/tree/v3.3.4>
- 提交：`69e0cb8606137c4f8dc0e7207a672ff8be39f358`
- 许可证文本：`licenses/LICENSE-AGPL-3.0.txt`
- 第三方说明：`licenses/NOTICE.md`

本封装自身的 compose、配置、语言文件、图标和构建脚本以公开仓库形式提供。
如后续修改 Immich 源码，将同时公开修改后的源码。
