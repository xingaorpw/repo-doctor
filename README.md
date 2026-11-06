# repo-doctor

> 给你的 GitHub 仓库做发布体检：缺什么、值多少分、怎么补。

[![tests](https://github.com/xingaorpw/repo-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/xingaorpw/repo-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

---

## 它解决什么问题

写完代码只是开始。真正决定一个仓库会不会被 star 的，是另外一些东西：

- 有没有 LICENSE——没有的话，别人**在法律上不能复用你的代码**
- 有没有 Topics——GitHub 的搜索和探索页靠它分类，没有就等于不存在
- README 里有没有安装命令、有没有一张截图
- 有没有 CI 徽章——绿色的 `tests passing` 比任何自我介绍都可信

这些事每一件都很小，但**没人会告诉你漏了哪一件**。

`repo-doctor` 就是那个会告诉你的人。

### 真实例子

这是我自己的仓库跑出来的结果：

```
$ python -m repo_doctor xingaorpw/Starscout --no-color
repo-doctor · xingaorpw/Starscout
https://github.com/xingaorpw/Starscout

  ✓  许可证         已声明 MIT                          +10
  ✓  仓库描述       131 字符                             +8
  ✓  Topics         10 个 topic                          +8
  ✓  README         4012 字符                           +12
  ✓  安装说明       有安装/快速开始章节                  +6
  ✗  用法示例       README 里找不到用法示例              +0
       ↳ 加一个 `## 用法`，贴一段真实运行输出
  ✓  截图/图片      含图片/截图                          +4
  ✓  持续集成       有 CI 工作流                        +10
  ✓  测试           1 个测试文件                        +10
  ✓  .gitignore     有 .gitignore                        +4
  ✗  协作规范       没有 CONTRIBUTING                    +0
       ↳ 可选，但有了会显得项目更正规
  ✓  近期活跃       0 天内有提交                        +12
  ✗  发布版本       没有 release                         +0
       ↳ 打个 v0.1.0 tag，别人就知道该用哪个版本

──────────────────────────────────────────────────────────────
  84 / 100   B    通过 10 / 13
  下一步：用法示例（6 分）、发布版本（6 分）、协作规范（4 分）
```

我之前以为这个仓库已经"发布完了"，结果还是漏了三项。

---

## 快速开始

```bash
pip install -r requirements.txt

python -m repo_doctor owner/repo
```

也可以直接传完整地址：

```bash
python -m repo_doctor https://github.com/owner/repo
```

### 可选参数

| 参数 | 作用 |
|---|---|
| `--json` | 输出机器可读的 JSON，方便接 CI 或做看板 |
| `--fix DIR` | 把缺失的 `LICENSE` / `.gitignore` / CI / `CONTRIBUTING.md` 生成到指定目录 |
| `--min-score 80` | 低于该分数时退出码为 1，可以直接卡 CI |
| `--token` | GitHub token，不填则读 `GITHUB_TOKEN` / `GH_TOKEN` |

> 不配 token 也能用，只是 GitHub 匿名限流是 **60 次/小时**，配了是 5000 次/小时。

---

## 检查哪些项

一共 13 项，权重加起来正好 100 分。

| 检查项 | 权重 | 级别 | 说明 |
|---|---:|---|---|
| 许可证 | 10 | error | 没许可证 = 保留所有权利 |
| 仓库描述 | 8 | warn | 少于 20 字符也算不通过 |
| Topics | 8 | warn | 至少 3 个，建议 5–10 个 |
| README | 12 | error | 少于 300 字符也算不通过 |
| 安装说明 | 6 | warn | README 里要有安装/快速开始章节 |
| 用法示例 | 6 | warn | README 里要有用法/示例章节 |
| 截图/图片 | 4 | info | 有图转化率明显更高 |
| 持续集成 | 10 | warn | `.github/workflows/*.yml` |
| 测试 | 10 | warn | 有测试文件即可 |
| .gitignore | 4 | info | 避免提交缓存和密钥 |
| 协作规范 | 4 | info | CONTRIBUTING / CODE_OF_CONDUCT / SECURITY |
| 近期活跃 | 12 | warn | 180 天内有提交 |
| 发布版本 | 6 | info | 至少一个 release |

### 打分规则

**分数 = 通过项的权重之和。** 就这么简单，你可以在脑子里手算出来。

| 分数 | 等级 |
|---|---|
| 90–100 | A |
| 75–89 | B |
| 60–74 | C |
| 40–59 | D |
| 0–39 | F |

刻意做成线性的，因为一个需要解释的分数没有意义。

---

## `--fix` 模式

```bash
python -m repo_doctor owner/repo --fix ./out
```

会把缺失的文件写到 `./out`：

```
已生成 3 个文件到 ./out：
  + LICENSE
  + .gitignore
  + .github/workflows/ci.yml
```

设计上**只生成没有争议的默认值**：

- `LICENSE` 固定 MIT（作者取仓库 owner，年份取当前年）
- `.gitignore` 按仓库主语言选 Python / Node / 通用模板
- CI 工作流按主语言选 Python（3.10–3.13 矩阵）或 Node（18/20/22 矩阵）
- `CONTRIBUTING.md` 是一个通用模板

**不会覆盖已存在的文件**，所以可以放心多次跑。

---

## 在 CI 里用

给仓库自己加一道门禁：

```yaml
- name: repo health
  run: |
    pip install -r requirements.txt
    python -m repo_doctor ${{ github.repository }} --min-score 70
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

分数掉下 70 就红，逼着你补上漏掉的东西。

---

## 已知限制

诚实说明：

- **只看"有没有"，不看"好不好"**。README 里有个 `## 安装` 标题就算通过，不管内容是不是空的。这是刻意的取舍——可判断的规则才能自动化。
- **权重是主观的**。12 分的"近期活跃"对工具类项目可能偏重，对稳定库可能偏轻。想改直接改 `checks.py` 里的数字。
- **匿名限流 60 次/小时**，一个仓库要调 4 次 API，连续查十几个仓库就会撞墙。
- **`--fix` 不碰 topics 和 description**——这两项只能通过 API 写，而写它们需要仓库的 `administration` 权限，超出了只读体检的范围。
- 私有仓库需要 token 且有权限才能查。

## License

[MIT](LICENSE) © 2026 xingaorpw
