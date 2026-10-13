# Demo4-最终版

导入文件：`workflow.dsl.yml`

## 已确认的依赖

- Dify DSL 版本：`0.7.0`
- Dify 镜像版本：`1.17.1`（来自当前 `docker-compose.yaml`）
- Marketplace 插件：
  - `langgenius/paddleocr:0.3.1`
  - `langgenius/openai:1.0.7`
- 模型：`gpt-5.6-sol`、`gpt-6-sol`
- 本地 PDF 渲染服务：`services/pdf-navigation`，默认监听宿主机 `8084`
- 外部 HTTP 服务：
  - `PDF_INSPECT_URL` → `/inspect`
  - 工作流中的 `/extract` 地址 → `/extract`

## 重要说明

DSL 不包含模型凭据、插件凭据、知识库文档和外部 HTTP 服务源码。导入后需要重新配置这些内容。

