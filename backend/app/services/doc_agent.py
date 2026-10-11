import ast
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import get_settings
from app.schemas.doc_gen import (
    DocFormat,
    DocGenRequest,
    DocGenResponse,
    MermaidDiagramType,
    ModuleDocItem,
)
from app.schemas.retrieval import HybridSearchQuery
from app.services.hybrid_retriever import hybrid_retriever_service

logger = logging.getLogger("devmind.agents.doc")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

DOC_AGENT_SYSTEM_PROMPT = """You are the DevMind Principal Technical Writer & Systems Architect.
Generate crystal-clear, production-grade living documentation, standardized docstrings, and valid Mermaid architecture diagrams for the provided source code.

Return your response strictly as a JSON object matching this schema:
{
  "module_overview": "High-level architectural summary",
  "mermaid_diagram": "flowchart TD\\n  A[\\"Client\\"] --> B[\\"Service\\"]",
  "documented_symbols": [
    {
      "symbol_name": "name",
      "symbol_type": "function" | "class" | "async_function",
      "signature": "def name(...)",
      "generated_docstring": "formatted docstring",
      "summary": "concise explanation"
    }
  ]
}
"""


class ExtractedSymbolDoc:
    """Internal representation of an AST-extracted symbol for documentation."""

    def __init__(
        self,
        name: str,
        symbol_type: str,
        signature: str,
        params: List[Tuple[str, str]],
        return_type: str,
        existing_docstring: Optional[str] = None,
        calls: Optional[List[str]] = None,
        bases: Optional[List[str]] = None,
        methods: Optional[List[str]] = None,
    ):
        self.name = name
        self.symbol_type = symbol_type
        self.signature = signature
        self.params = params
        self.return_type = return_type
        self.existing_docstring = existing_docstring
        self.calls = calls or []
        self.bases = bases or []
        self.methods = methods or []


class PythonASTDocExtractor(ast.NodeVisitor):
    """AST visitor extracting imports, classes, functions, type hints, and call edges."""

    def __init__(self):
        self.imports: List[str] = []
        self.symbols: List[ExtractedSymbolDoc] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        self.generic_visit(node)

    def _format_annotation(self, ann: Any) -> str:
        if ann is None:
            return "Any"
        try:
            return ast.unparse(ann)
        except Exception:
            return "Any"

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [self._format_annotation(b) for b in node.bases]
        methods = [
            n.name for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        base_str = f"({', '.join(bases)})" if bases else ""
        sig = f"class {node.name}{base_str}:"
        doc = ast.get_docstring(node)

        self.symbols.append(
            ExtractedSymbolDoc(
                name=node.name,
                symbol_type="class",
                signature=sig,
                params=[],
                return_type=node.name,
                existing_docstring=doc,
                bases=bases,
                methods=methods,
            )
        )
        self.generic_visit(node)

    def _visit_callable(self, node: Any, is_async: bool):
        params: List[Tuple[str, str]] = []
        for arg in node.args.args:
            if arg.arg in ("self", "cls"):
                continue
            ann_str = self._format_annotation(arg.annotation)
            params.append((arg.arg, ann_str))

        ret_str = self._format_annotation(node.returns)
        prefix = "async def" if is_async else "def"
        param_sig = ", ".join(f"{p}: {t}" for p, t in params)
        sig = f"{prefix} {node.name}({param_sig}) -> {ret_str}:"
        doc = ast.get_docstring(node)

        calls: List[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name):
                    calls.append(f"{child.func.value.id}.{child.func.attr}")
                elif isinstance(child.func, ast.Name):
                    calls.append(child.func.id)

        self.symbols.append(
            ExtractedSymbolDoc(
                name=node.name,
                symbol_type="async_function" if is_async else "function",
                signature=sig,
                params=params,
                return_type=ret_str,
                existing_docstring=doc,
                calls=sorted(list(set(calls)))[:5],
            )
        )

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_callable(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_callable(node, is_async=True)


class DocAgentService:
    """Specialized agent service for living documentation, docstring synthesis, and Mermaid diagrams."""

    def __init__(self):
        self.settings = get_settings()

    def build_docstring(
        self, sym: ExtractedSymbolDoc, doc_format: DocFormat
    ) -> Tuple[str, str]:
        """Generate formatted docstring and plain-English summary for a symbol."""
        base_summary = (
            sym.existing_docstring.splitlines()[0]
            if sym.existing_docstring
            else f"Executes `{sym.name}` ({sym.symbol_type.replace('_', ' ')}) operations and domain workflow."
        )

        if doc_format == DocFormat.JSDOC:
            lines = ["/**", f" * {base_summary}"]
            for p_name, p_type in sym.params:
                lines.append(f" * @param {{{p_type}}} {p_name} - Input parameter `{p_name}`.")
            lines.append(f" * @returns {{{sym.return_type}}} Resulting `{sym.return_type}` payload.")
            lines.append(" */")
            return "\n".join(lines), base_summary

        if doc_format == DocFormat.SPHINX:
            lines = [f'"""{base_summary}', ""]
            for p_name, p_type in sym.params:
                lines.append(f":param {p_name}: Input `{p_name}` of type `{p_type}`.")
                lines.append(f":type {p_name}: {p_type}")
            lines.append(f":return: Output of type `{sym.return_type}`.")
            lines.append(f":rtype: {sym.return_type}")
            lines.append('"""')
            return "\n".join(lines), base_summary

        # Default: Google Style
        lines = [f'"""{base_summary}']
        if sym.params:
            lines.append("\nArgs:")
            for p_name, p_type in sym.params:
                lines.append(f"    {p_name} ({p_type}): Input `{p_name}` parameter.")
        if sym.methods and sym.symbol_type == "class":
            lines.append("\nMethods:")
            for m in sym.methods:
                lines.append(f"    {m}: Class method handler.")
        lines.append("\nReturns:")
        lines.append(f"    {sym.return_type}: Processed `{sym.return_type}` result.")
        lines.append('"""')
        return "\n".join(lines), base_summary

    def generate_mermaid_diagram(
        self,
        target_file: str,
        symbols: List[ExtractedSymbolDoc],
        imports: List[str],
        diagram_type: MermaidDiagramType = MermaidDiagramType.FLOWCHART,
    ) -> str:
        """Synthesize valid Mermaid diagram representing module structure and call flow."""
        module_label = Path(target_file).name or "Module"

        if diagram_type == MermaidDiagramType.CLASS:
            lines = ["classDiagram"]
            classes = [s for s in symbols if s.symbol_type == "class"]
            if not classes:
                lines.append(f'    class Module_{Path(target_file).stem} {{')
                for s in symbols:
                    lines.append(f"        +{s.name}() {s.return_type}")
                lines.append("    }")
            else:
                for cls in classes:
                    lines.append(f"    class {cls.name} {{")
                    for m in cls.methods:
                        lines.append(f"        +{m}()")
                    lines.append("    }")
                    for b in cls.bases:
                        clean_b = re.sub(r"[^a-zA-Z0-9_]", "", b)
                        if clean_b:
                            lines.append(f"    {clean_b} <|-- {cls.name}")
            return "\n".join(lines)

        if diagram_type == MermaidDiagramType.SEQUENCE:
            lines = ["sequenceDiagram"]
            lines.append(f'    participant Caller as "Client / Caller"')
            lines.append(f'    participant Mod as "{module_label}"')
            for idx, s in enumerate(symbols[:4], 1):
                lines.append(f'    Caller->>Mod: {s.name}()')
                for call in s.calls[:2]:
                    dep_id = f"Dep_{idx}_{re.sub(r'[^a-zA-Z0-9]', '', call)}"
                    lines.append(f'    participant {dep_id} as "{call}"')
                    lines.append(f'    Mod->>{dep_id}: invoke {call}()')
                lines.append(f'    Mod-->>Caller: return {s.return_type}')
            return "\n".join(lines)

        # Default: Flowchart TD
        lines = ["flowchart TD"]
        lines.append(f'    Mod["Module: {module_label}"]')

        for idx, imp in enumerate(imports[:4], 1):
            imp_node = f"Imp{idx}"
            lines.append(f'    Mod -.->|imports| {imp_node}["Dependency: {imp}"]')

        for idx, sym in enumerate(symbols[:6], 1):
            sym_node = f"Sym{idx}"
            kind = sym.symbol_type.replace("_", " ").title()
            lines.append(f'    Mod --> {sym_node}["{kind}: {sym.name}()"]')
            for c_idx, call in enumerate(sym.calls[:2], 1):
                call_node = f"Call_{idx}_{c_idx}"
                lines.append(f'    {sym_node} --> {call_node}["Call: {call}"]')

        return "\n".join(lines)

    def assemble_markdown(
        self,
        repo_id: str,
        target_file: str,
        overview: str,
        items: List[ModuleDocItem],
        mermaid_diagram: Optional[str],
    ) -> str:
        """Assemble comprehensive Markdown documentation page."""
        sections = [
            f"# Living Documentation: `{target_file}`",
            f"**Repository:** `{repo_id}`\n",
            "## 1. Architectural Overview",
            overview + "\n",
        ]

        if mermaid_diagram:
            sections.extend(
                [
                    "## 2. Architecture & Execution Flow Diagram",
                    f"```mermaid\n{mermaid_diagram}\n```\n",
                ]
            )

        sections.append("## 3. Symbol & API Reference\n")
        if not items:
            sections.append("_No top-level symbols extracted._\n")
        else:
            sections.append("| Symbol | Type | Signature | Summary |")
            sections.append("| :--- | :--- | :--- | :--- |")
            for item in items:
                sections.append(
                    f"| `{item.symbol_name}` | **{item.symbol_type}** | `{item.signature}` | {item.summary} |"
                )

            sections.append("\n## 4. Standardized Docstrings\n")
            for item in items:
                sections.append(f"### `{item.symbol_name}` (`{item.symbol_type}`)")
                sections.append(f"```python\n{item.signature}\n    {item.generated_docstring}\n```\n")

        return "\n".join(sections)

    async def generate_documentation(
        self,
        request: DocGenRequest,
        force_offline: bool = False,
    ) -> DocGenResponse:
        """Generate structured module documentation, docstrings, and Mermaid diagrams."""
        source_code = request.code_snippet or ""
        target_file = request.target_path or "app/main.py"

        # 1. Retrieve from Hybrid Retriever if no snippet provided
        if not source_code and request.repo_id:
            search_q = request.query or "class def architecture main module"
            query_obj = HybridSearchQuery(
                repo_id=request.repo_id,
                query=search_q,
                top_k=4,
                alpha=0.5,
                file_path_filter=request.target_path,
            )
            search_resp = await hybrid_retriever_service.search(params=query_obj)
            if search_resp.chunks:
                target_file = search_resp.chunks[0].file_path
                source_code = "\n\n".join(c.content for c in search_resp.chunks[:3])

        # Auto-select JSDoc if TS/JS file and default format was left as GOOGLE
        doc_format = request.doc_format
        if target_file.endswith((".ts", ".tsx", ".js", ".jsx")) and doc_format == DocFormat.GOOGLE:
            doc_format = DocFormat.JSDOC

        # 2. Extract AST symbols and imports
        extractor = PythonASTDocExtractor()
        if source_code:
            try:
                tree = ast.parse(source_code)
                extractor.visit(tree)
            except SyntaxError:
                # Fallback regex extraction for TS/JS or partial snippets
                for m in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)", source_code):
                    fn_name = m.group(1)
                    raw_params = [p.strip().split(":")[0].strip() for p in m.group(2).split(",") if p.strip()]
                    extractor.symbols.append(
                        ExtractedSymbolDoc(
                            name=fn_name,
                            symbol_type="function",
                            signature=f"function {fn_name}({m.group(2)})",
                            params=[(p, "any") for p in raw_params],
                            return_type="Promise<any>",
                        )
                    )

        # If still empty, provide a module-level entry
        if not extractor.symbols:
            extractor.symbols.append(
                ExtractedSymbolDoc(
                    name=Path(target_file).stem or "module_entry",
                    symbol_type="function",
                    signature=f"def {Path(target_file).stem or 'module_entry'}() -> None:",
                    params=[],
                    return_type="None",
                )
            )

        # 3. Synthesize docstrings for all extracted symbols
        doc_items: List[ModuleDocItem] = []
        for sym in extractor.symbols:
            docstring, summary = self.build_docstring(sym, doc_format)
            doc_items.append(
                ModuleDocItem(
                    symbol_name=sym.name,
                    symbol_type=sym.symbol_type,
                    signature=sym.signature,
                    generated_docstring=docstring,
                    summary=summary,
                )
            )

        # 4. Generate Mermaid diagram if requested
        mermaid_str: Optional[str] = None
        if request.include_mermaid:
            mermaid_str = self.generate_mermaid_diagram(
                target_file=target_file,
                symbols=extractor.symbols,
                imports=extractor.imports,
                diagram_type=request.diagram_type,
            )

        symbol_names = ", ".join(f"`{i.symbol_name}`" for i in doc_items)
        overview = (
            f"Module `{target_file}` defines {len(doc_items)} core symbol(s) ({symbol_names}) "
            f"and integrates {len(extractor.imports)} module dependency import(s)."
        )

        # 5. Optional Online LLM Enhancement
        is_mock = (
            force_offline
            or not self.settings.OPENAI_API_KEY
            or self.settings.OPENAI_API_KEY.startswith("sk-placeholder")
        )

        if not is_mock and source_code:
            headers = {
                "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": DOC_AGENT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"File: {target_file}\nDoc Format: {doc_format.value}\n"
                            f"Diagram Type: {request.diagram_type.value}\nCode:\n{source_code}"
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = json.loads(data["choices"][0]["message"]["content"])
                    overview = parsed.get("module_overview", overview)
                    if request.include_mermaid and parsed.get("mermaid_diagram"):
                        mermaid_str = parsed["mermaid_diagram"]
                    llm_syms = [
                        ModuleDocItem(
                            symbol_name=s.get("symbol_name", "symbol"),
                            symbol_type=s.get("symbol_type", "function"),
                            signature=s.get("signature", ""),
                            generated_docstring=s.get("generated_docstring", ""),
                            summary=s.get("summary", ""),
                        )
                        for s in parsed.get("documented_symbols", [])
                    ]
                    if llm_syms:
                        doc_items = llm_syms
                    md_doc = self.assemble_markdown(
                        request.repo_id, target_file, overview, doc_items, mermaid_str
                    )
                    return DocGenResponse(
                        repo_id=request.repo_id,
                        target_file=target_file,
                        doc_format=doc_format,
                        module_overview=overview,
                        documented_symbols=doc_items,
                        mermaid_diagram=mermaid_str,
                        markdown_documentation=md_doc,
                        model_used=self.settings.OPENAI_MODEL,
                    )
            except Exception as e:
                logger.warning(f"LLM Documentation Generation failed: {e}; using AST doc synthesizer.")

        md_doc = self.assemble_markdown(
            request.repo_id, target_file, overview, doc_items, mermaid_str
        )
        return DocGenResponse(
            repo_id=request.repo_id,
            target_file=target_file,
            doc_format=doc_format,
            module_overview=overview,
            documented_symbols=doc_items,
            mermaid_diagram=mermaid_str,
            markdown_documentation=md_doc,
            model_used="ast-doc-synthesizer",
        )


doc_agent_service = DocAgentService()
