from frontend_class import DocBuilder
from backend_class import DocCreate
import flet as ft
import os
import pathlib
import sys


def resource_path(relative_path):
    """
    Garante que o caminho funcione tanto no PyCharm quanto no .exe (PyInstaller)
    """
    try:
        # Quando rodando no .exe
        base_path = sys._MEIPASS
    except Exception:
        # Quando rodando no PyCharm
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    return os.path.join(base_path, relative_path)

# IMAGENS DO PROJETO
banner_path = resource_path(os.path.join("assets", "docbuilder_banner.jpg"))
logo_eqtl_path = resource_path(os.path.join("assets", "equatorial_logo.png"))
logo_leao_at_path = resource_path(os.path.join("assets", "Leao_AT.png"))

# Caminhos para usar no LaTeX
logo_eqtl_path_tex = pathlib.Path(logo_eqtl_path).as_posix()
logo_leao_at_path_tex = pathlib.Path(logo_leao_at_path).as_posix()

def load_app(page: ft.Page):
    """ Página Inicial do Aplicativo """
    json = {}

    app = DocBuilder(page, "DocBuilder", '#1E293D')
    app.banner(banner_path)

    # Inputs do Cabeçalho da Documentação
    loc_pdflatex_text_box = app.big_text_input("Endereço do Compilador pdflatex")
    titulo_text_box = app.simple_text_input("Título da Documentação")
    nome_arquivo_text_box = app.simple_text_input("Nome do Arquivo")
    codigo_documentacao_text_box = app.simple_text_input("Codigo do Documento")

    # Seção 1
    app.tittle_section("Identificações do Projeto")
    nome_projeto_text_box = app.simple_text_input("Distribuidora")
    data_text_box = app.simple_text_input("Data da Ultima Edição DD/MM/AAAA")
    responsavel_text_box = app.simple_text_input("Responsável Técnico")
    versao_documento_text_box = app.simple_text_input("Revisão")

    # Seção 2
    app.tittle_section("Referências Técnicas")
    referencias_text_box = app.write_quantity_text_box("")

    # Seção 3
    app.tittle_section("Objetivo do Projeto")
    objetivo_text_box = app.big_text_input("")

    # Seção 4
    app.tittle_section("Escopo do Projeto")
    escopo_text_box = app.write_quantity_text_box("")

    # Seção 5
    app.tittle_section("Requisitos")
    requisitos_text_box = app.write_quantity_text_box("")

    # Seção 6
    app.tittle_section("Descrição Detalhada da Lógica")
    descricao_detalhada_text_box = app.big_text_input("")

    # Seção 7
    app.tittle_section("Adaptações Lógicas")
    tabela_adaptacoes_logicas, nomes_colunas_adaptacoes, adaptacoes_table = app.table_with_text_boxs(
        4, ["Equipamento", "Variável", "Equação Lógica", "Descrição"]
    )

    # Seção 8
    app.tittle_section("Matriz GOOSE")
    tabela_de_gooses, nomes_colunas_sinais, gooses_table = app.table_with_text_boxs(
        5, ["Publicador", "Assinante", "MAC Mensagem", "Virtual Bit", "Variável"]
    )

    # Seção 9
    app.tittle_section("Sinalizações")
    tabela_de_sinalizacoes, nome_coluna_sinalizacoes, sinalizacoes_table = app.table_with_text_boxs(
        5, ["Equipamento", "Tipo do Ponto", "Variável", "Descrição", "Funcionamento"]
    )

    # Seção 10
    app.tittle_section("Testes de Validação")
    testes_de_validacao_table, nomes_colunas_testes, testes_table = app.table_with_text_boxs(
        3, ["ID", "Cenário", "Resultado Esperado"]
    )

    # Seção 11
    app.tittle_section("Anexos")
    localizacao_imagens_list, titulos_imagens_text_box, descricoes_imagens_text_box = (
        app.image_attachment_and_description("Título", "Descrição")
    )

    def criar_documento(e):
        """ Database da Documentação """
        compilador = loc_pdflatex_text_box.value
        nome_arquivo = nome_arquivo_text_box.value
        nome_projeto = nome_projeto_text_box.value
        codigo_projeto = codigo_documentacao_text_box.value
        titulo_documentacao = titulo_text_box.value
        data = data_text_box.value
        responsavel_tecnico = responsavel_text_box.value
        versao = versao_documento_text_box.value
        objetivo = objetivo_text_box.value
        descricao = descricao_detalhada_text_box.value

        referencias_tecnicas = [item.value for item in referencias_text_box]
        escopo = [item.value for item in escopo_text_box]
        requisitos = [item.value for item in requisitos_text_box]

        sinalizacoes = [
            {"Equipamento": linha[0].value,
             "Tipo do Ponto": linha[1].value,
             "Variável": linha[2].value,
             "Descrição": linha[3].value,
             "Funcionamento": linha[4].value}
            for linha in tabela_de_sinalizacoes
        ]

        tabela_adaptacoes = [
            {"Equipamento": linha[0].value,
             "Variável": linha[1].value,
             "Equação Lógica": linha[2].value,
             "Descrição": linha[3].value}
            for linha in tabela_adaptacoes_logicas
        ]

        tabela_sinais = [
            {"Publicador": linha[0].value,
             "Assinante": linha[1].value,
             "MAC Mensagem": linha[2].value,
             "Virtual Bit": linha[3].value,
             "Variável": linha[4].value}
            for linha in tabela_de_gooses
        ]

        tabela_testes_realizados = [
            {"ID": linha[0].value,
             "Cenário": linha[1].value,
             "Resultado Esperado": linha[2].value}
            for linha in testes_de_validacao_table
        ]

        paths_imagens, descricoes_imagens, titulos_imagens = [], [], []
        for path_imagem, titulo_box, descricao_box in zip(localizacao_imagens_list,
                                                          titulos_imagens_text_box,
                                                          descricoes_imagens_text_box):
            paths_imagens.append(path_imagem)
            titulos_imagens.append(titulo_box.value)
            descricoes_imagens.append(descricao_box.value)

        json = {
            "Compilador": compilador,
            "Titulo da Documentação": titulo_documentacao,
            "Nome do Arquivo": nome_arquivo,
            "Nome do Projeto": nome_projeto,
            "Código da Documentação": codigo_projeto,
            "Data de Alteração": data,
            "Responsável Técnico": responsavel_tecnico,
            "Revisão": versao,
            "Referências Técnicas": referencias_tecnicas,
            "Objetivo": objetivo,
            "Escopo do Projeto": escopo,
            "Requisitos": requisitos,
            "Descrição Detalhada": descricao,
            "Adaptações Lógicas": tabela_adaptacoes,
            "Matriz GOOSE": tabela_sinais,
            "Sinalizações": sinalizacoes,
            "Testes de Validação": tabela_testes_realizados,
        }

        if not app.selected_folder:
            return
        diretorio_selecionado = app.selected_folder
        print("Arquivos serão salvos em:", diretorio_selecionado)

        doc = DocCreate("Documentação Técnica")
        doc.header(f"Aplicação Especial {codigo_projeto}",
                   logo_eqtl_path_tex,
                   logo_leao_at_path_tex,
                   1.5)
        doc.tittle(titulo_documentacao)

        doc.doc_identification_section(nome_projeto, data, responsavel_tecnico, versao)
        doc.list_itemsize_section("Referências Técnicas", referencias_tecnicas)
        doc.text_section("Objetivo", objetivo)
        doc.list_itemsize_section("Escopo do Projeto", escopo)
        doc.sequence_section("Requisitos", requisitos)
        doc.text_section("Descrição da Lógica", descricao)

        doc.table_section("Adaptações Lógicas", "n", "",
                          nomes_colunas_adaptacoes, tabela_adaptacoes, 'ADAPTAÇÕES LÓGICAS')

        doc.table_section("Matriz GOOSE", 'y', "Sinais GOOSE",
                          nomes_colunas_sinais, tabela_sinais, 'MATRIZ GOOSE')

        doc.table_section("Sinalizações", 'y', "Sinais Utilizados",
                          ["Equipamento", "Tipo do Ponto", "Variável", "Descrição", "Funcionamento"],
                          sinalizacoes, 'SINALIZAÇÕES')

        doc.table_section("Testes Realizados", 'n', "",
                          ["ID", "Cenário", "Resultado Esperado"],
                          tabela_testes_realizados, 'TESTES REALIZADOS')

        doc.figure("Anexos", paths_imagens, titulos_imagens, descricoes_imagens)

        doc.pdf_generator(loc_pdflatex_text_box.value,
                          diretorio_selecionado,
                          nome_arquivo,
                          json)

    # Botão para gerar a documentação
    app.doc_generate_button(criar_documento, "Gerar Documentação")

    # Botão para selecionar diretório
    app.select_folder_button()

    def apos_carregamento(quantidade_linhas):
        print(quantidade_linhas)

    # Preenchimento das lacunas pelo arquivo JSON selecionado
    app.load_from_json(json,
                       loc_pdflatex_text_box,
                       titulo_text_box,
                       nome_arquivo_text_box,
                       nome_projeto_text_box,
                       codigo_documentacao_text_box,
                       data_text_box,
                       responsavel_text_box,
                       versao_documento_text_box,
                       referencias_text_box,
                       objetivo_text_box,
                       escopo_text_box,
                       requisitos_text_box,
                       descricao_detalhada_text_box,
                       tabela_adaptacoes_logicas, ["Equipamento", "Variável", "Equação Lógica", "Descrição"], adaptacoes_table,
                       tabela_de_gooses, ["Publicador", "Assinante", "MAC Mensagem", "Virtual Bit", "Variável"], gooses_table,
                       tabela_de_sinalizacoes, ["Equipamento", "Tipo do Ponto", "Variável", "Descrição", "Funcionamento"], sinalizacoes_table,
                       testes_de_validacao_table, ["ID", "Cenário", "Resultado Esperado"], testes_table,
                       on_loaded=apos_carregamento)


ft.app(target=load_app)
