# Dify Demo4 工作流迁移包

这个仓库保存 `Demo4-最终版` 工作流、Dify 部署模板，以及工作流使用的 PDF 辅助服务。目标是：下载仓库后，配置本地密钥和模型凭据，即可重新部署并导入工作流。

## 目录

- `apps/demo4`：Dify DSL 工作流和导入说明
- `deployment`：当前 Dify `1.17.1` Docker Compose 与非敏感环境变量模板
- `services/pdf-navigation`：监听宿主机 `8084` 的 PDF 渲染/页码服务
- `services/pdf-bridge`：`/inspect` 和 `/extract` PDF 服务
- `docs`：依赖和恢复说明
- `scripts`：本地部署准备脚本

## 尚未包含的运行数据

没有提交 Dify 数据库、上传文件、插件存储、日志、证书私钥或真实 API 密钥。这些内容应通过备份或 Secret Manager 单独保存。

## 仍需人工配置的内容

- Dify 的 `SECRET_KEY`、数据库/Redis 密码
- OpenAI 兼容模型 API 地址和 API Key
- PaddleOCR 插件的凭据或端点
- 知识库文档、用户上传文件和历史数据库（如需要）

PDF 辅助服务和 Gotenberg 的编排已在 `deployment/docker-compose.pdf-services.yaml` 中提供。

