# HelpLabel 标注助手

本项目提供一个基于 Tkinter 的图形界面工具 `gui_app.py`，用于高效创建与维护视频标注数据。

## 运行环境

- Python 3.8+（内置 Tkinter，常见 Conda 环境默认可用）


## 目录结构约定

```text
helplabel/
├─ Dataset/
│  └─ {Sport}/
│     └─ {Event}/
│        ├─ 1.mp4
│        ├─ 2.mp4
│        └─ ...
├─ template_json/
│  ├─ Perception_ObjectTracking.json
│  ├─ Perception_Segmentation.json
│  ├─ Understanding_*.json
│  ├─ Reasoning_*.json
│  └─ Special_*.json
└─ gui_app.py
```

## 启动方式

在项目根目录（含 `gui_app.py`）打开 PowerShell，运行：

```powershell
python gui_app.py
```

- 直接运行即可

## 功能概览

- “视频信息”页：
  - 扫描 `Dataset/{Sport}/{Event}` 下的视频；显示每个视频的 JSON 状态（已存在/未创建）。
  - 选中视频后，在右侧填写元数据并保存为同名 JSON（保留既有 annotations）。
- “添加标注”页：
  - 扫描 `Dataset` 下的所有视频 JSON；选择目标 JSON。
  - 选择 L1/L2（来源于 `template_json`），自动生成动态表单。
  - 支持复杂字段（如数组/对象）粘贴 JSON 文本。
  - 窗口时间字段（Q_window_frame / A_window_frame）输入规则：
    - 单组：`10,20` → `[10, 20]`
    - 多组：`10,20; 30,40` → `[[10, 20], [30, 40]]`
    - 也兼容 `10-20` 形式，会等价转换为 `10,20`。
    - **注意：","是英文符号 否则会报错**
  - annotation 字段顺序固定为：
    1) `annotation_id`（自动递增）
    2) `task_L1`、`task_L2`
    3) 其他内容字段

## 常见问题

- L1/L2 下拉为空：
  - 确认 `template_json` 目录存在且文件名为 `L1_L2.json` 格式。
  - 点击“重新加载模板”。
- 模板变更后未生效：
  - 使用“重新加载模板”按钮刷新。
- 无法找到视频：
  - 确保 `Dataset/{Sport}/{Event}` 结构正确且有视频文件（.mp4/.avi/.mov/.mkv）。
- 目前AI解说(Special-Commentary)还没有实现，需要大家手动处理
- 后续版本将会更新可能新增的L1-L2
  