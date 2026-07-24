# mri-qc 演示教程（Demo）

本文档带你从零跑通一个完整的 QC 流程：**生成演示数据 → 启动服务 → 网页审阅 → 交互式看片 → 导出结果**。

全程约 5 分钟。

---

## 第一步：准备演示数据

如果你手头有真实的 `.nii` / `.nii.gz` 数据，可以直接跳到第二步。

没有数据？运行下面的脚本生成 6 个仿真的"大脑" NIfTI 体积（含脑实质、脑室、灰质边缘和噪声，三截面看起来像模像样）：

```python
# make_demo_data.py
import numpy as np
import nibabel as nib
from pathlib import Path


def make_brain(out_path, shape=(160, 192, 160), seed=0):
    rng = np.random.default_rng(seed)
    x, y, z = np.indices(shape)
    cx, cy, cz = (s / 2 for s in shape)

    # 椭球体模拟大脑
    r = ((x - cx) / (shape[0] * 0.42))**2 + \
        ((y - cy) / (shape[1] * 0.46))**2 + \
        ((z - cz) / (shape[2] * 0.42))**2
    brain = (r < 1).astype(np.float32)

    # 中央暗色"脑室"
    rv = ((x - cx) / (shape[0] * 0.06))**2 + \
         ((y - cy) / (shape[1] * 0.10))**2 + \
         ((z - cz * 0.98) / (shape[2] * 0.08))**2
    ventricle = (rv < 1).astype(np.float32)

    # 外层"灰质"高信号边缘
    rim = ((r > 0.75) & (r < 1)).astype(np.float32)

    img = brain * 100 - ventricle * 60 + rim * 40
    img += rng.normal(0, 3, shape).astype(np.float32)   # 背景噪声
    img = np.clip(img, 0, None)

    nib.save(nib.Nifti1Image(img, np.eye(4)), str(out_path))


out = Path("demo_data")
for i in range(6):
    sub = out / f"sub-{i + 1:02d}" / "anat"
    sub.mkdir(parents=True, exist_ok=True)
    make_brain(sub / "T1w.nii.gz", seed=i)

print(f"✅ 已生成 6 个演示样本 → {out.resolve()}")
```

```bash
pip install nibabel numpy   # 如未安装
python make_demo_data.py
```

生成的目录结构（模拟真实的多层子文件夹）：

```
demo_data/
├── sub-01/anat/T1w.nii.gz
├── sub-02/anat/T1w.nii.gz
├── ...
└── sub-06/anat/T1w.nii.gz
```

---

## 第二步：启动 QC 服务

```bash
mri-qc demo_data
```

终端输出：

```
  ╔══════════════════════════════════════════════╗
  ║          🧠  MRI QC Review Server           ║
  ╚══════════════════════════════════════════════╝

  📂  Data folder : /path/to/demo_data
  🌐  Local       : http://127.0.0.1:5000
  📱  LAN         : http://192.168.x.x:5000
  ...
```

浏览器打开 `http://127.0.0.1:5000`。

> 💡 想在手机/iPad 上操作？确保和电脑连**同一个 WiFi**，然后访问上面打印的 **LAN** 地址。

---

## 第三步：网页审阅

打开后你会看到：

- **顶部状态栏** — 总数、通过/复核/排除计数、审阅进度条
- **工具栏** — 搜索框、状态筛选、文件夹筛选、每页数量、卡片宽度/图片高度滑块
- **图像网格** — 每张卡片显示三截面缩略图 + 文件名 + QC 按钮

### 开始 QC

1. 点击卡片上的 **「✓ 通过」「⚑ 复核」「✗ 排除」** 按钮标记
2. 或用键盘：`←→` 选中图像，按 `1` / `2` / `3` 快速标记，`0` 清除
3. 按 `N` 自动跳到下一个**未审核**的图像
4. 标记会**实时保存**，刷新页面、关浏览器甚至重启服务器都不会丢

### 筛选与搜索

- 搜索框输入 `sub-03` → 只显示匹配的文件
- 状态下拉选「未审核」→ 专注处理剩余任务
- 文件夹下拉可按子文件夹（如 `sub-01/anat`）过滤

---

## 第四步：交互式切片查看器

**点击任意缩略图**，打开全屏查看器：

```
┌──────────────────────────────────────────────┐
│  sub-01/anat/T1w.nii.gz            [✕ 关闭]  │
│                                              │
│              ┌──────────────┐                │
│              │   主视图(大)  │                │
│              │  当前切面     │                │
│              └──────────────┘                │
│                                              │
│        [Axial] [Sagittal] [Coronal]          │  ← 点小缩略图切换方向
│                                              │
│        Slice ──────●────── z=80/159          │  ← 拖动滑块浏览切片
│                                              │
│        [✓ 通过] [⚑ 复核] [✗ 排除] [↺]        │
└──────────────────────────────────────────────┘
```

- **拖动滑块** — 沿当前方向逐层浏览（原始分辨率，细节清晰）
- **点击小缩略图** — 切换 Axial / Sagittal / Coronal 主视图
- **点击主视图** — 移动十字线定位，其他两个切面自动联动到对应位置
- 首次打开某个文件会下载其 3D 体积（约几 MB），之后走缓存秒开

---

## 第五步：导出 QC 结果

点击工具栏的 **「⬇ 导出 CSV」**，下载 `qc_results.csv`：

```csv
file,folder,size_mb,qc_status,note,timestamp
T1w.nii.gz,sub-01/anat,1.23,pass,,2026-07-24T...
T1w.nii.gz,sub-02/anat,1.23,exclude,,2026-07-24T...
T1w.nii.gz,sub-03/anat,1.23,unreviewed,,
...
```

可直接导入 Excel / pandas 做后续统计分析。

---

## 第六步（可选）：发给别人远程 QC

不在同一局域网的同事也能参与？启用 ngrok 隧道：

```bash
export NGROK_TOKEN=你的token     # https://dashboard.ngrok.com 免费注册获取
mri-qc demo_data --tunnel
```

终端会多打印一行：

```
🌍  Public URL : https://xxxx.ngrok-free.dev
```

把这个链接发给任何人，打开即可远程审阅。**所有人的标记写入同一份 QC 状态**，实时同步。

---

## 常见问题

**Q：缩略图一直显示"生成中"？**
A：首次启动需要后台生成缩略图，数据量大时等 1-2 分钟。进度显示在顶部状态栏「缩略图 x/N」。

**Q：手机打不开 LAN 地址？**
A：① 确认手机和电脑同一 WiFi；② 检查 Windows 防火墙是否放行 `python.exe`（专用+公用网络）。

**Q：换了电脑/重启后 QC 进度还在吗？**
A：在。进度存在 `<数据文件夹>/.qc_cache/qc_state.json`，只要这个文件还在就能恢复。

**Q：图像方向怎么看？**
A：统一为放射学惯例——Axial/Coronal 中患者的 **R（右）显示在图像左侧**，Sagittal 中 **A（前）在左、S（上）在上**。
