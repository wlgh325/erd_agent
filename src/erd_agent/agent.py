from __future__ import annotations
from pathlib import Path
import typer
from rich.console import Console

from erd_agent.config import settings
from erd_agent.repo import prepare_repo
from erd_agent.scanner import scan_repo
from erd_agent.model import Schema
from erd_agent.parsers.jpa_java import JPAJavaParser
from erd_agent.normalize import normalize_schema
from erd_agent.dbml_writer import write_dbml
from erd_agent.docs_writer import write_summary_md

# Azure OpenAI 옵션
from erd_agent.llm.schema_refiner import refine_schema_with_aoai

app = typer.Typer(add_completion=False)
console = Console()

def load_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

@app.command()
def generate(
    repo: str = typer.Argument(..., help="로컬 경로 또는 https git URL"),
    out_dbml: str = typer.Option("database.dbml", help="출력 DBML 파일명"),
    out_md: str = typer.Option("erd_summary.md", help="출력 요약 MD 파일명"),
    use_aoai: bool = typer.Option(False, help="Azure OpenAI로 스키마 보정(옵션)"),
):
    repo_path = prepare_repo(repo)
    console.print(f"[bold]Repo:[/bold] {repo_path}")

    files = scan_repo(repo_path)
    console.print(f"Found [green]{len(files)}[/green] JPA candidates")

    schema = Schema()
    parsers = [JPAJavaParser()]

    for f in files:
        text = load_text(f)
        for p in parsers:
            if p.can_parse(f, text):
                p.parse(f, text, schema)

    normalize_schema(schema)

    if use_aoai:
        console.print("[yellow]Refining with Azure OpenAI (optional)[/yellow]")
        schema = refine_schema_with_aoai(schema)
        normalize_schema(schema)

    settings.erd_output_dir.mkdir(parents=True, exist_ok=True)
    dbml_path = settings.erd_output_dir / out_dbml
    md_path = settings.erd_output_dir / out_md

    write_dbml(schema, dbml_path)
    write_summary_md(schema, md_path)

    console.print(f"[bold green]DBML:[/bold green] {dbml_path}")
    console.print(f"[bold green]MD:[/bold green]   {md_path}")

if __name__ == "__main__":
    app()