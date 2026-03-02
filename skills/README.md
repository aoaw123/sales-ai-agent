# Skills 目录

此目录用于存放你的本地技能文件，与主项目进行集成。

## 当前集成状态

| Skill | 集成方式 | 状态 |
|-------|----------|------|
| docx | python-docx | ✅ 已集成 |
| xlsx | openpyxl | ✅ 已集成 |
| pptx | python-pptx | ✅ 已集成 |
| pdf | pypdf + reportlab | ✅ 已集成 |

## 高级集成

如需使用 Node.js 版本的技能脚本，可将原技能目录复制到此目录：

```
skills/
├── docx/           # 从 1tools/skills/skills/docx 复制
├── xlsx/           # 从 1tools/skills/skills/xlsx 复制
├── pptx/           # 从 1tools/skills/skills/pptx 复制
└── pdf/            # 从 1tools/skills/skills/pdf 复制
```

然后在代码中通过 `subprocess` 调用：

```python
import subprocess

result = subprocess.run(
    ["python", "skills/docx/scripts/accept_changes.py", "input.docx", "output.docx"],
    capture_output=True,
    text=True
)
```
