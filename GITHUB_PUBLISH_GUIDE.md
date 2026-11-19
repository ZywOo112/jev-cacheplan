# 维护已公开的 JEV-CachePlan

维护目标为 [ZywOo112/jev-cacheplan](https://github.com/ZywOo112/jev-cacheplan) 的 `main`。先检查本地工作区和远端，再通过快进获取最新历史。

```bash
git status --short --branch
git remote -v
git fetch origin main
git merge --ff-only origin/main
```

审查拟提交的差异、相对链接、测试及第三方归属。公开内容限定在代码、文档、图像和经审查的实验汇总；模型权重、原始运行目录、环境和凭据应留在本地。使用具有仓库写权限的账号，在完成验证后提交并正常推送。

```bash
git diff --cached --check
git commit -m "Update JEV-CachePlan documentation"
git push origin main
```

远端有新的提交时，先获取并核对它们，再处理本地分支与远端的差异。最终在 GitHub 检查 `main` 的提交、README 图片和文档链接。 [展示与课程汇报的对应关系](docs/PRESENTATION_ALIGNMENT.md)
