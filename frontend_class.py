import flet as ft
import json


class DocBuilder:
    def __init__(self, page: ft.Page, software_name, page_color):
        self.page = page
        self.page.window_maximized = True
        self.page.window_full_screen = True
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.theme_mode = "light"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.title = software_name
        self.page.bgcolor = page_color
        self.selected_folder = None
        self.number_lists_lines = None
        self.page.update()

    def banner(self, image_name):
        self.page.add(ft.Image(src=image_name, width=400, height=200))
        self.page.update()

    def tittle_section(self, name):
        tittle = ft.Text(name, size=20, color='white')
        self.page.add(tittle)
        self.page.update()

    def simple_text_input(self, name_box):
        box = ft.TextField(label=name_box, width=400, border_color='black', multiline=True,
                           bgcolor='white', border_width=2,
                           label_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.page.add(box)
        self.page.update()
        return box

    @staticmethod
    def accept_numbers_only(e):
        valor_filtrado = ''.join(filter(str.isdigit, e.control.value))
        if e.control.value != valor_filtrado:
            e.control.value = valor_filtrado
            e.control.update()

    def write_quantity_text_box(self, box_names):
        container_button = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        container_text_boxs = ft.Column()
        boxs = []

        text_box = ft.TextField(label="Quantidade",
                                width=130,
                                border_color='black', bgcolor='white', border_width=2,
                                label_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                                keyboard_type=ft.KeyboardType.NUMBER,
                                on_change=self.accept_numbers_only)
        container_button.controls.append(text_box)

        def text_boxs_columns_create(e):
            quantity = int(text_box.value)
            for a in range(int(quantity)):
                box = ft.TextField(label=box_names, width=400, border_color='black', multiline=True,
                                   bgcolor='white', border_width=2,
                                   label_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
                container_text_boxs.controls.append(box)
                boxs.append(box)
            self.page.update()

        button = ft.ElevatedButton(text="+", color='black', bgcolor='white', on_click=text_boxs_columns_create)

        container_button.controls.append(button)
        self.page.add(container_button)
        self.page.add(container_text_boxs)
        self.page.update()
        return boxs

    def big_text_input(self, name_box):
        text_input = ft.TextField(label=name_box, multiline=True, expand=True, width=800,
                                  border_color='black', bgcolor='white', border_width=2,
                                  label_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        self.page.add(text_input)
        self.page.update()
        return text_input

    def table_with_text_boxs(self, columns_quantity: int, columns_names: list):
        text_boxs_table = []
        container_input_quantity_select = ft.Row(alignment=ft.MainAxisAlignment.CENTER)

        box = ft.TextField(
            label="Quantidade",
            width=130,
            border_color='black',
            bgcolor='white',
            border_width=2,
            label_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self.accept_numbers_only
        )
        table = ft.DataTable(
            border=ft.border.all(1, ft.Colors.BLACK),
            bgcolor=ft.Colors.WHITE,
            vertical_lines=ft.border.BorderSide(1, ft.Colors.BLACK),
            horizontal_lines=ft.border.BorderSide(1, ft.Colors.BLACK),
            heading_row_color=ft.Colors.GREY,
            columns=[
                ft.DataColumn(ft.Text(columns_names[i], width=300, text_align=ft.TextAlign.CENTER))
                for i in range(columns_quantity)
            ])

        def create_table_rows(e):
            quantity = int(box.value) if box.value else 0
            for a in range(quantity):
                table_cells = []
                row_textboxes = []
                for b in range(columns_quantity):
                    text_box = ft.TextField(label="", color='black', border_color='white')
                    table_cells.append(ft.DataCell(text_box))
                    row_textboxes.append(text_box)
                text_boxs_table.append(row_textboxes)
                new_line = ft.DataRow(cells=table_cells)
                table.rows.append(new_line)
            self.page.update()

        button = ft.ElevatedButton(
            text="+",
            color='black',
            bgcolor='white',
            on_click=create_table_rows
        )

        container_input_quantity_select.controls.append(box)
        container_input_quantity_select.controls.append(button)

        self.page.add(container_input_quantity_select)
        self.page.add(table)
        self.page.update()
        return text_boxs_table, columns_names, table

    def fill_table_from_json(self, table, table_textboxes, columns_names, data_list):
        """Cria linhas na DataTable de acordo com o JSON e preenche os valores"""
        for item in data_list:
            row_textboxes = []
            table_cells = []
            for col in columns_names:
                text_box = ft.TextField(label="", color='black', border_color='white', value=item.get(col, ""))
                table_cells.append(ft.DataCell(text_box))
                row_textboxes.append(text_box)
            table_textboxes.append(row_textboxes)
            new_line = ft.DataRow(cells=table_cells)
            table.rows.append(new_line)
        self.page.update()

    def fill_texts_from_json(self, sequence_list, keys):
        """Cria linhas de TextFields de acordo com o JSON e preenche os valores"""
        for item in sequence_list:
            row_textboxes = []
            for key in keys:
                text_box = ft.TextField(
                    label=key,
                    color='black',
                    border_color='white',
                    value=item.get(key, "")
                )
                row_textboxes.append(text_box)
                self.container_text_boxs.controls.append(text_box)  # adiciona na coluna/contêiner
            self.page.update()

    def image_attachment_and_description(self, tittle_box_name, description_box_name):
        images_path_list = []
        image_tittles_list = []
        image_descriptions_list = []
        container_images = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        container_quantity_text_box = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        box_images_quantity = ft.TextField(label="Quantidade",
                                           multiline=True,
                                           width=130,
                                           border_color='black', bgcolor='white', border_width=2,
                                           label_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
                                           keyboard_type=ft.KeyboardType.NUMBER,
                                           on_change=self.accept_numbers_only)

        def submit_images(e):
            quantity = int(box_images_quantity.value)
            for a in range(quantity):
                def doc_image_create():
                    image_tittle = ft.TextField(
                        label=tittle_box_name,
                        width=400,
                        border_color='black',
                        bgcolor='white',
                        border_width=2,
                        multiline=True,
                        label_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
                    image_description = ft.TextField(
                        label=description_box_name,
                        width=800,
                        border_color='black',
                        bgcolor='white',
                        border_width=2,
                        multiline=True,
                        label_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
                    image_name = ft.Text(value="------------", size=16, color='white')
                    image_tittles_list.append(image_tittle)
                    image_descriptions_list.append(image_description)

                    file_select = ft.FilePicker()

                    def on_file_pick(ev: ft.FilePickerResultEvent):
                        if ev.files:
                            image_name.value = f'Imagem Selecionada: {ev.files[0].name}'
                            images_path_list.append(ev.files[0].path)
                        else:
                            image_name.value = "Nenhuma Imagem Selecionada"
                        self.page.update()

                    file_select.on_result = on_file_pick
                    image_select_button = ft.ElevatedButton("Selecionar Imagem")
                    image_select_button.on_click = lambda ev: file_select.pick_files(
                        allow_multiple=False,
                        allowed_extensions=["jpg", "jpeg", "png", "gif"])

                    self.page.overlay.append(file_select)
                    container_images.controls.append(image_select_button)
                    container_images.controls.append(image_name)
                    container_images.controls.append(image_tittle)
                    container_images.controls.append(image_description)

                doc_image_create()
            self.page.update()

        button_send_quantity = ft.ElevatedButton(text="+",
                                                 color='black',
                                                 bgcolor='white',
                                                 on_click=submit_images)

        container_quantity_text_box.controls.append(box_images_quantity)
        container_quantity_text_box.controls.append(button_send_quantity)

        self.page.add(container_quantity_text_box)
        self.page.add(container_images)

        return images_path_list, image_tittles_list, image_descriptions_list

    def doc_generate_button(self, function, button_name):
        button = ft.ElevatedButton(text=button_name,
                                   width=200,
                                   height=50,
                                   color="black",
                                   bgcolor="white",
                                   on_click=function)
        self.page.add(button)
        self.page.update()

    def load_from_json(self, json_file_name, compiler_pdflatex, tittle_textbox,
                       file_name_text_box, project_name_text_box, doc_code,
                       date_text_box, responsable_text_box, doc_version_text_box,
                       references_list_text_boxs,
                       objetive_text_box,
                       escopes_list_text_boxs,
                       requests_list_text_boxs,
                       description_text_box,
                       adaptation_list_text_boxs, labels_name_adaptation_list: list, adaptation_table,
                       gooses_list_text_boxs, labels_name_gooses_list: list, gooses_table,
                       integrations_list_text_boxs, labels_name_integrations_list: list, integrations_table,
                       tests_list_text_boxs, labels_name_tests_list: list, tests_table,
                       on_loaded=None):

        json_container = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        def on_file_json_result(e):
            if e.files:
                json_file = e.files[0].path
                json_file_name.value = f"{e.files[0].name}"
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Campos simples
                compiler_pdflatex.value = data.get("Compilador", "")
                tittle_textbox.value = data.get("Titulo da Documentação", "")
                file_name_text_box.value = data.get("Nome do Arquivo", "")
                project_name_text_box.value = data.get("Nome do Projeto", "")
                doc_code.value = data.get("Código da Documentação", "")
                date_text_box.value = data.get("Data de Alteração", "")
                responsable_text_box.value = data.get("Responsável Técnico", "")
                doc_version_text_box.value = data.get("Revisão", "")
                objetive_text_box.value = data.get("Objetivo", "")
                description_text_box.value = data.get("Descrição Detalhada", "")

                # Listas e tabelas
                adaptations = data.get("Adaptações Lógicas", [])
                escopes = data.get("Escopo do Projeto", [])
                requests = data.get("Requisitos", [])
                signals = data.get("Sinalizações", [])
                gooses = data.get("Matriz GOOSE", [])
                references = data.get("Referências Técnicas", [])
                tests = data.get("Testes de Validação", [])

                self.number_lists_lines = [
                    len(adaptations), len(escopes), len(requests),
                    len(signals), len(gooses), len(references), len(tests)
                ]

                # Referências
                if references and len(references_list_text_boxs) > 0:
                    for a in range(min(len(references_list_text_boxs), len(references))):
                        references_list_text_boxs[a].value = references[a]

                # Escopo
                if escopes and len(escopes_list_text_boxs) > 0:
                    for a in range(min(len(escopes_list_text_boxs), len(escopes))):
                        escopes_list_text_boxs[a].value = escopes[a]

                # Requisitos
                if requests and len(requests_list_text_boxs) > 0:
                    for a in range(min(len(requests_list_text_boxs), len(requests))):
                        requests_list_text_boxs[a].value = requests[a]

                # Tabelas automáticas
                if signals:
                    self.fill_table_from_json(integrations_table, integrations_list_text_boxs,
                                              labels_name_integrations_list, signals)

                if adaptations:
                    self.fill_table_from_json(adaptation_table, adaptation_list_text_boxs,
                                              labels_name_adaptation_list, adaptations)

                if gooses:
                    self.fill_table_from_json(gooses_table, gooses_list_text_boxs,
                                              labels_name_gooses_list, gooses)

                if tests:
                    self.fill_table_from_json(tests_table, tests_list_text_boxs,
                                              labels_name_tests_list, tests)

                if on_loaded:
                    on_loaded(self.number_lists_lines)

                self.page.update()
            else:
                json_file_name.value = f"Sem Arquivo de Dados Selecionado"
                self.page.update()

        button = ft.ElevatedButton("Adicionar Arquivo de Dados")
        json_select = ft.FilePicker(on_result=on_file_json_result)
        json_file_name = ft.Text("Sem dados salvos selecionados.", color='white')

        button.on_click = lambda ev: json_select.pick_files(
            allow_multiple=False,
            allowed_extensions=["json"],
            dialog_title="Selecione o arquivo de dados JSON")

        self.page.overlay.append(json_select)
        json_container.controls.append(json_file_name)
        self.page.add(button)
        self.page.add(json_container)

    def select_folder_button(self):
        folder_text = ft.Text("Sem diretório selecionado.", color='white')

        def on_folder_selected(e: ft.FilePickerResultEvent):
            if e.path:
                self.selected_folder = e.path
                folder_text.value = e.path
            else:
                self.selected_folder = None
                folder_text.value = "Sem diretório selecionado."
            self.page.update()

        file_picker = ft.FilePicker(on_result=on_folder_selected)
        self.page.overlay.append(file_picker)

        button = ft.ElevatedButton(
            text="Salvar em",
            on_click=lambda e: file_picker.get_directory_path()
        )

        self.page.add(button, folder_text)
