# Dify 部署模板

这里的 `docker-compose.yaml` 来自当前本地 Dify 部署，使用的核心镜像版本是 `1.17.1`。

首次准备：

```powershell
..\scripts\prepare-deployment.ps1
```

然后编辑 `.env`。`*.env.example` 只提供变量模板，不代表已经配置好模型、密码或外部服务。

不要把 `deployment/.env` 或 `deployment/volumes/` 提交到 Git。

