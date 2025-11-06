import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog

# ------------------------------
# 模板加载与工具函数
# ------------------------------
TEMPLATES = {}
L1_L2_MAP = {}


def load_templates(template_dir="template_json"):
    global TEMPLATES, L1_L2_MAP
    TEMPLATES.clear()
    L1_L2_MAP.clear()
    if not os.path.isdir(template_dir):
        messagebox.showerror("错误", f"找不到模板目录: {template_dir}")
        return False
    files = [f for f in os.listdir(template_dir) if f.endswith('.json') and f != 'video-info.json']
    if not files:
        messagebox.showerror("错误", f"模板目录为空: {template_dir}")
        return False
    for filename in files:
        try:
            l1, l2 = filename.replace('.json', '').split('_', 1)
        except ValueError:
            # 非规范文件名，跳过
            continue
        try:
            with open(os.path.join(template_dir, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showwarning("模板加载警告", f"无法解析模板 {filename}: {e}")
            continue
        TEMPLATES[l2] = data
        L1_L2_MAP.setdefault(l1, []).append(l2)
    if not TEMPLATES:
        messagebox.showerror("错误", "未能加载任何模板。")
        return False
    return True


def scan_videos(dataset_root='Dataset'):
    video_ext = ('.mp4', '.avi', '.mov', '.mkv')
    videos = []
    if not os.path.isdir(dataset_root):
        return videos
    for root, _, files in os.walk(dataset_root):
        parts = root.replace('\\', '/').split('/')
        if len(parts) == 3 and parts[0] == dataset_root:
            sport, event = parts[1], parts[2]
            for f in files:
                if f.lower().endswith(video_ext):
                    video_id, _ = os.path.splitext(f)
                    video_path = os.path.join(root, f)
                    json_path = os.path.splitext(video_path)[0] + '.json'
                    videos.append({
                        'sport': sport,
                        'event': event,
                        'video_id': video_id,
                        'video_path': video_path,
                        'json_exists': os.path.exists(json_path)
                    })
    return videos


def scan_video_jsons(dataset_root='Dataset'):
    jsons = []
    if not os.path.isdir(dataset_root):
        return jsons
    for root, _, files in os.walk(dataset_root):
        for f in files:
            if f.lower().endswith('.json'):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    if 'video_metadata' in data:
                        jsons.append(path)
                except Exception:
                    continue
    return jsons


def frames_from_input(raw: str, template_value):
    """解析 Q_window_frame / A_window_frame 为数字区间：
    - 单组："10,20" -> [10, 20]
    - 多组："10,20; 30,40" -> [[10, 20], [30, 40]]
    兼容容错：组内也可写成 "10-20"，将被等价处理为 "10,20"。
    """
    raw = (raw or '').strip()
    if not raw:
        return []
    # 拆组
    groups = [g.strip() for g in raw.split(';') if g.strip()]
    parsed = []
    for g in groups:
        g_norm = g.replace('–', '-').replace('—', '-').replace('−', '-')  # 处理各种短横线
        if '-' in g_norm and ',' not in g_norm:
            g_norm = g_norm.replace('-', ',')
        parts = [p.strip() for p in g_norm.split(',') if p.strip()]
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            # 若包含非数字，忽略该组
            continue
        if len(nums) == 1:
            # 只有一个数字，无法构成区间，忽略该组
            continue
        parsed.append(nums)
    if not parsed:
        return []
    if len(parsed) == 1:
        return parsed[0]
    return parsed


def parse_value_from_text(raw: str, template_value, key: str):
    raw = (raw or '').strip()
    if template_value is None:
        return raw
    # 特殊处理窗口字段
    if key in ("Q_window_frame", "A_window_frame"):
        return frames_from_input(raw, template_value)
    # 直接尝试 JSON 解析（允许复杂结构）
    if raw.startswith('{') or raw.startswith('['):
        try:
            return json.loads(raw)
        except Exception:
            pass
    # 基于模板类型的兜底解析
    if isinstance(template_value, int):
        try:
            return int(raw)
        except ValueError:
            return 0
    if isinstance(template_value, float):
        try:
            return float(raw)
        except ValueError:
            return 0.0
    if isinstance(template_value, list):
        # 逗号分隔为列表
        items = [s.strip() for s in raw.split(',') if s.strip()]
        # 尝试根据元素类型转型
        if template_value and isinstance(template_value[0], int):
            out = []
            for s in items:
                try:
                    out.append(int(s))
                except ValueError:
                    out.append(s)
            return out
        if template_value and isinstance(template_value[0], float):
            out = []
            for s in items:
                try:
                    out.append(float(s))
                except ValueError:
                    out.append(s)
            return out
        return items
    # 默认返回字符串
    return raw


# ------------------------------
# GUI 应用
# ------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HelpLabel 标注助手")
        self.geometry("1080x720")
        self.dataset_root = 'Dataset'

        # 顶部工具栏
        topbar = ttk.Frame(self)
        topbar.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(topbar, text="Dataset 根目录:").pack(side=tk.LEFT)
        self.dataset_var = tk.StringVar(value=self.dataset_root)
        self.dataset_entry = ttk.Entry(topbar, textvariable=self.dataset_var, width=50)
        self.dataset_entry.pack(side=tk.LEFT, padx=6)
        ttk.Button(topbar, text="选择...", command=self.choose_dataset).pack(side=tk.LEFT)
        ttk.Button(topbar, text="重新加载模板", command=self.reload_templates).pack(side=tk.LEFT, padx=10)

        # 选项卡
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Tab1: 视频信息
        self.tab_info = ttk.Frame(notebook)
        notebook.add(self.tab_info, text="视频信息")
        self.build_tab_info(self.tab_info)

        # Tab2: 添加标注
        self.tab_anno = ttk.Frame(notebook)
        notebook.add(self.tab_anno, text="添加标注")
        self.build_tab_anno(self.tab_anno)

        # 初始加载
        if load_templates():
            # 让 L1 下拉在启动时就可用
            try:
                self.l1_combo['values'] = list(L1_L2_MAP.keys())
            except Exception:
                pass
        self.refresh_videos()
        self.refresh_jsons()

    # ---------- 顶部操作 ----------
    def choose_dataset(self):
        path = filedialog.askdirectory(title="选择 Dataset 根目录")
        if path:
            self.dataset_var.set(path)
            self.refresh_videos()
            self.refresh_jsons()

    def reload_templates(self):
        if load_templates():
            messagebox.showinfo("成功", "模板已重新加载。")
            # 刷新 L1 选项
            self.l1_combo['values'] = list(L1_L2_MAP.keys())
            self.l1_combo.set('')
            self.l2_combo.set('')
            for w in self.form_container.winfo_children():
                w.destroy()

    # ---------- 视频信息 Tab ----------
    def build_tab_info(self, parent):
        # 左侧：视频列表
        left = ttk.Frame(parent)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        actions = ttk.Frame(left)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="扫描视频", command=self.refresh_videos).pack(side=tk.LEFT)

        cols = ("sport", "event", "video_id", "status", "path")
        self.video_tree = ttk.Treeview(left, columns=cols, show='headings', height=18)
        for c, txt, width in [
            ("sport", "运动", 120),
            ("event", "赛事", 180),
            ("video_id", "视频ID", 80),
            ("status", "JSON状态", 100),
            ("path", "视频路径", 400)
        ]:
            self.video_tree.heading(c, text=txt)
            self.video_tree.column(c, width=width, anchor=tk.W)
        self.video_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.video_tree.bind('<<TreeviewSelect>>', self.on_video_select)

        # 右侧：表单
        right = ttk.Frame(parent)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.info_vars = {
            'sport': tk.StringVar(),
            'event': tk.StringVar(),
            'video_id': tk.StringVar(),
            'info': tk.StringVar(),
            'duration_sec': tk.StringVar(),
            'fps': tk.StringVar(),
            'total_frames': tk.StringVar(),
            'width': tk.StringVar(),
            'height': tk.StringVar(),
        }

        def add_row(label, var):
            row = ttk.Frame(right)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=14, anchor=tk.E).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var, width=28).pack(side=tk.LEFT, padx=6)

        ttk.Label(right, text="创建 / 更新视频信息", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(4, 6))
        add_row("运动(sport)", self.info_vars['sport'])
        add_row("赛事(event)", self.info_vars['event'])
        add_row("视频ID", self.info_vars['video_id'])
        add_row("视频简介", self.info_vars['info'])
        add_row("时长(sec)", self.info_vars['duration_sec'])
        add_row("帧率(fps)", self.info_vars['fps'])
        add_row("总帧数", self.info_vars['total_frames'])
        add_row("宽度(width)", self.info_vars['width'])
        add_row("高度(height)", self.info_vars['height'])

        ttk.Button(right, text="保存 JSON", command=self.save_video_json).pack(anchor=tk.W, pady=8)

        self.selected_video = None

    def refresh_videos(self):
        for i in self.video_tree.get_children():
            self.video_tree.delete(i)
        videos = scan_videos(self.dataset_var.get())
        for v in videos:
            status = '已存在' if v['json_exists'] else '未创建'
            self.video_tree.insert('', tk.END, values=(v['sport'], v['event'], v['video_id'], status, v['video_path']))

    def on_video_select(self, event):
        sel = self.video_tree.selection()
        if not sel:
            return
        vals = self.video_tree.item(sel[0], 'values')
        sport, event, vid, status, path = vals
        self.selected_video = {
            'sport': sport,
            'event': event,
            'video_id': vid,
            'video_path': path,
        }
        # 预填
        self.info_vars['sport'].set(sport)
        self.info_vars['event'].set(event)
        self.info_vars['video_id'].set(vid)
        # 若已有 json，加载预填
        json_path = os.path.splitext(path)[0] + '.json'
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                vm = data.get('video_metadata', {})
                self.info_vars['info'].set(data.get('info', ''))
                self.info_vars['duration_sec'].set(str(vm.get('duration_sec', '')))
                self.info_vars['fps'].set(str(vm.get('fps', '')))
                self.info_vars['total_frames'].set(str(vm.get('total_frames', '')))
                res = vm.get('resolution', ["", ""]) or ["", ""]
                if isinstance(res, list) and len(res) >= 2:
                    self.info_vars['width'].set(str(res[0]))
                    self.info_vars['height'].set(str(res[1]))
            except Exception:
                pass
        else:
            for k in ['info', 'duration_sec', 'fps', 'total_frames', 'width', 'height']:
                self.info_vars[k].set('')

    def save_video_json(self):
        if not self.selected_video:
            messagebox.showwarning("提示", "请先在列表中选择一个视频。")
            return
        sport = self.info_vars['sport'].get().strip()
        event = self.info_vars['event'].get().strip()
        video_id = self.info_vars['video_id'].get().strip()
        info = self.info_vars['info'].get().strip()
        try:
            duration_sec = float(self.info_vars['duration_sec'].get().strip())
            fps = int(self.info_vars['fps'].get().strip())
            total_frames = int(self.info_vars['total_frames'].get().strip())
            width = int(self.info_vars['width'].get().strip())
            height = int(self.info_vars['height'].get().strip())
        except ValueError:
            messagebox.showerror("错误", "请检查元数据字段是否为正确的数字。")
            return
        # 输出路径
        json_path = os.path.splitext(self.selected_video['video_path'])[0] + '.json'
        if os.path.exists(json_path):
            if not messagebox.askyesno("确认", f"文件已存在，是否覆盖？\n{json_path}"):
                return
        data = {
            "sport": sport,
            "event": event,
            "video_id": video_id,
            "info": info,
            "video_metadata": {
                "duration_sec": duration_sec,
                "fps": fps,
                "total_frames": total_frames,
                "resolution": [width, height]
            },
            "annotations": []
        }
        # 若已有 JSON，尽量保留已有 annotations
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    old = json.load(f)
                if isinstance(old.get('annotations'), list):
                    data['annotations'] = old['annotations']
            except Exception:
                pass
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("成功", f"已保存: {json_path}")
            self.refresh_videos()
            self.refresh_jsons()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    # ---------- 添加标注 Tab ----------
    def build_tab_anno(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)

        ttk.Button(top, text="扫描 JSON", command=self.refresh_jsons).pack(side=tk.LEFT, padx=4, pady=4)
        self.json_combo_var = tk.StringVar()
        self.json_combo = ttk.Combobox(top, textvariable=self.json_combo_var, width=100, state='readonly')
        self.json_combo.pack(side=tk.LEFT, padx=6, pady=4)

        # 选择 L1/L2
        sel = ttk.Frame(parent)
        sel.pack(fill=tk.X, padx=4, pady=6)
        ttk.Label(sel, text="L1:").pack(side=tk.LEFT)
        self.l1_combo = ttk.Combobox(sel, values=list(L1_L2_MAP.keys()), state='readonly', width=28)
        self.l1_combo.pack(side=tk.LEFT, padx=6)
        ttk.Label(sel, text="L2:").pack(side=tk.LEFT)
        self.l2_combo = ttk.Combobox(sel, state='readonly', width=40)
        self.l2_combo.pack(side=tk.LEFT, padx=6)
        self.l1_combo.bind('<<ComboboxSelected>>', self.on_l1_selected)
        self.l2_combo.bind('<<ComboboxSelected>>', self.on_l2_selected)

        # 动态表单容器
        self.form_container = ttk.Frame(parent)
        self.form_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 底部操作
        bottom = ttk.Frame(parent)
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="添加标注", command=self.add_annotation).pack(side=tk.LEFT, padx=6, pady=6)

        # 保存当前表单控件引用
        self.current_template = None
        self.field_widgets = {}

    def refresh_jsons(self):
        jsons = scan_video_jsons(self.dataset_var.get())
        self.json_combo['values'] = jsons
        if jsons:
            self.json_combo.current(0)

    def on_l1_selected(self, event=None):
        l1 = self.l1_combo.get()
        l2s = L1_L2_MAP.get(l1, [])
        self.l2_combo['values'] = l2s
        self.l2_combo.set('')
        for w in self.form_container.winfo_children():
            w.destroy()
        self.current_template = None
        self.field_widgets.clear()

    def on_l2_selected(self, event=None):
        l2 = self.l2_combo.get()
        template = TEMPLATES.get(l2)
        self.current_template = template
        for w in self.form_container.winfo_children():
            w.destroy()
        self.field_widgets.clear()
        if not template:
            return
        # 根据模板构建表单
        row = 0
        for key, default in template.items():
            if key in ("task_L1", "task_L2", "annotation_id"):
                continue
            ttk.Label(self.form_container, text=key).grid(row=row, column=0, sticky=tk.E, padx=4, pady=4)
            # 选择控件：长文本/JSON 用 Text，其他用 Entry
            widget = None
            if isinstance(default, (list, dict)) or key in ("Q_window_frame", "A_window_frame"):
                widget = tk.Text(self.form_container, width=60, height=3)
            else:
                widget = ttk.Entry(self.form_container, width=60)
                if isinstance(default, (int, float)):
                    widget.insert(0, str(default))
            widget.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
            self.field_widgets[key] = (widget, default)
            # 在文本框下方增加提示标签（不写入内容本身）
            if key in ("Q_window_frame", "A_window_frame"):
                hint = ttk.Label(self.form_container, text="示例: 10,20   或   10,20; 30,40", foreground="#666")
                hint.grid(row=row+1, column=1, sticky=tk.W, padx=4, pady=(0,6))
                row += 2
            else:
                row += 1

    def add_annotation(self):
        target_json = self.json_combo.get().strip()
        if not target_json:
            messagebox.showwarning("提示", "请先选择一个目标视频 JSON 文件。")
            return
        if not self.current_template:
            messagebox.showwarning("提示", "请先选择 L1 和 L2。")
            return
        # 读取 JSON
        try:
            with open(target_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"无法读取 JSON: {e}")
            return
        # 构造 annotation
        # 先收集内容字段
        content_fields = {}
        for key, (widget, default) in self.field_widgets.items():
            if isinstance(widget, tk.Text):
                raw = widget.get('1.0', tk.END).strip()
            else:
                raw = widget.get().strip()
            content_fields[key] = parse_value_from_text(raw, default, key)
        # 构造有序 annotation：annotation_id -> task -> 其他字段
        ann = {}
        # 分配 annotation_id
        existing = data.get('annotations') or []
        max_id = 0
        for a in existing:
            try:
                max_id = max(max_id, int(a.get('annotation_id', 0)))
            except Exception:
                continue
        ann['annotation_id'] = str(max_id + 1)
        # 任务信息
        ann['task_L1'] = self.l1_combo.get()
        ann['task_L2'] = self.l2_combo.get()
        # 其他字段按当前表单顺序写入
        for k, v in content_fields.items():
            ann[k] = v
        existing.append(ann)
        data['annotations'] = existing
        # 保存
        try:
            with open(target_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("成功", f"已添加标注，写回: {target_json}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


if __name__ == '__main__':
    app = App()
    app.mainloop()
