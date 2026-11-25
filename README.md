# 合同速查

员工按岗位查阅合同。电商合规专员只能查青禾市集和南湖优选，小区事务专员只能查示范小区，管理员可以看全部知识库、整理报告和审计。

检索链路没有改：Markdown 标题切父块写入 PostgreSQL，子块写入 Milvus，按 `kb_id` 过滤后用 `parent_id` 回取父块。回答里的 `[1]`、`[2]` 必须来自本次材料，页面只列出实际用到的出处。

演示账号写在 `data/accounts.json`，只用于本地演示：

| 账号 | 密码 | 能看的知识库 |
| --- | --- | --- |
| merchant | merchant123 | 青禾市集、南湖优选 |
| steward | steward123 | 示范小区 |
| admin | admin123 | 全部，以及审计 |

## 启动

1. 复制 `.env.example` 为 `.env`，填数据库、Milvus 和 `DEEPSEEK_API_KEY`。没有密钥时，提问会返回「对话模型未配置」，不会空失败。
2. 整理合同并查看脏数据记录：

```bash
python scripts/prepare_documents.py
```

买卖、租赁、物业三份示范文本写入 `data/documents/estate/`，和电商知识库并列，知识库编号是 `estate`。缺页、空章节、重复条款和无法解析的样例文件记在 `data/reports/estate_prepare.json`。无法解析的必需文件会让命令失败，并打印原因。

3. 入库（需要 PostgreSQL 和 Milvus 已经可连接）：

```bash
python scripts/ingest.py
```

4. 启动接口和页面：

```bash
python -m app.main
cd frontend && npm install && npm run dev
```

页面是 http://127.0.0.1:5173/ ，接口是 http://127.0.0.1:8020/ 。

也可以用 Compose 起数据库、Milvus 和接口。第一次构建当前镜像：

```bash
docker compose build app
docker tag contractrag-app:current contractrag-app:previous
docker compose up -d
```

前端仍然在本机用 `npm run dev`。Compose 里的数据库密码只用于这套演示容器。

入库脚本连上数据库后，会给 `system` 记一条入库审计。查询、切换知识库、查看完整章节由页面触发，记谁、何时、哪个 `kb_id`、做了什么、成功还是失败。

## 评测

```bash
python scripts/eval_qa.py
```

评测集在 `data/eval/questions.json`，不少于 20 条。判分是写死的规则：目标章节是否在该 `kb_id` 的父块里、不该出现的句子是否跑进了当前库、引用编号是否落在材料范围内。不调用对话模型，结果不能当成线上准确率或 QPS。

通过和失败写到 `data/reports/eval_latest.json`。管理员打开接口 `GET /api/admin/metrics` 能看到本次进程里的检索次数、平均耗时、空召回次数、模型失败次数，以及最近一次评测通过率。关键失败同时打在应用日志里：召回为空、模型调用失败、引用缺失、审计写入失败。

失败样例也在同一个文件的 `failure_samples` 里，脚本会检查它们确实失败，原因分别是未引用、引用编号不在材料中、错引用、跨库串扰。

## 回滚

应用镜像：

```bash
docker tag contractrag-app:previous contractrag-app:current
docker compose up -d app
```

`previous` 是发布前打的标签。没有上一版镜像时，用 git 把 Compose 和代码退回上一提交再构建：

```bash
git checkout HEAD~1 -- docker-compose.yml Dockerfile app data scripts
docker compose build app
docker compose up -d
```

这只回退应用和编排文件，不删除 PostgreSQL 和 Milvus 的数据卷。要连数据一起回到空库，再执行 `docker compose down -v`。那会清掉已入库的合同和审计，演示前先确认。

## 业务规则

规则在 `data/business_rules.json`，由 `app/rag/policy.py` 在检索之前执行，不交给模型判断。

- 每个知识库有归口部门和使用场景：青禾市集、南湖优选归电商合规部，示范小区归小区事务部。专员仍然只能进自己被授权的库。
- 咨询单号随提问写入审计。单号只允许字母、数字和短横线，不合法会拒绝并记失败。
- 起草合同、代写条款、起诉策略、规避或伪造约定，直接拒答，不检索、不调用模型。
- 已废止的《2019版物业服务收费说明》不入库。提问里点名这份文件时，明确要求改查现行《山东省物业服务合同》。
- 问题先归成费用、违约、权属、履约或其他。命中押金、违约解除、权属登记时，答案下给出关注提示。每条答复都带“只转述已生效原文，不构成法律意见”。

```bash
python scripts/check_policy.py
```

## 权限和例外

- 知识库不存在：404，文档集不存在。
- 账号无权访问该知识库：403，没有该知识库的查询权限。切换和打开原文同样拒绝，并记失败审计。
- 未登录或登录过期：401。
- 模型没配密钥：503，对话模型未配置。
- 模型调用失败：502，对话模型调用失败。日志里有异常。
- 检索为空：回答「无相关约定」，引用列表为空。
- 模型没标出有效的 `[n]`：422，回答未标注有效引用，已拒答。页面不展示无出处的事实。
