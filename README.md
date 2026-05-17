# PDFAIExtract

多语言证书 PDF 信息提取工具，支持文本 + 视觉双模式识别。

## 功能特性

- 自动识别 PDF 文本层，文本充足时直接提取
- 文本不足时自动切换视觉识别模式
- 支持多种 LLM Provider (OpenAI/Claude/讯飞星火)
- 输出结构化 JSON 结果
- **支持自定义提取字段**

## 支持字段

默认支持以下字段，可在 `config.json` 中自定义：

- certificate_number (证书编号)
- product_name (产品名称)
- product_model (产品型号)
- manufacturer (制造商)
- issuing_authority (发证机构)
- issue_date (发证日期)
- expiry_date (有效期)
- certification_type (证书类型：3C/CE/FCC/UL 等)
- standards (适用标准)
- country (国家)
- language (语言)

### 自定义字段

在 `config.json` 的 `extraction.fields` 中配置要提取的字段：

```json
{
  "extraction": {
    "fields": {
      "serial_number": {
        "description": "设备序列号",
        "required": true
      },
      "firmware_version": {
        "description": "固件版本号",
        "required": false
      },
      "tags": {
        "description": "标签列表",
        "type": "list",
        "required": false
      }
    }
  }
}
```

字段配置说明：
- `description`: 字段描述，告诉 LLM 如何识别该字段
- `required`: 是否必填，必填字段缺失时会警告
- `type`: 字段类型，`string`（默认）或 `list`

也可以用环境变量：
```bash
export EXTRACTION_FIELDS='{"my_field": {"description": "我的字段", "required": true}}'
```

## 安装

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

## 配置

复制 `config.example.json` 为 `config.json` 并配置提取参数。也可直接用 `.env` 覆盖：

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o"
  },
  "extraction": {
    "dpi": 150,
    "min_text_length": 100,
    "fields": {
      "certificate_number": {
        "description": "证书编号",
        "required": true
      },
      "product_name": {
        "description": "产品名称",
        "required": true
      },
      "manufacturer": {
        "description": "制造商",
        "required": false
      }
    }
  }
}
```

`provider` 可选 `openai`、`anthropic`。

环境变量优先级更高：

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
```

Claude 走 `provider=anthropic`，`LLM_API_KEY` 可直接放 `ANTHROPIC_API_KEY`。

## 使用

### Python 调用

单文件处理：
```python
from main import CertificateExtractor

extractor = CertificateExtractor()
results = extractor.process_pdf("path/to/certificate.pdf")
extractor.save_results(results, "output.json")
```

### 通过方法入参指定字段（最简）

无需改配置文件，直接传 `fields`：

```python
extractor = CertificateExtractor()

# 形式 1: 字符串列表（描述即字段名）
results = extractor.process_pdf("cert.pdf", fields=["证书编号", "产品名称", "制造商"])

# 形式 2: 简单 dict（key=字段名, value=描述）
results = extractor.process_pdf("cert.pdf", fields={
    "serial": "设备序列号",
    "model": "产品型号",
})

# 形式 3: 完整 dict（含 required/type）
results = extractor.process_pdf("cert.pdf", fields={
    "serial": {"description": "序列号", "required": True},
    "tags": {"description": "标签", "type": "list"},
})

# 也可在初始化时设
extractor = CertificateExtractor(fields=["证书编号", "型号"])

# 目录批量也支持
extractor.process_directory("pdfs/", "output/", fields=["证书编号"])
```

批量处理：
```python
extractor.process_directory("pdfs/", "output/")
```

### FastAPI 接口

启动服务：
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看交互式 API 文档。

#### 1. 上传 PDF 文件

**请求：**
```bash
curl -X POST "http://localhost:8000/extract" \
  -F "file=@certificate.pdf"
```

**响应：**
```json
{
  "success": true,
  "results": [
    {
      "file_name": "certificate.pdf",
      "page_number": 1,
      "extraction_method": "text",
      "confidence": 0.9,
      "data": {
        "certificate_number": "2026010708845104",
        "product_name": "智能吸尘器",
        "product_model": "RLZ83DE",
        "manufacturer": "追觅贸易（天津）有限公司",
        "issuing_authority": null,
        "issue_date": "2026-01-28",
        "expiry_date": "2031-01-27",
        "certification_type": "3C",
        "standards": ["GB 17625.1-2022", "GB 4343.1-2024"],
        "country": "CN",
        "language": "zh"
      },
      "raw_text": "..."
    }
  ],
  "error": null
}
```

#### 2. Base64 编码的 PDF

**请求：**
```bash
curl -X POST "http://localhost:8000/extract/base64" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "certificate.pdf",
    "content_base64": "JVBERi0xLjQKJeLjz9..."
  }'
```

**响应：** 同上

#### 3. 健康检查

```bash
curl http://localhost:8000/health
```

响应：`{"status": "ok"}`

#### 错误响应

```json
{
  "success": false,
  "results": [],
  "error": "错误信息"
}
```

常见错误码：
- `400` - 文件格式错误（非 PDF）
- `413` - 文件过大（默认最大 50MB）
- `500` - 服务器内部错误

## 项目结构

```
PDFAIExtract/
├── main.py              # 主入口
├── config.py            # 配置加载
├── config.example.json  # 配置示例
├── processors/          # PDF 处理
├── extractors/          # LLM 提取器
├── models/              # 数据模型
├── test_pdfs/           # 测试文件
└── output/              # 输出目录
```

## 技术流程

1. 提取 PDF 文本层
2. 判断文本是否充足
3. 充足 → 直接 LLM 提取; 不足 → 渲染图片 → 视觉模型识别
4. 输出结构化 JSON

## License

MIT
