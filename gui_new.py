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
    # 特殊处理 answer：允许单字符串或多条（分号/换行分隔）或 JSON 数组
    if key == 'answer':
        if raw.startswith('['):
            try:
                val = json.loads(raw)
                return val
            except Exception:
                pass
        # 分号或换行视为多项
        if ';' in raw or '\n' in raw:
            parts = []
            for seg in raw.replace('\r', '').split('\n'):
                parts.extend([p.strip() for p in seg.split(';') if p.strip()])
            return parts
        # 若模板本为列表，则按列表解析（逗号分隔）
        if isinstance(template_value, list):
            items = [s.strip() for s in raw.split(',') if s.strip()]
            return items
        # 默认单字符串
        return raw
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
        notebook.add(self.tab_anno, text="标注管理") ### 修改 ###
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

    # ---------- S( tab_info ) ... (代码与原版一致，此处省略) ----------
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
            fps = float(self.info_vars['fps'].get().strip())
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
    # ---------- E( tab_info ) ----------


    # ---------- 标注管理 Tab (原 tab_anno) ----------
    def build_tab_anno(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)

        ttk.Button(top, text="扫描 JSON", command=self.refresh_jsons).pack(side=tk.LEFT, padx=4, pady=4)
        self.json_combo_var = tk.StringVar()
        self.json_combo = ttk.Combobox(top, textvariable=self.json_combo_var, width=100, state='readonly')
        self.json_combo.pack(side=tk.LEFT, padx=6, pady=4)
        self.json_combo.bind('<<ComboboxSelected>>', self.on_json_selected) ### 新增 ###

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

        # ### 新增：历史标注列表 ###
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.X, padx=4, pady=(4, 8))
        
        ttk.Label(list_frame, text="历史标注 (点击加载):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

        cols = ("id", "l1", "l2", "preview")
        self.anno_tree = ttk.Treeview(list_frame, columns=cols, show='headings', height=7)
        for c, txt, width in [
            ("id", "ID", 40),
            ("l1", "L1", 150),
            ("l2", "L2", 180),
            ("preview", "内容预览", 500)
        ]:
            self.anno_tree.heading(c, text=txt)
            self.anno_tree.column(c, width=width, anchor=tk.W)
        
        # 滚动条
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.anno_tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.anno_tree.configure(yscrollcommand=vsb.set)
        
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.anno_tree.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.anno_tree.configure(xscrollcommand=hsb.set)

        self.anno_tree.pack(fill=tk.X, expand=True)
        self.anno_tree.bind('<<TreeviewSelect>>', self.on_annotation_select)
        # ### 历史标注列表 结束 ###

        # 动态表单容器
        self.form_container = ttk.Frame(parent)
        self.form_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 底部操作
        bottom = ttk.Frame(parent)
        bottom.pack(fill=tk.X)
        ### 修改：按钮 ###
        ttk.Button(bottom, text="保存标注", command=self.save_annotation).pack(side=tk.LEFT, padx=6, pady=6)
        ttk.Button(bottom, text="新建 / 清空表单", command=self.clear_annotation_form).pack(side=tk.LEFT, padx=6, pady=6)
        
        # 保存当前表单控件引用
        self.current_template = None
        self.field_widgets = {}
        
        self.current_annotations_map = {} ### 新增：用于存储ID到完整标注的映射
        self.selected_annotation_id = None ### 新增：用于跟踪当前是否在修改

    ### 新增：在选择JSON时触发 ###
    def on_json_selected(self, event=None):
        self.populate_annotation_list()
        self.clear_annotation_form() # 选择新文件时，清空表单

    ### 新增：加载标注列表到 Treeview ###
    def populate_annotation_list(self):
        target_json = self.json_combo.get().strip()
        # 清空
        for i in self.anno_tree.get_children():
            self.anno_tree.delete(i)
        self.current_annotations_map.clear()
        
        if not target_json or not os.path.exists(target_json):
            return
        
        try:
            with open(target_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return # 读取失败则不显示
        
        annotations = data.get('annotations', [])
        for ann in annotations:
            ann_id = str(ann.get('annotation_id', 'N/A'))
            l1 = ann.get('task_L1', '')
            l2 = ann.get('task_L2', '')
            
            # 生成预览
            preview = ann.get('question', ann.get('answer', ''))
            if isinstance(preview, list):
                preview = "; ".join(preview)
            if not preview:
                preview = ann.get('relationship', '...') # 备用预览
            
            self.anno_tree.insert('', tk.END, values=(ann_id, l1, l2, str(preview)[:100]))
            self.current_annotations_map[ann_id] = ann # 存储完整数据

    ### 新增：格式化值以便填回 Text/Entry ###
    def format_value_for_text(self, value, key):
        if value is None:
            return ""
        
        if key in ("Q_window_frame", "A_window_frame"):
            if isinstance(value, list) and value:
                if isinstance(value[0], list): # 多组 [[10, 20], [30, 40]]
                    return "; ".join([f"{v[0]},{v[1]}" for v in value if isinstance(v, list) and len(v) >= 2])
                elif len(value) >= 2: # 单组 [10, 20]
                    return f"{value[0]},{value[1]}"
            return "" # 空或格式不对
            
        if key == 'answer':
            if isinstance(value, list):
                return ";\n".join(str(s) for s in value)
            if isinstance(value, (dict)):
                return json.dumps(value, ensure_ascii=False, indent=2)

        if isinstance(value, (list, dict)):
            # 默认的列表/字典使用json
            return json.dumps(value, ensure_ascii=False, indent=2)

        return str(value)

    ### 新增：将历史标注数据填入表单 ###
    def populate_form_widgets(self, data_dict):
        for key, (widget, default) in self.field_widgets.items():
            if key not in data_dict:
                continue
            
            value = data_dict[key]
            
            # --- 处理 ObjectsSpatialRelationships 的 bounding_box ---
            if key == 'bounding_box' and isinstance(widget, tuple) and widget[0] == 'composite':
                sub = widget[1]
                if not isinstance(value, list) or len(value) < 2:
                    continue # 数据格式不对
                
                # 清空
                sub['label1'].delete(0, tk.END)
                sub['label2'].delete(0, tk.END)
                for e in sub['box1'] + sub['box2']: e.delete(0, tk.END)
                
                # 填对象1
                val1 = value[0]
                if isinstance(val1, dict):
                    sub['label1'].insert(0, val1.get('label', ''))
                    if isinstance(val1.get('box'), list) and len(val1['box']) == 4:
                        for i, e in enumerate(sub['box1']):
                            e.insert(0, str(val1['box'][i]))
                # 填对象2
                val2 = value[1]
                if isinstance(val2, dict):
                    sub['label2'].insert(0, val2.get('label', ''))
                    if isinstance(val2.get('box'), list) and len(val2['box']) == 4:
                        for i, e in enumerate(sub['box2']):
                            e.insert(0, str(val2['box'][i]))
                continue
            # --- 复合控件处理结束 ---

            formatted_value = self.format_value_for_text(value, key)
            
            if isinstance(widget, tk.Text):
                widget.delete('1.0', tk.END)
                widget.insert('1.0', formatted_value)
            elif isinstance(widget, ttk.Entry):
                widget.delete(0, tk.END)
                widget.insert(0, formatted_value)

    ### 新增：清空/重置表单，准备新建 ###
    def clear_annotation_form(self):
        self.selected_annotation_id = None
        self.l1_combo.set('')
        self.l2_combo.set('')
        # 取消 Treeview 中的选中状态
        for i in self.anno_tree.selection():
            self.anno_tree.selection_remove(i)
        
        self.on_l1_selected() # on_l1 会清空 l2 和 form

    ### 新增：点击 Treeview 中的历史标注 ###
    def on_annotation_select(self, event=None):
        sel = self.anno_tree.selection()
        if not sel:
            return
        
        selected_item = self.anno_tree.item(sel[0])
        ann_id = selected_item['values'][0]
        
        ann_data = self.current_annotations_map.get(str(ann_id))
        if not ann_data:
            messagebox.showwarning("加载失败", f"未能在映射中找到 ID: {ann_id}")
            return
            
        self.selected_annotation_id = str(ann_id) # 标记当前正在修改
        
        # 1. 设置 L1
        self.l1_combo.set(ann_data['task_L1'])
        # 2. 触发 L1 更新 (这会更新 L2 下拉列表)
        self.on_l1_selected()
        # 3. 设置 L2
        self.l2_combo.set(ann_data['task_L2'])
        # 4. 触发 L2 更新 (这会根据模板 *重建* 表单)
        self.on_l2_selected()
        # 5. 填充数据 (此时表单已创建)
        self.populate_form_widgets(ann_data)

    def refresh_jsons(self):
        jsons = scan_video_jsons(self.dataset_var.get())
        self.json_combo['values'] = jsons
        if jsons:
            self.json_combo.current(0)
            self.on_json_selected() ### 新增：刷新JSON后自动加载标注列表
        else:
            self.populate_annotation_list() ### 新增：清空列表
            self.clear_annotation_form() ### 新增：清空表单


    def on_l1_selected(self, event=None):
        l1 = self.l1_combo.get()
        l2s = L1_L2_MAP.get(l1, [])
        self.l2_combo['values'] = l2s
        self.l2_combo.set('')
        for w in self.form_container.winfo_children():
            w.destroy()
        self.current_template = None
        self.field_widgets.clear()
        ### 修改：选择L1时，不再自动清空ID，而是由 clear_annotation_form 控制
        # self.selected_annotation_id = None 

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
            # 对 ObjectsSpatialRelationships 的 bounding_box 提供优雅输入（两个对象的独立输入框）
            if key == 'bounding_box' and self.l2_combo.get() == 'ObjectsSpatialRelationships':
                bb_frame = ttk.Frame(self.form_container)
                bb_frame.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)

                def build_bb_column(parent, title):
                    col = ttk.Labelframe(parent, text=title)
                    col.pack(side=tk.LEFT, padx=6)
                    # label
                    r1 = ttk.Frame(col); r1.pack(anchor=tk.W, pady=2)
                    ttk.Label(r1, text="label:").pack(side=tk.LEFT)
                    ent_label = ttk.Entry(r1, width=18)
                    ent_label.pack(side=tk.LEFT, padx=4)
                    # box 4 ints
                    r2 = ttk.Frame(col); r2.pack(anchor=tk.W, pady=2)
                    ttk.Label(r2, text="box:").pack(side=tk.LEFT)
                    e1 = ttk.Entry(r2, width=5); e2 = ttk.Entry(r2, width=5); e3 = ttk.Entry(r2, width=5); e4 = ttk.Entry(r2, width=5)
                    for i, e in enumerate((e1, e2, e3, e4)):
                        e.pack(side=tk.LEFT)
                        if i < 3:
                            ttk.Label(r2, text=",").pack(side=tk.LEFT)
                    return ent_label, [e1, e2, e3, e4]

                la1, b1 = build_bb_column(bb_frame, "对象1")
                la2, b2 = build_bb_column(bb_frame, "对象2")

                # 保存复合控件引用，供保存时读取
                self.field_widgets[key] = (("composite", {"label1": la1, "box1": b1, "label2": la2, "box2": b2}), default)

                # 提示
                hint = ttk.Label(self.form_container, text="请填写两个对象：每个包含 label 与 box(四个整数)", foreground="#666")
                hint.grid(row=row+1, column=1, sticky=tk.W, padx=4, pady=(0,6))
                row += 2
                continue
            # 选择控件：长文本/JSON 用 Text，其他用 Entry
            widget = None
            use_text = isinstance(default, (list, dict)) or key in ("Q_window_frame", "A_window_frame") or key == 'answer'
            if use_text:
                widget = tk.Text(self.form_container, width=60, height=3)
                # 针对特定字段提供默认结构或提示（不影响保存的有效性）
                if key == 'answer':
                    # 不预填内容，避免误保存；仅放提示标签
                    pass
            else:
                widget = ttk.Entry(self.form_container, width=60)
                if isinstance(default, (int, float)):
                    ### 修改：仅在“新建”时才填充默认值
                    if self.selected_annotation_id is None:
                        widget.insert(0, str(default))
            widget.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
            self.field_widgets[key] = (widget, default)
            # 在文本框下方增加提示标签（不写入内容本身）
            if key in ("Q_window_frame", "A_window_frame"):
                hint = ttk.Label(self.form_container, text="示例: 10,20   或   10,20; 30,40", foreground="#666")
                hint.grid(row=row+1, column=1, sticky=tk.W, padx=4, pady=(0,6))
                row += 2
            elif key == 'answer':
                hint = ttk.Label(self.form_container, text="支持：单条答案；或多条以分号/换行分隔；或直接粘贴JSON数组", foreground="#666")
                hint.grid(row=row+1, column=1, sticky=tk.W, padx=4, pady=(0,6))
                row += 2
            else:
                row += 1

    ### 修改：重命名为 save_annotation，并添加“修改”逻辑 ###
    def save_annotation(self):
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
        
        # --------------------------------
        # 构造 annotation (与原版一致)
        # --------------------------------
        content_fields = {}
        for key, (widget, default) in self.field_widgets.items():
            # 处理复合 bounding_box（ObjectsSpatialRelationships）
            if key == 'bounding_box' and isinstance(widget, tuple) and widget[0] == 'composite':
                sub = widget[1]
                lab1 = sub['label1'].get().strip()
                lab2 = sub['label2'].get().strip()
                b1_vals = [e.get().strip() for e in sub['box1']]
                b2_vals = [e.get().strip() for e in sub['box2']]
                # 暂不在此强制转 int，留待统一校验阶段处理
                try:
                    b1_list = [int(x) if x != '' else x for x in b1_vals]
                except Exception:
                    b1_list = b1_vals
                try:
                    b2_list = [int(x) if x != '' else x for x in b2_vals]
                except Exception:
                    b2_list = b2_vals
                content_fields[key] = [
                    {"label": lab1, "box": b1_list},
                    {"label": lab2, "box": b2_list}
                ]
                continue
            if isinstance(widget, tk.Text):
                raw = widget.get('1.0', tk.END).strip()
            else:
                raw = widget.get().strip()
            content_fields[key] = parse_value_from_text(raw, default, key)

        # 针对 ObjectsSpatialRelationships：强制字段形状与类型
        if self.l2_combo.get() == 'ObjectsSpatialRelationships':
            # timestamp_frame 必须为整数
            if 'timestamp_frame' not in content_fields:
                messagebox.showerror("错误", "缺少字段：timestamp_frame。")
                return
            try:
                content_fields['timestamp_frame'] = int(content_fields['timestamp_frame'])
            except Exception:
                messagebox.showerror("错误", "timestamp_frame 必须为整数。")
                return

            # answer 统一为单字符串（若为多条则合并为一条，以中文分号连接）
            if 'answer' in content_fields:
                ans_val = content_fields['answer']
                if isinstance(ans_val, list):
                    content_fields['answer'] = '；'.join(str(s) for s in ans_val)
                elif isinstance(ans_val, (dict, int, float)):
                    content_fields['answer'] = str(ans_val)
                else:
                    # 字符串保持不变
                    pass

            # bounding_box 必须为两个对象，且每个对象含 label 与 box(4个整数)
            bb = content_fields.get('bounding_box')
            if not isinstance(bb, list) or len(bb) != 2:
                messagebox.showerror("错误", "bounding_box 必须是包含两个对象的列表。")
                return
            def _check_item(item):
                if not isinstance(item, dict):
                    return False
                label = item.get('label')
                box = item.get('box')
                if not isinstance(label, str) or not label.strip():
                    return False
                if not isinstance(box, list) or len(box) != 4:
                    return False
                try:
                    coords = [int(x) for x in box]
                except Exception:
                    return False
                item['label'] = label.strip()
                item['box'] = coords
                return True
            if not (_check_item(bb[0]) and _check_item(bb[1])):
                messagebox.showerror("错误", "bounding_box 的每个对象必须包含 label 与 box(4个整数)。")
                return
            # 规范化后的值写回
            content_fields['bounding_box'] = bb
        # --------------------------------
        # 构造 annotation 结束
        # --------------------------------

        # 构造有序 annotation：annotation_id -> task -> 其他字段
        ann = {}
        existing = data.get('annotations') or []

        ### 新增：区分“修改”和“新增” ###
        is_modification = self.selected_annotation_id is not None
        
        if is_modification:
            # --- 修改模式 ---
            ann['annotation_id'] = self.selected_annotation_id
            ann['task_L1'] = self.l1_combo.get()
            ann['task_L2'] = self.l2_combo.get()
            for k, v in content_fields.items():
                ann[k] = v
            
            # 在列表中找到并替换
            found_index = -1
            for i, old_ann in enumerate(existing):
                if str(old_ann.get('annotation_id')) == self.selected_annotation_id:
                    found_index = i
                    break
            
            if found_index != -1:
                existing[found_index] = ann
            else:
                # 如果没找到（例如列表被外部修改），则当作追加
                existing.append(ann)
            
            data['annotations'] = existing
            msg = f"已修改标注 (ID: {self.selected_annotation_id}), 写回: {target_json}"
            
        else:
            # --- 新增模式 (原逻辑) ---
            max_id = 0
            for a in existing:
                try:
                    max_id = max(max_id, int(a.get('annotation_id', 0)))
                except Exception:
                    continue
            ann['annotation_id'] = str(max_id + 1)
            ann['task_L1'] = self.l1_combo.get()
            ann['task_L2'] = self.l2_combo.get()
            for k, v in content_fields.items():
                ann[k] = v
            existing.append(ann)
            data['annotations'] = existing
            msg = f"已添加新标注 (ID: {ann['annotation_id']}), 写回: {target_json}"
        
        # 保存
        try:
            with open(target_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("成功", msg)
            
            # --- 保存后刷新 ---
            self.populate_annotation_list() # 刷新列表
            self.clear_annotation_form()    # 清空表单
            
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


if __name__ == '__main__':
    app = App()
    app.mainloop()