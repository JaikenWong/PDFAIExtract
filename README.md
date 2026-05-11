# PDFAIExtract

多语言证书PDF信息提取工具，支持文本+视觉双模式识别。

## 功能特性

- 自动识别PDF文本层，文本充足时直接提取
- 文本不足时自动切换视觉识别模式
- 支持多种LLM Provider (OpenAI/Claude/讯飞星火)
- 输出结构化JSON结果

## 支持字段

- certificate_number (证书编号)
- product_name (产品名称)
- product_model (产品型号)
- manufacturer (制造商)
- issuing_authority (发证机构)
- issue_date (发证日期)
- expiry_date (有效期)
- certification_type (证书类型: 3C/CE/FCC/UL等)
- standards (适用标准)
- country (国家)
- language (语言)

## 安装

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入API密钥
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
    "min_text_length": 100
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
├── processors/          # PDF处理
├── extractors/          # LLM提取器
├── models/              # 数据模型
├── test_pdfs/           # 测试文件
└── output/              # 输出目录
```

## 技术流程

1. 提取PDF文本层
2. 判断文本是否充足
3. 充足 → 直接LLM提取; 不足 → 渲染图片 → 视觉模型识别
4. 输出结构化JSON

## License

MIT
