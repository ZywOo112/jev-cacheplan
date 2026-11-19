# 手动发布到自己的GitHub个人账号

本地发行目录已完成整理；准备机器没有安装GitHub CLI，因此尚未创建远程仓库。不要上传整个课程目录或任何模型/环境。首次公开应使用全新历史。

## 已有本地Git提交的发行目录

在自己的终端安装[GitHub CLI](https://cli.github.com/)，然后登录：

```bash
gh auth login
gh auth status
gh api user --jq '{login: .login, type: .type}'
```

确认输出是你本人的个人账号（type=User），不是其他账号或组织。不要把Token/密码发给任何助手。检查同名仓库：

```bash
gh repo view YOUR_LOGIN/jev-cacheplan
```

只有明确返回仓库不存在（404）、且不存在权限/网络错误时，才在**本公开仓库根目录**执行：

```bash
gh repo create YOUR_LOGIN/jev-cacheplan --public --source=. --remote=origin --push
gh repo view YOUR_LOGIN/jev-cacheplan --json url,isPrivate,defaultBranchRef
```

如果同名仓库存在，先检查其中内容，停止自动创建步骤；不得强推、覆盖或删除。不要使用`git push --force`。推送后在网页检查main、Public、README图像与关键源码。

## Windows下载源码ZIP后

ZIP只包含已审计、已提交的公开文件，不含.git。解压到独立目录，在该目录使用Git与gh：

```powershell
git init -b main
git add .
git commit -m "Release JEV-CachePlan"
gh auth login
gh api user --jq '{login: .login, type: .type}'
gh repo view YOUR_LOGIN/jev-cacheplan
# 只在明确确认仓库不存在后运行
gh repo create YOUR_LOGIN/jev-cacheplan --public --source=. --remote=origin --push
```

Windows可用`winget install --id GitHub.cli`安装gh，再开启新终端。若Git尚未设置作者身份，自行在这个公开目录配置愿意公开的名称和GitHub noreply邮箱；不要盲用私人邮箱。上传GitHub网页也应只选择解压后的公开文件，不包括模型、运行时日志、凭据或环境。

本发行版CPU测试与历史GPU测量范围见README；公开目录整理没有重新运行GPU推理，性能结果不是通用保证。
