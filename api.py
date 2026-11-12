import os
import sys
import json
import tempfile
import pathlib
import threading
import webbrowser
import uvicorn
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend_class import DocCreate
import sel_analyzer
from ai_describer import improve_text, AIUnavailable

def resource_path(relative_path):
    """ Garante que o caminho funcione tanto no PyCharm quanto no .exe (PyInstaller) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Caminhos das imagens do cabeçalho (funciona no Python e no .exe gerado pelo PyInstaller)
logo_eqtl_path_tex = pathlib.Path(resource_path(os.path.join("assets", "equatorial_logo.png"))).as_posix()
logo_leao_at_path_tex = pathlib.Path(resource_path(os.path.join("assets", "Leao_AT.png"))).as_posix()

@app.post("/gerar-documento")
async def gerar_documento(
        data: str = Form(...),
        images: list[UploadFile] = File(default=[]),
        image_titles: list[str] = Form(default=[]),
        image_descriptions: list[str] = Form(default=[])
):
    json_data = json.loads(data)
    temp_dir = tempfile.mkdtemp()

    paths_imagens = []
    for i, img in enumerate(images):
        ext = os.path.splitext(img.filename)[1]
        safe_img_name = f"anexo_{i}{ext}"
        img_path = os.path.join(temp_dir, safe_img_name)
        with open(img_path, "wb") as f:
            f.write(await img.read())
        paths_imagens.append(pathlib.Path(img_path).as_posix())

    doc = DocCreate("Documentação Técnica")
    doc.header(f"Aplicação Especial {json_data['Código da Documentação']}",
               logo_eqtl_path_tex, logo_leao_at_path_tex, 1.5)
    doc.tittle(json_data['Titulo da Documentação'])
    doc.doc_identification_section(json_data['Nome do Projeto'], json_data['Data de Alteração'], json_data['Responsável Técnico'], json_data['Revisão'])
    doc.list_itemsize_section("Referências Técnicas", json_data['Referências Técnicas'])
    doc.text_section("Objetivo", json_data['Objetivo'])
    doc.list_itemsize_section("Escopo do Projeto", json_data['Escopo do Projeto'])
    doc.sequence_section("Requisitos", json_data['Requisitos'])
    doc.rich_text_section("Descrição da Lógica", json_data['Descrição Detalhada'])
    doc.table_section("Adaptações Lógicas", "n", "", ["Equipamento", "Variável", "Equação Lógica", "Descrição"], json_data['Adaptações Lógicas'], 'ADAPTAÇÕES LÓGICAS')
    doc.table_section("Matriz GOOSE", 'y', "Sinais GOOSE", ["Publicador", "Assinante", "MAC Mensagem", "Virtual Bit", "Variável"], json_data['Matriz GOOSE'], 'MATRIZ GOOSE')
    doc.table_section("Sinalizações", 'y', "Sinais Utilizados", ["Equipamento", "Tipo do Ponto", "Variável", "Descrição", "Funcionamento"], json_data['Sinalizações'], 'SINALIZAÇÕES')
    doc.table_section("Testes Realizados", 'n', "", ["ID", "Cenário", "Resultado Esperado"], json_data['Testes de Validação'], 'TESTES REALIZADOS')
    doc.figure("Anexos", paths_imagens, image_titles, image_descriptions)

    safe_filename = "documento_compilado_seguro"
    doc.pdf_generator(json_data['Compilador'], temp_dir, safe_filename, json_data)

    pdf_filepath = os.path.join(temp_dir, f"{safe_filename}.pdf")
    return FileResponse(pdf_filepath, filename=f"{json_data['Nome do Arquivo']}.pdf")

@app.post("/analisar-arquivos")
async def analisar_arquivos(
        rdb_backup: UploadFile | None = File(default=None),
        rdb_novo: UploadFile | None = File(default=None),
        scd_backup: UploadFile | None = File(default=None),
        scd_novo: UploadFile | None = File(default=None),
):
    """Lê .rdb/.scd (backup e novo) e monta as tabelas de lógicas, GOOSE e sinalizações (mapa DNP)."""
    async def ler(arquivo):
        return await arquivo.read() if arquivo is not None and arquivo.filename else None

    if rdb_novo is None or not rdb_novo.filename:
        raise HTTPException(status_code=400, detail="Envie pelo menos o arquivo .rdb novo.")
    try:
        analise = sel_analyzer.analyze(await ler(rdb_backup), await ler(rdb_novo),
                                       await ler(scd_backup), await ler(scd_novo))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "logica": [{k: v for k, v in row.items() if k != "id"} for row in analise["logic_rows"]],
        "goose": analise["goose_rows"],
        "sinalizacoes": analise["signal_rows"],
        "avisos": analise["warnings"],
        "reles": analise["relays"],
        "ieds": analise["ieds"],
    }


@app.post("/melhorar-texto")
async def melhorar_texto(texto: str = Form(...)):
    """Revisa a Descrição Detalhada (gramática e linguagem técnica) sem alterar o conteúdo."""
    if not texto.strip():
        raise HTTPException(status_code=400, detail="O texto está vazio.")
    try:
        resultado = await run_in_threadpool(improve_text, texto)
    except AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Não foi possível revisar o texto: {exc}.")
    return {"texto": resultado["texto"], "modelo": resultado["modelo"]}


# ==============================================================
# CONFIGURAÇÃO DO FRONTEND (REACT)
# ==============================================================
dist_path = resource_path("dist")
assets_path = os.path.join(dist_path, "assets")

if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    return FileResponse(os.path.join(dist_path, "index.html"))

def open_browser():
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    # Abre o navegador automaticamente após 1.5 segundos
    threading.Timer(1.5, open_browser).start()
    # Inicia o servidor local
    uvicorn.run(app, host="127.0.0.1", port=8000)