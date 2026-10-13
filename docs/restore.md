# 恢复步骤

1. 安装 Docker Desktop，并准备与当前版本兼容的 Docker Compose。
2. 进入 `deployment`，运行 `..\scripts\prepare-deployment.ps1`，生成本地 `.env` 文件。
3. 编辑 `deployment/.env`，填写真实密钥和服务地址。
4. 在 `deployment` 目录以固定项目名启动 Dify 和全部辅助服务：

   ```powershell
   Set-Location deployment
   docker compose -p dify -f docker-compose.yaml -f docker-compose.pdf-services.yaml up -d --build
   ```

5. 检查辅助服务：

   ```powershell
   Invoke-RestMethod http://localhost:8082/health
   Invoke-RestMethod http://localhost:8083/health
   Invoke-RestMethod http://localhost:8084/health
   Invoke-RestMethod http://localhost:3000/health
   ```

6. 在 Dify 中安装 `PaddleOCR` 和 `OpenAI` 插件，配置模型凭据。
7. 导入 `apps/demo4/workflow.dsl.yml`。
8. 用小型 PDF 测试，再进行完整工作流验收。

## 限制

仓库可以重建工作流定义和辅助服务，但不能重建第三方模型账户、模型 API Key、Dify 用户账户、历史数据库、知识库文档或已上传文件。它们必须在新环境中重新配置或单独恢复备份。

