#!/usr/bin/env python3
"""Render a DOCX and bind the actual renderer, PDF and every page to that input.

This command always invokes the supplied renderer in a new, empty output
folder. There is intentionally no command to certify a pre-existing render.
Visual judgment remains a separate, actual page inspection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MIN_SHORT_EDGE = 600
MIN_LONG_EDGE = 1000


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dependencies():
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow is required; use the Codex bundled Python runtime") from exc
    try:
        import fitz
        return "fitz",fitz,Image
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PyMuPDF or pypdf is required to read the actual PDF page count") from exc
        return "pypdf",PdfReader,Image


def inside(directory: Path, value: str) -> Path:
    path = (directory / value).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError(f"render artifact escapes output directory: {value}")
    return path


def inspect_artifacts(directory: Path, pdf_path: Path) -> tuple[dict, list[dict]]:
    backend,reader,Image=dependencies()
    if backend=="fitz":
        with reader.open(pdf_path) as pdf:
            if pdf.page_count<1 or pdf.is_encrypted:
                raise ValueError("rendered PDF is empty or encrypted")
            sizes=[{"widthPoints":page.rect.width,"heightPoints":page.rect.height} for page in pdf]
            page_count=pdf.page_count
    else:
        pdf=reader(str(pdf_path))
        if pdf.is_encrypted or len(pdf.pages)<1:
            raise ValueError("rendered PDF is empty or encrypted")
        sizes=[]
        for page in pdf.pages:
            width,height=float(page.cropbox.width),float(page.cropbox.height)
            if int(page.get("/Rotate",0))%180:
                width,height=height,width
            sizes.append({"widthPoints":width,"heightPoints":height})
        page_count=len(pdf.pages)
    images = sorted(directory.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)",p.stem)[1]) if re.search(r"(\d+)",p.stem) else 0)
    if [p.name for p in images] != [f"page-{i}.png" for i in range(1,page_count+1)]:
        raise ValueError("rendered PNG pages must exactly cover the PDF's true page count")
    pages=[]
    for number, path in enumerate(images,1):
        if path.is_symlink():
            raise ValueError("rendered pages must be actual files in this output directory")
        with Image.open(path) as im:
            if im.format != "PNG":
                raise ValueError(f"page {number} is not a PNG")
            im.load()
            width, height = im.size
        if min(width,height)<MIN_SHORT_EDGE or max(width,height)<MIN_LONG_EDGE:
            raise ValueError(f"page {number} is too small for visual QA ({width}x{height}); placeholder images are not renders")
        size=sizes[number-1]
        expected=size["widthPoints"]/size["heightPoints"]
        if abs((width/height)/expected-1)>0.02:
            raise ValueError(f"page {number} dimensions do not match the PDF page aspect ratio")
        pages.append({"number":number,"path":path.name,"sha256":digest(path),"width":width,"height":height})
    return {"path":pdf_path.name,"sha256":digest(pdf_path),"pageCount":page_count,"pages":sizes}, pages


def verify_render_manifest(docx: Path, manifest_path: Path, render_directory: Path | None = None) -> list[str]:
    """Read-only verification of current DOCX, renderer, PDF and complete page set."""
    errors=[]
    try:
        docx=docx.expanduser().resolve()
        manifest_path=manifest_path.expanduser().resolve()
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest,dict) or manifest.get("schemaVersion")!="1.0.0" or manifest.get("status")!="rendered":
            return ["missing or invalid actual render manifest"]
        directory=manifest_path.parent
        if manifest_path.name!="render-manifest.json" or Path(manifest.get("outputDirectory","")).resolve()!=directory:
            errors.append("render manifest must reside in its actual output directory")
        if render_directory is not None and render_directory.expanduser().resolve()!=directory:
            errors.append("visual QA directory differs from the render manifest directory")
        source=manifest.get("inputDocx",{})
        if source.get("sha256")!=digest(docx):
            errors.append("render manifest belongs to a different or changed DOCX")
        renderer=manifest.get("renderer",{})
        renderer_path=Path(renderer.get("path","")).expanduser().resolve()
        if not renderer_path.is_file() or renderer.get("sha256")!=digest(renderer_path):
            errors.append("actual renderer is missing or has changed")
        python_path=Path(manifest.get("pythonExecutable","")).expanduser().resolve()
        command=manifest.get("command")
        source_path=Path(source.get("path","")).expanduser().resolve()
        expected=[str(python_path),str(renderer_path),str(source_path),"--output_dir",str(directory),"--emit_pdf"]
        if command!=expected or manifest.get("returnCode")!=0 or not manifest.get("startedAt") or not manifest.get("completedAt"):
            errors.append("render manifest is missing its successful actual command")
        pdf_info=manifest.get("pdf",{})
        pdf_path=inside(directory,pdf_info.get("path","missing.pdf"))
        if not pdf_path.is_file() or pdf_path.is_symlink():
            errors.append("actual rendered PDF is missing")
        else:
            actual_pdf, actual_pages=inspect_artifacts(directory,pdf_path)
            if pdf_info!=actual_pdf:
                errors.append("rendered PDF hash, true page count or page geometry changed")
            if manifest.get("pages")!=actual_pages:
                errors.append("rendered page hashes, dimensions or coverage changed")
    except Exception as exc:
        # PDF/image decoders use backend-specific exceptions for corrupt files.
        # Treat unreadable evidence as a failed gate, never a successful render.
        errors.append(f"render evidence invalid: {exc}")
    return errors


def render(docx: Path, renderer: Path, output_dir: Path) -> Path:
    docx=docx.expanduser().resolve()
    renderer=renderer.expanduser().resolve()
    output_dir=output_dir.expanduser().resolve()
    if not docx.is_file() or docx.suffix.lower()!=".docx":
        raise ValueError("input must be an existing DOCX")
    if not renderer.is_file() or renderer.suffix.lower()!=".py":
        raise ValueError("--renderer must be the actual bundled render_docx.py file")
    if output_dir.exists():
        raise FileExistsError("output directory already exists; choose a new directory for a fresh actual render")
    output_dir.mkdir(parents=True,exist_ok=False)
    input_hash, renderer_hash=digest(docx), digest(renderer)
    executable=Path(sys.executable).resolve()
    command=[str(executable),str(renderer),str(docx),"--output_dir",str(output_dir),"--emit_pdf"]
    started=now()
    result=subprocess.run(command,text=True,capture_output=True)
    (output_dir/'renderer.stdout.log').write_text(result.stdout,encoding="utf-8")
    (output_dir/'renderer.stderr.log').write_text(result.stderr,encoding="utf-8")
    if result.returncode:
        raise ValueError(f"renderer failed with exit {result.returncode}; see {output_dir/'renderer.stderr.log'}")
    if digest(docx)!=input_hash or digest(renderer)!=renderer_hash:
        raise ValueError("DOCX or renderer changed during rendering; no manifest issued")
    pdf_path=output_dir/(docx.stem+".pdf")
    if not pdf_path.is_file():
        raise ValueError("renderer did not produce the requested PDF; no manifest issued")
    pdf,pages=inspect_artifacts(output_dir,pdf_path)
    manifest={"schemaVersion":"1.0.0","status":"rendered","inputDocx":{"path":str(docx),"sha256":input_hash},
              "renderer":{"path":str(renderer),"sha256":renderer_hash},"pythonExecutable":str(executable),
              "command":command,"returnCode":result.returncode,"startedAt":started,"completedAt":now(),
              "outputDirectory":str(output_dir),"pdf":pdf,"pages":pages}
    path=output_dir/'render-manifest.json'
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    errors=verify_render_manifest(docx,path,output_dir)
    if errors:
        path.unlink(missing_ok=True)
        raise ValueError("; ".join(errors))
    return path


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx",type=Path)
    parser.add_argument("--renderer",required=True,type=Path,help="Actual bundled documents/render_docx.py")
    parser.add_argument("--output-dir",required=True,type=Path,help="New directory; pre-existing output cannot be certified")
    args=parser.parse_args()
    try:
        manifest=render(args.docx,args.renderer,args.output_dir)
        print(json.dumps({"status":"rendered","renderManifest":str(manifest)},ensure_ascii=False))
        return 0
    except (OSError,ValueError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    raise SystemExit(main())
