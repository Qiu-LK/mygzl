# Demo4 依赖清单

## 可迁移内容

仓库已包含：

- 工作流 DSL
- 当前 Dify Docker Compose 文件
- Dify 的非敏感 `*.env.example` 模板
- Compose 引用的代理、Nginx、证书脚本和向量库初始化配置
- 自定义 PDF 导航/渲染服务源码
- PDF 预检和原生文字提取服务源码（PyMuPDF）
- Gotenberg、预检/提取、页码目录服务的 Compose 编排

## 需要重新配置的内容

1. Dify 的 `deployment/.env`，尤其是 `SECRET_KEY`、数据库密码、Redis 密码。
2. OpenAI 插件凭据和模型访问权限。
3. PaddleOCR 插件安装和凭据（如当前环境需要）。
4. 知识库及其文档。
5. OpenAI 和 PaddleOCR 插件需要在 Dify 控制台重新安装/配置。

PDF 辅助服务已在 `deployment/docker-compose.pdf-services.yaml` 中提供；它们从仓库源码构建，Gotenberg 使用官方镜像 `gotenberg/gotenberg:8`。

