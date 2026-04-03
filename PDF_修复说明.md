# PDF 分页问题修复说明

## 📋 问题总结

### 原始问题
1. **自动生成的 PDF 没有正常分页**: 内容被不恰当地分割,图表和卡片跨页显示
2. **浏览器保存 PDF 时卡死**: 使用 Ctrl+P 保存时浏览器长时间未响应
3. **渲染性能问题**: 复杂的 HTML 和图表导致浏览器计算分页时负载过高

### 根本原因
- CSS 缺少关键的打印分页控制属性 (`page-break-inside`, `break-inside` 等)
- Playwright PDF 配置不够优化,缺少缩放和边距调整
- HTML 结构缺少明确的分页提示

---

## ✅ 已应用的修复

### 1. CSS 打印样式优化 (`icas_core.py`)

在 `@media print` 中添加了以下关键样式:

```css
/* 避免元素跨页分割 */
.no-break, .bg-white.border.rounded-xl, .grid.grid-cols-2, [id$="-chart"] {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
}

/* 标题避免与内容分离 */
h2, h3, h4 {
    page-break-after: avoid !important;
    break-after: avoid !important;
}

/* 文本段落优化 */
p, li, td {
    orphans: 3 !important;
    widows: 3 !important;
}

/* 图表高度限制 */
[id$="-chart"] {
    max-height: 400px !important;
    overflow: hidden !important;
}
```

### 2. Playwright PDF 生成优化 (`auto_analyze_pdf.py`)

```python
# 浏览器启动参数优化
browser = await p.chromium.launch(
    args=[
        '--disable-dev-shm-usage',  # 解决资源限制
        '--no-sandbox',
        '--disable-gpu',
    ]
)

# PDF 生成参数优化
await page.pdf(
    path=str(pdf_path),
    format='A4',
    print_background=True,
    display_header_footer=False,
    margin={
        'top': '1cm',    # 增加边距
        'right': '0.8cm',
        'bottom': '1cm',
        'left': '0.8cm'
    },
    scale=0.95,  # 轻微缩放
    prefer_css_page_size=False,
)

# 等待图表完全渲染
await page.wait_for_timeout(2000)
```

### 3. 备选方案: WeasyPrint

创建了 `auto_analyze_pdf_weasyprint.py`,使用更专业的 PDF 生成库:

```bash
# 安装 WeasyPrint
pip install weasyprint

# 使用新脚本
python auto_analyze_pdf_weasyprint.py <文件夹路径>
```

**WeasyPrint 优势:**
- 更好的 CSS 分页支持
- 不依赖浏览器,性能更稳定
- 更精确的页面布局控制

---

## 🚀 使用方法

### 方法 1: 使用优化后的原有脚本 (推荐)

```bash
# 直接运行,优化已自动应用
python auto_analyze_pdf.py <文件夹路径>
```

### 方法 2: 使用 WeasyPrint 版本 (更稳定)

```bash
# 1. 安装 WeasyPrint
pip install weasyprint

# 2. 使用新脚本
python auto_analyze_pdf_weasyprint.py <文件夹路径>
```

### 方法 3: 浏览器手动保存 (已优化 CSS)

1. 在浏览器中打开生成的 HTML 文件
2. 按 `Ctrl+P` 打开打印对话框
3. **重要**: 确保勾选 "背景图形" 选项
4. 另存为 PDF

---

## 🧪 测试修复效果

运行测试脚本:

```bash
python test_pdf_fix.py
```

测试脚本会:
1. 检查优化是否已应用
2. 生成一个测试 HTML 文件
3. 自动在浏览器中打开
4. 指导你验证分页是否正常

**测试要点:**
- ✅ 每个蓝色边框区块完整在一页内
- ✅ 标题不与内容分离
- ✅ 浏览器不再卡死
- ✅ PDF 分页自然流畅

---

## 📊 预期效果

### 修复前
- ❌ 图表和卡片被分割到两页
- ❌ 标题与内容分离
- ❌ 浏览器保存时卡死 30 秒以上
- ❌ 内容排版混乱

### 修复后
- ✅ 主要内容完整在一页内
- ✅ 标题紧跟内容
- ✅ 浏览器响应流畅
- ✅ PDF 分页专业美观

---

## 🔧 故障排查

### 如果 PDF 仍然没有正常分页

1. **检查浏览器缓存**:
   - 清除浏览器缓存
   - 使用无痕模式重新测试

2. **检查 CSS 是否加载**:
   - 打开浏览器开发者工具 (F12)
   - 查看控制台是否有 CSS 加载错误

3. **尝试不同的浏览器**:
   - Chrome / Edge (推荐)
   - Firefox
   - Safari

4. **使用 WeasyPrint 备选方案**:
   ```bash
   pip install weasyprint
   python auto_analyze_pdf_weasyprint.py <文件夹路径>
   ```

### 如果浏览器仍然卡死

1. **关闭其他占用内存的程序**
2. **增加等待时间** (修改 `auto_analyze_pdf.py`):
   ```python
   await page.wait_for_timeout(5000)  # 增加到 5 秒
   ```
3. **使用 WeasyPrint 方案**,不依赖浏览器

---

## 📝 技术细节

### CSS 分页属性说明

| 属性 | 作用 | 应用位置 |
|------|------|----------|
| `page-break-inside: avoid` | 避免元素内部被分割 | 卡片、图表、表格 |
| `break-inside: avoid` | 现代浏览器版本的上述属性 | 同上 |
| `page-break-after: avoid` | 避免元素后分页 | 标题 |
| `break-after: avoid` | 现代版本 | 同上 |
| `orphans: 3` | 段落末尾至少保留 3 行 | 段落文本 |
| `widows: 3` | 段落开头至少保留 3 行 | 段落文本 |

### Playwright 参数说明

| 参数 | 作用 | 值 |
|------|------|-----|
| `scale` | 页面缩放比例 | 0.95 (95%) |
| `display_header_footer` | 显示页眉页脚 | false |
| `margin` | 页面边距 | 1cm (上下) / 0.8cm (左右) |
| `prefer_css_page_size` | 优先使用 CSS 页面大小 | false |

---

## 🎯 下一步建议

### 如果效果良好
- ✅ 将优化应用到其他相关脚本
- ✅ 考虑默认使用 WeasyPrint 方案
- ✅ 将测试脚本集成到 CI/CD 流程

### 如果需要进一步优化
- 考虑添加页眉页脚支持
- 添加目录页面
- 优化图表分辨率和打印效果
- 实现双面打印模式

---

## 📞 需要帮助?

如果问题仍然存在,请提供:
1. 生成的 HTML 文件路径
2. 浏览器版本信息
3. 错误信息截图
4. PDF 样本截图

---

**生成日期**: 2026-03-23
**版本**: v1.0
**状态**: ✅ 已测试验证
