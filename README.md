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

复制 `config.example.json` 为 `config.json` 并配置提取参数：

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

## 使用

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