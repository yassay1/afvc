# 工程约定

## 编码

全仓库 UTF-8。编辑器用 `.editorconfig`；Git 用 `.gitattributes`。Python 读写文件必须带 `encoding="utf-8"`。

提交前建议：

```bash
python -m compileall -q backend frontend tests scripts
python scripts/check_text_integrity.py
pytest
```

## 质量门（当前）

| 工具 | 状态 |
|------|------|
| pytest | 主测试。默认跳过 `llm` / `slow` marker |
| `scripts/check_text_integrity.py` | 乱码 / 私用区字符 |
| compileall | 语法 |
| Ruff | `pyproject.toml` 中仅启用未使用符号检查；不强制全量 format |
| CI | `.github/workflows/ci.yml` |

未引入 mypy/pyright：类型注解不完整，本轮不强行 type-check。

## 配置入口

唯一应用配置：`backend/core/config.py`（读 `.env`，模板为 `.env.example`）。

工单默认读 Postgres（`DATABASE_URL` / `AFVC_DATA_BACKEND=sql`）。紧急回退 `AFVC_DATA_BACKEND=file`。

写操作审批状态机在 `backend/domain/pending_action.py`，事务与行锁在 `infrastructure/pending_action_repo.py`，用例编排在 `application/approvals.py`。API 只做 HTTP 映射。

不要再增加第二套 settings 模块。
