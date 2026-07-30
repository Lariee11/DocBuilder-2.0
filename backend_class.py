from pylatex import Document, Package, NoEscape, Section, Itemize, Table, Tabular, Center, Enumerate, Figure, Tabularx
import os
from pylatex.utils import escape_latex
import json
from pathlib import Path

def sanitize(text):
    """Escapa caracteres reservados do LaTeX para não quebrar a compilação."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return escape_latex(text)

class DocCreate:
    def __init__(self, doc_name):
        self.doc_name = doc_name
        self.geometry_options = {
                "top": "3cm",
                "bottom": "2.5cm",
                "left": "1cm",
                "right": "1cm",
                "headheight": "40pt",
                "headsep": "1.2cm"}

        self.doc = Document(self.doc_name, geometry_options=self.geometry_options)
        self.doc.packages.append(Package('babel', options='portuguese'))
        self.doc.packages.append(Package('fancyhdr'))
        self.doc.packages.append(Package('graphicx'))
        self.doc.packages.append(Package('caption'))
        self.doc.packages.append(Package('float'))
        self.doc.packages.append(Package('tabularx'))
        self.doc.packages.append(Package('parskip'))

        self.doc.preamble.append(NoEscape(r'\setlength{\parindent}{0pt}'))
        self.doc.preamble.append(NoEscape(r'\pagestyle{fancy}'))
        self.doc.preamble.append(NoEscape(r'\fancyhf{}'))
        self.doc.preamble.append(NoEscape(r'\captionsetup[figure]{position=above}'))
        self.doc.preamble.append(NoEscape(r'\fancyfoot[R]{\thepage}'))

    def header(self, type_document, image_left, image_right, images_size):
        """ Cria o cabeçalho da documentação com o tipo seguindo o padrão """
        self.doc.preamble.append(NoEscape(
            rf'\fancyhead[L]{{\includegraphics[height=1.5cm]{{{image_left}}}}}'
        ))
        self.doc.preamble.append(NoEscape(
            rf'\fancyhead[R]{{\large\textbf{{{type_document}}}\hspace{{0.5em}}\includegraphics[height={images_size}cm]{{{image_right}}}}}'
        ))

    def tittle(self, tittle):
        """ Adiciona um título na documentação """

        self.doc.append(NoEscape(r'\vspace{3cm}'))
        self.doc.append(NoEscape(fr'''
            \begin{{center}}
                \LARGE \textbf{{{tittle}}}
            \end{{center}}
            '''))

    def doc_identification_section(self, aplication, date, responsable, version_doc):
        """ Cria uma seção de identificação da documentação """

        with self.doc.create(Section("Identificação do Documento")):
            with self.doc.create(Itemize()) as itemize:
                itemize.add_item(NoEscape(f"\\textbf{{Distribuidora}}: {aplication}"))
                itemize.add_item(NoEscape(f"\\textbf{{Data}}: {date}"))
                itemize.add_item(NoEscape(f"\\textbf{{Responsável Técnico}}: {responsable}"))
                itemize.add_item(NoEscape(f"\\textbf{{Revisão}}: {version_doc}"))

    def list_itemsize_section(self, section_name, strings_list):
        """ Cria uma seção com uma lista de strings """

        with self.doc.create(Section(section_name)):
            if len(strings_list) > 0:
                with self.doc.create(Itemize()) as itemize:
                    for a in range(len(strings_list)):
                        itemize.add_item(NoEscape(f"{strings_list[a]}"))
            else:
                self.doc.append(NoEscape("Não se Aplica."))


    def text_section(self, section_name, text):
        """ Cria um seção com um texto descrito """

        with self.doc.create(Section(section_name)):
            self.doc.append(NoEscape(text))

    def table_section(self, section_name: str, tittle_y_or_n: str, table_title: str,
                      columns_names: list, lista_dicts: list, name_table: str):
        """ Cria uma seção com uma tabela longa que quebra de página nativamente sem bugs """

        # Importa a classe necessária diretamente da biblioteca pylatex
        from pylatex import LongTable

        columns_quantity = len(columns_names)
        with self.doc.create(Section(section_name)):
            if len(lista_dicts) > 0:
                # Inclui os pacotes necessários
                self.doc.packages.append(Package('array'))
                self.doc.packages.append(Package('booktabs'))

                # Removemos o 'ltablex'. O LongTable cuida de tudo nativamente.

                # Calcula dinamicamente o tamanho proporcional de cada coluna baseando-se no número de colunas
                # Exemplo: Se forem 4 colunas, cada uma terá 0.23 da largura da página (deixando margem para as bordas '|')
                width_per_column = round((1.0 / columns_quantity) - 0.02, 2)

                if columns_quantity == 2:
                    # Se tiver apenas duas colunas, fixa a primeira na esquerda e estica a segunda
                    column_format = NoEscape(r'| l | >{\raggedright\arraybackslash}p{0.75\linewidth} |')
                else:
                    # Define colunas do tipo 'p' (parágrafo), que quebram linha sozinhas baseado no tamanho calculado
                    spec = f'| >{{\\raggedright\\arraybackslash}}p{{{width_per_column}\\linewidth}} ' * columns_quantity + '|'
                    column_format = NoEscape(spec)

                # Cria o ambiente LongTable diretamente
                tab = LongTable(column_format)

                # Aplica o tamanho da fonte antes da tabela
                self.doc.append(NoEscape(r'\small'))

                with self.doc.create(tab) as tabela_interna:
                    # Legenda da tabela no topo (O LongTable aceita legenda como se fosse uma linha)
                    if tittle_y_or_n == 'y':
                        tabela_interna.append(NoEscape(f'\\caption{{{table_title}}} \\\\'))

                    tabela_interna.add_hline()
                    # Cabeçalho da Tabela
                    header_row = [NoEscape(r'\textbf{' + nome + '}') for nome in columns_names]
                    tabela_interna.add_row(header_row)
                    tabela_interna.add_hline()

                    # Comando nativo do LaTeX: Repete esse cabeçalho no topo de cada página que a tabela quebrar
                    tabela_interna.append(NoEscape(r'\endhead'))

                    # Popula as linhas com os dicionários
                    for item in lista_dicts:
                        row = [item.get(col, '') for col in columns_names]
                        tabela_interna.add_row(row)
                        tabela_interna.add_hline()
            else:
                # Caso a tabela esteja vazia
                self.doc.append(NoEscape("Não se Aplica."))

    def sequence_section(self, section_tittle, sequence_list):
        """ Cria uma seção com uma sequência enumerada """

        with self.doc.create(Section(section_tittle)):
            with self.doc.create(Enumerate()) as sequence:
                for item in sequence_list:
                    sequence.add_item(item)

    def pdf_generator(self, pdflatex, folder_diretory, doc_name, json_data):
        """ Gera a documentação em PDF """
        folder_path = Path(folder_diretory)
        filepath = folder_path / doc_name
        json_path = folder_path / f"{doc_name}.json"

        # Apenas filepath, clean_tex e compiler
        self.doc.generate_pdf(
            filepath=filepath,
            clean_tex=False,
            compiler=rf"{pdflatex}"
        )

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)

    def figure(self, section_name, figures_paths_list, figure_tittles_list, figure_descriptions_list):
        """ Gera a seção de anexos, com as imagens, títulos e descrições """
        if len(figures_paths_list) > 0:
            with self.doc.create(Section(section_name)):
                for a in range(len(figures_paths_list)):
                    with self.doc.create(Figure(position='H')) as image:
                        # Sanitiza o título
                        image.add_caption(sanitize(figure_tittles_list[a]))

                        image.add_image(figures_paths_list[a], width=NoEscape(r'0.8\linewidth'))
                        self.doc.append(NoEscape(r'\par'))

                        # Sanitiza a descrição
                        self.doc.append(sanitize(figure_descriptions_list[a]))
