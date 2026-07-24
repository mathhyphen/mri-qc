# mri-qc

一个基于 Web 的 MRI 影像质量控制（QC）审阅工具。递归扫描文件夹中的 NIfTI 影像，自动生成三截面缩略图（轴位 / 矢状位 / 冠状位），并提供响应式网页界面，支持在**手机、平板、电脑**任意设备上进行人工 QC。

## ✨ 核心功能

- **递归扫描** — 自动发现多层子文件夹中的所有 `.nii` / `.nii.gz` 文件
- **三截面缩略图** — 统一重定向到 RAS+，采用放射学惯例显示（R 在左）
- **交互式切片查看器** — 点击图像即可滑动浏览三个方向的任意切片，原始分辨率渲染
- **响应式 Web 界面** — 手机 / 平板 / 电脑自适应布局
- **QC 状态持久化** — 审阅结果实时写入 JSON，浏览器崩溃或服务器重启不丢失
- **缩略图缓存** — 生成一次后缓存，重启秒开
- **CSV 导出** — 一键导出全部 QC 判定结果
- **键盘快捷键** — `1/2/3` 快速标记，`N` 跳到下一个未审核
- **公网隧道** — 可选 ngrok 集成，生成公网链接发给他人远程 QC

## 📦 安装

**推荐 — 使用 [pipx](https://pipx.pypa.io/)（独立环境，不污染系统 Python）：**

```bash
pipx install git+https://github.com/mathhyphen/mri-qc.git
```

**或使用 pip：**

```bash
pip install git+https://github.com/mathhyphen/mri-qc.git
```

**开发者：**

```bash
git clone https://github.com/mathhyphen/mri-qc.git
cd mri-qc
pip install -e ".[tunnel]"   # [tunnel] 为可选的 ngrok 支持
```

> 依赖：Python ≥ 3.9，Flask、nibabel、numpy、Pillow

## 🚀 快速开始

```bash
# 扫描文件夹并启动服务
mri-qc /path/to/mri/data
```

启动后终端会打印访问地址，在任意浏览器打开即可开始 QC：

```
🌐  Local : http://127.0.0.1:5000
📱  LAN   : http://192.168.x.x:5000   ← 同一 WiFi 下手机/平板可访问
```

更多示例见 [DEMO.md](DEMO.md) 完整演示教程。

## ⚙️ 命令行参数

```
mri-qc --help
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `folder` | （必填） | 递归扫描的根文件夹 |
| `--port, -p` | 5000 | Web 服务端口 |
| `--host` | 0.0.0.0 | 监听地址 |
| `--cache-dir` | `<folder>/.qc_cache` | 缩略图缓存目录 |
| `--state-dir` | 同 cache-dir | QC 状态 JSON 存放目录 |
| `--workers, -w` | 4 | 缩略图生成并发线程数 |
| `--ext` | `.nii .nii.gz` | 要扫描的文件扩展名 |
| `--tunnel` | 关闭 | 启用 ngrok 公网隧道 |
| `--ngrok-token` | `$NGROK_TOKEN` | ngrok 认证 token |
| `--ngrok-domain` | `$NGROK_DOMAIN` | ngrok 固定域名 |

## ⌨️ 键盘快捷键

| 按键 | 功能 |
|------|------|
| `← →` | 选择图像 |
| `1` | 通过（保留） |
| `2` | 复核（暂留） |
| `3` | 排除 |
| `0` | 清除标记 |
| `N` | 跳到下一个未审核 |
| `PgUp/PgDn` | 翻页 |
| `Esc` | 关闭查看器/大图 |

## 🌍 公网访问（ngrok）

想把链接发给不在同一局域网的人？启用隧道：

```bash
export NGROK_TOKEN=你的token        # 在 https://dashboard.ngrok.com 免费获取
export NGROK_DOMAIN=你的域名.ngrok-free.dev   # 可选，固定域名
mri-qc /path/to/data --tunnel
```

启动后会打印一个公网 URL，任何人打开即可远程 QC。

## 📁 缓存说明

- 缩略图缓存：`<folder>/.qc_cache/thumbs/`
- 体积数据缓存：`<folder>/.qc_cache/volumes/`（交互式查看器用）
- QC 状态：`<folder>/.qc_cache/qc_state.json`（可用 `--state-dir` 分离）

所有缓存均可安全删除，重启后自动重建。

## 📄 License

MIT
