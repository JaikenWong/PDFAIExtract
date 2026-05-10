import sys
from config import load_config, get_config
from main import CertificateExtractor

cfg = load_config()
api_key = cfg["llm"].get("api_key", "")

if not api_key or api_key == "your_api_key_here":
    print("ERROR: No API key found in config.json")
    print("Please edit config.json and set llm.api_key")
    sys.exit(1)

extractor = CertificateExtractor()

print("Testing with 3C certificate sample...")
results = extractor.process_pdf("test_pdfs/3c_cert_sample.pdf")
extractor.save_results(results, "output/3c_test.json")

print("\n" + "=" * 50)
print("Testing with CE certificate sample...")
results = extractor.process_pdf("test_pdfs/ce_cert_sample.pdf")
extractor.save_results(results, "output/ce_test.json")

print("\n" + "=" * 50)
print("Testing with FCC certificate sample...")
results = extractor.process_pdf("test_pdfs/fcc_cert_sample.pdf")
extractor.save_results(results, "output/fcc_test.json")

print("\n" + "=" * 50)
print("All tests completed! Check output/ directory for results.")