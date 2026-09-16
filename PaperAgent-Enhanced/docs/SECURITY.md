# Security and limitations

- Uploaded PDFs are untrusted input. Run the application in an isolated environment and keep dependencies patched.
- A paper can contain prompt-injection text. The system prompt reduces this risk but does not eliminate it; never expose privileged tools or unrelated secrets to the model.
- Do not commit `.env`, uploaded papers, generated indexes, or API keys. The supplied `.gitignore` excludes them.
- Generated answers and slides may still be wrong. Verify quotations, page numbers, numerical results, and conclusions against the source PDF.
- Scanned PDFs require OCR; this repository only extracts embedded PDF text.

