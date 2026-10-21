# Immich for TOS - 隐私政策 / Privacy Policy

适用于 TerraMaster TOS 应用 **Immich 相册**（应用 ID `le3gold-immich`），由
**lee3gold** 基于开源项目 Immich 3.3.4 封装。最后更新：2026-10-21。

## 摘要

这是一个本地自托管应用。照片、视频、相册、账号和数据库都保存在你的 TNAS
上，不会上传到本封装项目或任何 Immich 云服务。应用不使用广告、分析 SDK 或
用户行为追踪。

本应用是**非官方封装**，与 Immich 项目维护者没有隶属或背书关系。

## 应用处理的数据

| 数据 | 保存位置 | 用途 |
|---|---|---|
| 原始照片、视频及其缩略图 | `/Volume*/DockerAppData/le3gold-immich/library` | 时间线、相册、下载和分享 |
| 数据库和索引 | `/Volume*/DockerAppData/le3gold-immich/postgres` | 账号、元数据、搜索索引、任务状态 |
| Redis 数据 | `/Volume*/DockerAppData/le3gold-immich/redis` | 后台任务队列和缓存 |
| 机器学习模型缓存 | `/Volume*/DockerAppData/le3gold-immich/ml-cache` | 人脸识别、OCR、智能搜索 |
| 随机数据库密码 | `/Volume*/DockerAppData/le3gold-immich/network/db-password` | 仅用于本机容器之间连接数据库，权限为 `0600` |

这些目录位于 NAS 本地。管理员可以通过 TOS 的备份、快照或共享文件夹功能自行
备份。封装项目不接收这些数据。

## 网络请求

应用运行时可能产生以下网络请求：

- **Docker 镜像拉取**：安装或重装时，DockerEngine 从 Docker Hub 拉取 Immich、
  pgvector、Valkey 和 BusyBox 镜像。请求由 DockerEngine 发出，不包含照片内容。
- **机器学习模型下载**：首次使用人脸识别、OCR 或智能搜索时，机器学习容器从
  `hf-mirror.com` 和 `modelscope.cn` 下载模型文件。请求包含模型名称和常规
  HTTP 信息，例如 IP 地址和 User-Agent；不会上传你的照片、视频或账号数据。
- **版本检查**：Immich 默认会向 `version.immich.cloud` 查询稳定版版本号，
  请求只带发布渠道参数。管理员可以在 Immich 管理设置中关闭该项。
- **管理员启用的可选功能**：如果管理员自行配置 SMTP、OAuth、反向地理编码、
  外部存储或其他第三方集成，相关数据会按照该功能的配置发送给对应服务。本
  封装默认不启用这些集成。

机器学习模型下载使用的镜像和版本检查地址由本封装写入 compose 文件。它们是
公开网络服务，不由本封装项目运营。

## 账号与权限

- Immich 的账号体系完全在本机数据库中，密码由 Immich 使用哈希方式保存。
- Docker 容器以 UID/GID `1000:1000` 运行，不使用 `privileged`，也不使用
  host 网络。
- 应用监听 NAS 的 2283 端口。请不要把该端口直接暴露到公网；如需远程访问，
  请使用 TOS 的 VPN、反向代理和 HTTPS 配置，并自行评估访问控制。
- `config.ini` 的 `all_user_display` 为 `false`。管理员需要在 TOS 权限设置
  中明确授权普通用户，普通用户才能看到并使用该应用。

## 数据保留与删除

- 从应用中心卸载时选择**保留数据**：`/Volume*/DockerAppData/le3gold-immich`
  保留，重新安装后可以继续使用。
- 卸载时选择**同时删除数据**：平台会删除上述应用目录，包括照片、数据库、
  模型缓存和随机密码文件。此操作不可恢复，请先自行备份。
- Immich 应用内删除照片、清空回收站或删除账号，只会修改本机数据库和文件，
  不会通知本封装项目。

## 安全说明

数据库密码由 `config-init` 容器在首次启动时随机生成，写入权限为 `0600` 的
文件，不写入 compose 明文。不要删除或修改
`/Volume*/DockerAppData/le3gold-immich/network/db-password`，否则已有数据库
可能无法再连接。需要重置密码时，应先备份数据库并按 Immich 官方文档操作。

## 变更与联系

本政策的变更会先提交到公开仓库
<https://github.com/le3gold/tos-immich>，再随新版本发布。隐私问题、数据删除
问题或安全报告请通过该仓库的 Issues 联系。

## 上游与许可证

Immich 由 Immich 项目维护者开发，采用 AGPL-3.0 许可证。对应源码版本为
`v3.3.4`，提交
`69e0cb8606137c4f8dc0e7207a672ff8be39f358`，源码地址
<https://github.com/immich-app/immich/tree/v3.3.4>。本封装保留上游许可证和
版权声明，详见仓库中的 `licenses/` 目录。
